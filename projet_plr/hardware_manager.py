"""
hardware_manager.py
===================
Gestionnaire de communication avec le dispositif électronique.
Mode Simulation activé.
"""
import logging
import time
import serial.tools.list_ports
try:
    import winsound
except ImportError:
    winsound = None
from PySide6.QtCore import QObject, Signal, QTimer
from serial_worker import SerialWorker

logger = logging.getLogger("Hardware")

class HardwareManager(QObject):
    # Signaux émis vers l'interface
    connection_status_changed = Signal(bool) # True=Connecté, False=Déconnecté
    trigger_pressed = Signal()               # Quand la gâchette est appuyée
    firmware_received = Signal(str)          # Quand la version est reçue
    flash_fired = Signal()                   # Quand la commande de flash est envoyée
    
    def __init__(self):
        super().__init__()
        self.is_connected = False
        self.worker = None
        self.command_queue = []
        self.current_port = None
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)
        self.current_command = None
        self.is_recording = False

    def connect_device(self):
        """Tente de détecter et connecter le dispositif Hardware."""
        logger.info("Recherche du dispositif Hardware...")
        
        # 1. Détection automatique (comme dans le sandbox)
        ports = serial.tools.list_ports.comports()
        if not ports:
            logger.warning("Aucun port COM détecté.")
            self.connection_status_changed.emit(False)
            return False

        selected_port = None
        # Stratégie : On cherche un port avec "USB" dans la description
        for p in ports:
            if "USB" in p.description.upper():
                selected_port = p.device
                break
        
        # Fallback : Si aucun port USB explicite, on prend le premier
        if selected_port is None:
            selected_port = ports[0].device

        self.current_port = selected_port
        logger.info(f"Port sélectionné : {selected_port}")

        # 2. Lancement du Worker
        try:
            if self.worker:
                self.worker.stop()
                self.worker.deleteLater()
            
            self.worker = SerialWorker(selected_port)
            self.worker.data_received.connect(self._on_data_received)
            self.worker.start()
            
            # Attendre que le port soit physiquement ouvert (Fix Race Condition)
            for _ in range(20): # Timeout ~2s
                if self.worker.ser and self.worker.ser.is_open:
                    break
                time.sleep(0.1)
            
            if not (self.worker.ser and self.worker.ser.is_open):
                raise Exception("Le port série ne s'est pas ouvert correctement (Timeout).")

            # Initialisation du module (Commande 'depart')
            logger.info("Initialisation du module...")
            self.worker.send("depart")
            
            # Pause pour laisser le temps au module de s'initialiser (Reset Hard)
            time.sleep(1.5)
            
            self.is_connected = True
            self.connection_status_changed.emit(True)
            return True
            
        except Exception as e:
            logger.error(f"Erreur connexion hardware : {e}")
            self.is_connected = False
            self.connection_status_changed.emit(False)
            return False

    def disconnect_device(self):
        if self.is_connected:
            self.stop_flash()
            time.sleep(0.1)
            
        if self.worker:
            self.worker.stop()
            self.worker = None
        
        self.is_connected = False
        self.connection_status_changed.emit(False)

    def set_recording_state(self, state: bool):
        """Met à jour l'état d'enregistrement pour ignorer les triggers."""
        self.is_recording = state
        if not state:
            self.stop_flash()
            if winsound:
                # Bip système Windows pour signaler la fin
                winsound.MessageBeep(winsound.MB_OK)

    def stop_flash(self):
        """Arrête immédiatement le flash et vide la file d'attente."""
        if self.is_connected and self.worker:
            logger.info(">>> HARDWARE : ARRET FLASH (Sécurité) <<<")
            self.timeout_timer.stop()
            self.command_queue = []
            self.worker.send("Type : commande, Commande :arret_flash")

    def configure_flash_sequence(self, color: str, duration_ms: int, intensity: int = 2000, frequency: float = 0.1, ambiance: int = 0, flash_count: int = 1):
        """
        Envoie la configuration du flash (SANS LE DÉCLENCHER).
        Protocole : Envoi des commandes séquentielles.
        """
        if not self.is_connected or not self.worker:
            logger.warning("Impossible d'envoyer la commande : Non connecté.")
            return

        # 1. Mapping Couleur
        color_map = {"BLUE": "bleu", "RED": "rouge", "WHITE": "blanc"}
        val_color = color_map.get(color, "blanc")
        
        # 2. Conversion Durée (ms -> µs)
        val_us = duration_ms * 1000
        
        logger.info(f"Préparation Séquence Flash : {val_color} / {val_us}us")
        
        # On vide la file d'attente précédente si elle existe
        self.timeout_timer.stop()
        self.command_queue = []
        
        # Ajout des commandes dans la file
        self.command_queue.append(f"Type : commande, Commande :ecrire_couleur_flash , valeur: {val_color}")
        self.command_queue.append(f"Type : commande, Commande :ecrire_duree_flash_us , valeur: {val_us}")
        
        # Nouveaux paramètres
        self.command_queue.append(f"Type : commande, Commande :ecrire_intensite_flash_droit , valeur: {intensity}")
        self.command_queue.append(f"Type : commande, Commande :ecrire_frequence_flash , valeur: {frequency}")
        self.command_queue.append(f"Type : commande, Commande :ecrire_intensite_ambiance_droit , valeur: {ambiance}")
        self.command_queue.append(f"Type : commande, Commande :ecrire_nombre_acquisition , valeur: {flash_count}")
        
        # Lancement de la séquence (envoi de la première commande)
        self._send_next_command()

    def trigger_flash(self):
        """Envoie l'ordre de déclencher le flash (via file d'attente pour synchro)."""
        if self.is_connected:
            logger.info(">>> HARDWARE : DEPART FLASH (Queued) <<<")
            self.command_queue.append("Type : commande, Commande :depart_flash")
            # Si le timer n'est pas actif, c'est qu'aucune séquence n'est en cours, on lance.
            if not self.timeout_timer.isActive():
                self._send_next_command()

    def lancer_sequence_synchro(self):
        """
        Envoie la séquence de synchronisation par Black Frame.
        Séquence : IR OFF -> Pause (1 frame) -> Flash/IR ON
        """
        if self.is_connected:
            logger.info(">>> HARDWARE : SÉQUENCE SYNCHRO (Black Frame) <<<")
            # 1. Couper l'IR (Création de la frame noire)
            self.command_queue.append("Type : commande, Commande :arret_eclairage_ir")
            # 2. Lancer le flash (Le délai inter-commande de 100ms crée le trou noir)
            self.command_queue.append("Type : commande, Commande :depart_flash")
            
            if not self.timeout_timer.isActive():
                self._send_next_command()

    def configure_device(self, intensity: int, frequency: float, ambiance: int, flash_count: int = 1):
        """Envoie uniquement les paramètres de configuration (sans déclencher le flash)."""
        if not self.is_connected or not self.worker: return
        
        logger.info("Envoi Configuration Dispositif...")
        
        self.timeout_timer.stop()
        self.command_queue = []
        
        self.command_queue.append(f"Type : commande, Commande :ecrire_intensite_flash_droit , valeur: {intensity}")
        self.command_queue.append(f"Type : commande, Commande :ecrire_frequence_flash , valeur: {frequency}")
        self.command_queue.append(f"Type : commande, Commande :ecrire_intensite_ambiance_droit , valeur: {ambiance}")
        self.command_queue.append(f"Type : commande, Commande :ecrire_nombre_acquisition , valeur: {flash_count}")
        
        self._send_next_command()

    def request_firmware_version(self):
        """Demande la version du firmware au dispositif."""
        if self.is_connected and self.worker:
            logger.info("Demande version firmware...")
            self.worker.send("Type : commande, Commande :version")

    def _on_data_received(self, data: str):
        """Analyse les données reçues du module."""
        logger.info(f"RX: {data}")
        
        # Note : On ne gère plus l'avancement de la séquence ici car le module ne répond pas 
        # pour les commandes de configuration. L'avancement est géré par le timer.
            
        # Détection du signal de gâchette
        if "TRIG" in data.upper() or "BT1" in data.upper():
            if not self.is_recording:
                logger.info("Gâchette détectée via Série !")
                self.trigger_pressed.emit()
            else:
                logger.info("Gâchette ignorée (Examen en cours).")

        # Détection de la version
        if "version" in data.lower():
            self.firmware_received.emit(data)

    def simulate_trigger_press(self):
        """Appelé par la touche ESPACE pour simuler le clic gâchette."""
        if not self.is_recording:
            logger.info(">>> HARDWARE SIMULATION : GÂCHETTE APPUYÉE <<<")
            self.trigger_pressed.emit()

    def _send_next_command(self):
        """Envoie la prochaine commande de la file d'attente."""
        if self.command_queue:
            cmd = self.command_queue.pop(0)
            self.current_command = cmd
            logger.info(f"Envoi Séquence > {cmd}")
            
            self.worker.send(cmd)
            
            # Signal de synchronisation immédiat (puisqu'on n'a pas de réponse)
            if "depart_flash" in cmd:
                self.flash_fired.emit()

            # Pause de 100ms entre chaque commande pour laisser le temps au µC de traiter
            self.timeout_timer.start(100) 
        else:
            self.current_command = None
            logger.info("Séquence de commande terminée.")

    def _on_timeout(self):
        """Appelé après le délai inter-commande (Flow Control)."""
        # On passe simplement à la commande suivante
        self._send_next_command()