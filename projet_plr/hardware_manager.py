"""
hardware_manager.py
===================
Gestionnaire de communication avec le dispositif PLR via port série (RS232).
Protocole : commandes au format "!commande;" / réponses OK, D, f, F, A.

Architecture : Le µC (micro-contrôleur) gère le flash et la gâchette.
Le PC configure les paramètres, lance l'examen via !depart=1234; et
écoute les signaux retour pour synchroniser l'enregistrement.
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
    connection_status_changed = Signal(bool)
    firmware_received = Signal(str)
    # Signaux d'examen (retour µC)
    exam_started = Signal()             # D reçu : examen démarré (avec retard)
    flash_fired = Signal()              # F ou f reçu : le flash a été déclenché
    flash_ended = Signal()              # A reçu : le flash est terminé
    # Signaux de debug série
    serial_tx = Signal(str)             # Commande envoyée au µC
    serial_rx = Signal(str)             # Réponse reçue du µC
    serial_raw = Signal(str)            # Octets bruts reçus (hex)

    def __init__(self):
        super().__init__()
        self.is_connected = False
        self._handshake_done = False  # True quand "TEST OK" reçu du µC
        self._exam_in_progress = False  # True entre D/F et A (examen µC en cours)
        self.worker = None
        self.command_queue = []
        self.current_port = None
        self.current_command = None
        self._waiting_ok = False
        # Timer de sécurité : si le µC ne répond pas OK après 2s, on passe à la suite
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)
        # Timer handshake : si "TEST OK" n'arrive pas dans les 10s
        self._handshake_timer = QTimer()
        self._handshake_timer.setSingleShot(True)
        self._handshake_timer.timeout.connect(self._on_handshake_timeout)

    # ─── Formatage des commandes PLR ────────────────────────────────
    @staticmethod
    def _fmt(cmd: str) -> str:
        """Encadre une commande au format PLR : !commande;"""
        return f"!{cmd};"

    # ─── Connexion / Déconnexion ────────────────────────────────────
    def connect_device(self):
        """Tente de détecter et connecter le dispositif Hardware."""
        logger.info("Recherche du dispositif Hardware...")

        ports = serial.tools.list_ports.comports()
        if not ports:
            logger.warning("Aucun port COM détecté.")
            self.connection_status_changed.emit(False)
            return False

        selected_port = None
        for p in ports:
            if "USB" in p.description.upper():
                selected_port = p.device
                logger.info(f"Port USB détecté : {p.device} ({p.description})")
                break

        if selected_port is None:
            logger.warning("Aucun port USB détecté — le microcontrôleur n'est pas branché.")
            self.connection_status_changed.emit(False)
            return False

        self.current_port = selected_port
        logger.info(f"Port sélectionné : {selected_port}")

        try:
            if self.worker:
                self.worker.stop()
                self.worker.deleteLater()

            self.worker = SerialWorker(selected_port)
            self.worker.data_received.connect(self._on_data_received)
            self.worker.data_sent.connect(self.serial_tx.emit)
            self.worker.raw_received.connect(self.serial_raw.emit)
            self.worker.connection_lost.connect(self._on_connection_lost)
            self.worker.port_ready.connect(self._on_port_ready)
            self.worker.start()

            # Attente que le port soit ouvert (le flush + init se fait dans _on_port_ready)
            for _ in range(30):
                if self.worker.running:
                    break
                time.sleep(0.1)

            if not self.worker.running:
                raise Exception("Le port série ne s'est pas ouvert correctement (Timeout).")

            return True

        except Exception as e:
            logger.error(f"Erreur connexion hardware : {e}")
            self.is_connected = False
            self.connection_status_changed.emit(False)
            return False

    def _on_port_ready(self):
        """Appelé quand le port série est ouvert et les buffers vidés.
        On attend "TEST OK" ou une réponse à "!version=0;" pour valider."""
        logger.info("Port série ouvert — en attente du µC...")
        self._handshake_done = False
        self._handshake_timer.start(10000)  # Timeout 10s
        # Demander la version pour détecter un µC déjà allumé (pas de "TEST OK" au boot)
        QTimer.singleShot(500, self._send_handshake_probe)

    def _send_handshake_probe(self):
        """Envoie !version=0; pour détecter un µC déjà allumé."""
        if not self._handshake_done and self.worker and self.worker.running:
            logger.info("Envoi sonde handshake : !version=0;")
            self.worker.send(self._fmt("version=0"))

    def _on_handshake_timeout(self):
        """Le µC n'a pas répondu dans les 10s."""
        if not self._handshake_done:
            logger.warning("Timeout handshake : aucune reponse du µC — non pret ou eteint.")
            self.is_connected = False
            self.connection_status_changed.emit(False)

    def disconnect_device(self):
        self._handshake_timer.stop()
        if self.is_connected:
            self.stop_flash()
            time.sleep(0.1)

        if self.worker:
            self.worker.stop()
            self.worker = None

        self.is_connected = False
        self._handshake_done = False
        self.connection_status_changed.emit(False)

    # ─── Commandes de configuration (envoyées AVANT l'examen) ──────
    def set_flash_color(self, color: str):
        """Définit la couleur du flash. color: 'BLUE','RED','WHITE'"""
        color_map = {"BLUE": "bleu", "RED": "rouge", "WHITE": "blanc"}
        val = color_map.get(color, "blanc")
        return self._fmt(f"couleur flash={val}")

    def set_flash_intensity(self, intensity: int):
        """Définit l'intensité du flash (0-1023, 1023=nulle)."""
        val = str(min(max(intensity, 0), 1023)).zfill(4)
        return self._fmt(f"intensité flash={val}")

    def set_flash_duration(self, duration_s: int):
        """Définit la durée du flash en secondes (1-10)."""
        val = str(min(max(duration_s, 1), 10)).zfill(3)
        return self._fmt(f"durée flash={val}")

    def set_flash_delay(self, delay_s: int):
        """Définit le retard avant flash en secondes (0-5)."""
        val = str(min(max(delay_s, 0), 5)).zfill(3)
        return self._fmt(f"retard flash={val}")

    def enqueue_command(self, cmd: str):
        """Ajoute une commande à la file d'attente.
        Si aucune commande n'est en cours, l'envoie immédiatement."""
        self.command_queue.append(cmd)
        if not self._waiting_ok:
            self._send_next_command()

    def configure_flash_sequence(self, color: str, duration_ms: int, intensity: int = 0, delay_s: int = 0):
        """
        Envoie la configuration du flash au µC (SANS LE DÉCLENCHER).
        Le µC stocke ces paramètres et les utilise au prochain départ.
        Chaque commande attend le OK du µC avant d'envoyer la suivante.
        """
        if not self.is_connected or not self.worker:
            logger.warning("Impossible de configurer : Non connecté.")
            return

        duration_s = max(1, round(duration_ms / 1000))
        logger.info(f"Config Flash : couleur={color}, durée={duration_s}s, intensité={intensity}, retard={delay_s}s")

        # Vider la file et stopper tout envoi en cours
        self.timeout_timer.stop()
        self.command_queue = []
        self._waiting_ok = False

        self.command_queue.append(self.set_flash_color(color))
        self.command_queue.append(self.set_flash_duration(duration_s))
        self.command_queue.append(self.set_flash_intensity(intensity))
        self.command_queue.append(self.set_flash_delay(delay_s))

        self._send_next_command()

    # ─── Commandes d'examen ───────────────────────────────────────
    def start_exam(self):
        """
        Envoie la commande de départ d'examen au µC via la file d'attente.
        Ne fait rien si un examen est deja en cours sur le µC.
        """
        if self._exam_in_progress:
            logger.info(">>> Examen deja en cours sur le µC — !depart non envoye <<<")
            return
        if self.is_connected and self.worker:
            logger.info(">>> HARDWARE : DÉPART EXAMEN (logiciel) <<<")
            self.enqueue_command(self._fmt("depart=1234"))

    def stop_flash(self):
        """Arrête immédiatement le flash et vide la file d'attente."""
        if self.is_connected and self.worker:
            logger.info(">>> HARDWARE : ARRET FLASH <<<")
            self.timeout_timer.stop()
            self.command_queue = []
            self.worker.send(self._fmt("arret pwm=0"))

    def set_ir(self, on: bool):
        """Allume ou éteint l'éclairage IR (via la file d'attente)."""
        if self.is_connected and self.worker:
            cmd = self._fmt("marche IR=1") if on else self._fmt("arret IR=0")
            self.enqueue_command(cmd)

    def set_pupil_position(self, x: int, y: int):
        """Envoie les coordonnées de la pupille au dispositif."""
        if self.is_connected and self.worker:
            x_str = str(min(max(x, 0), 999)).zfill(3)
            y_str = str(min(max(y, 0), 999)).zfill(3)
            self.worker.send(self._fmt(f"axe xy={x_str}{y_str}"))

    def request_firmware_version(self):
        """Demande la version du firmware au dispositif."""
        if self.is_connected and self.worker:
            logger.info("Demande version firmware...")
            self.worker.send(self._fmt("version=0"))

    # ─── Réception des données (signaux retour du µC) ─────────────
    def _on_data_received(self, data: str):
        """
        Analyse les signaux retour du µC.
        C'est le cœur de la communication : le µC informe le PC
        de ce qui se passe (flash déclenché, terminé, etc.)
        """
        logger.info(f"RX: {data}")
        self.serial_rx.emit(data)

        # Handshake initial : le µC envoie "TEST OK" au boot
        if data == "TEST OK":
            self._handshake_timer.stop()
            self._handshake_done = True
            self.is_connected = True
            logger.info("Handshake reussi : 'TEST OK' recu du µC.")
            self.connection_status_changed.emit(True)
            return

        # Réponse "version" avant handshake → µC déjà allumé, valider le handshake
        if not self._handshake_done and "version" in data.lower():
            self._handshake_timer.stop()
            self._handshake_done = True
            self.is_connected = True
            logger.info(f"Handshake reussi via reponse version : '{data}'")
            self.connection_status_changed.emit(True)
            self.firmware_received.emit(data)
            return

        # Ignorer les messages avant le handshake
        if not self._handshake_done:
            logger.debug(f"Message ignore (handshake non fait) : {data}")
            return

        if data == "OK":
            logger.debug("ACK reçu du dispositif")
            # OK reçu → envoyer la commande suivante de la file
            if self._waiting_ok:
                self._waiting_ok = False
                self.timeout_timer.stop()
                self._send_next_command()
            return

        # Signaux d'examen retournés par le µC
        if data == "D":
            self._exam_in_progress = True
            logger.info("Signal µC : Départ examen AVEC retard (flash imminent)")
            self.exam_started.emit()

        elif data == "F":
            self._exam_in_progress = True
            logger.info("Signal µC : Flash déclenché (sans retard / gâchette)")
            self.flash_fired.emit()

        elif data == "f":
            # Le µC a déclenché le flash APRÈS le retard configuré.
            # Précédé par un "D".
            logger.info("Signal µC : Flash déclenché (après retard)")
            self.flash_fired.emit()

        elif data == "A":
            self._exam_in_progress = False
            logger.info("Signal µC : Fin du flash")
            self.flash_ended.emit()
            self.set_ir(True)

        # Détection de la version firmware
        if "version" in data.lower() or (len(data) > 3 and data not in ("OK", "D", "f", "F", "A")):
            self.firmware_received.emit(data)

    def _on_connection_lost(self):
        """Gère la perte brutale de connexion."""
        logger.warning("Hardware déconnecté inopinément.")
        self.disconnect_device()

    # ─── File d'attente des commandes ───────────────────────────────
    def _send_next_command(self):
        """Envoie la prochaine commande de la file d'attente.
        Attend le OK du µC avant d'envoyer la suivante."""
        if self.command_queue:
            cmd = self.command_queue.pop(0)
            self.current_command = cmd
            self._waiting_ok = True
            logger.info(f"Envoi > {cmd}")
            self.worker.send(cmd)
            # Timeout de sécurité : si pas de OK après 2s, on continue quand même
            self.timeout_timer.start(2000)
        else:
            self.current_command = None
            self._waiting_ok = False
            logger.info("Séquence de commande terminée.")

    def _on_timeout(self):
        """Timeout de sécurité : le µC n'a pas répondu OK à temps."""
        if self._waiting_ok:
            logger.warning(f"Timeout : pas de OK reçu pour '{self.current_command}' → commande suivante")
            self._waiting_ok = False
            self._send_next_command()
