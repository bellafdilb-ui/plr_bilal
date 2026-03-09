import serial
import time
import logging
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("SerialWorker")

class SerialWorker(QThread):
    """
    Thread dédié à la communication série asynchrone.
    Gère la lecture en continu sans bloquer l'interface graphique.
    """
    # Signal émis quand une ligne de texte est reçue (ex: 'TRIG')
    data_received = Signal(str)
    data_sent = Signal(str)
    raw_received = Signal(str)   # Log brut hexadécimal pour diagnostic
    connection_lost = Signal()
    port_ready = Signal()  # Émis quand le port est ouvert et les buffers vidés

    def __init__(self, port_name, baud_rate=115200):
        super().__init__()
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.running = False
        self.ser = None

    def run(self):
        """Boucle principale du thread (Lecture)."""
        try:
            logger.info(f"Connexion au port {self.port_name} ({self.baud_rate} bauds)...")
            self.ser = serial.Serial(
                port=self.port_name,
                baudrate=self.baud_rate,
                timeout=0.1,
                write_timeout=1,
                dsrdtr=False,
                rtscts=False
            )

            # Stabilisation du port (important pour les adaptateurs USB-Série)
            time.sleep(0.2)

            # Vider les buffers d'entrée et sortie (données résiduelles)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            logger.info("Buffers série vidés — port prêt.")

            self.running = True
            self.port_ready.emit()
            buffer = ""

            while self.running:
                try:
                    # Lecture de tout ce qui est disponible dans le tampon
                    if self.ser.in_waiting > 0:
                        raw = self.ser.read(self.ser.in_waiting)
                        text = raw.decode('utf-8', errors='replace')
                        # Log brut lisible pour diagnostic
                        clean = text.replace('\r', '').replace('\n', '')
                        if clean:
                            self.raw_received.emit(f"[{len(raw)}B] {clean}")
                        buffer += text

                        # Parser les tokens connus du µC (sans terminateur \n)
                        # Tokens : "OK", "D", "F", "f", "A"
                        buffer = self._parse_buffer(buffer)
                    else:
                        time.sleep(0.05) # Petite pause pour ne pas surcharger le CPU
                        
                except (OSError, serial.SerialException):
                    logger.error("Perte de connexion série (Déconnexion physique ?)")
                    self.connection_lost.emit()
                    break
                except Exception as e:
                    logger.error(f"Erreur lecture série : {e}")
                    time.sleep(0.1)

        except serial.SerialException as e:
            logger.error(f"Impossible d'ouvrir le port {self.port_name} : {e}")
        finally:
            self.close_port()

    def stop(self):
        """Arrête proprement le thread."""
        self.running = False
        self.wait()

    def close_port(self):
        """Ferme la connexion série."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("Port série fermé.")
            
    def _parse_buffer(self, buffer: str) -> str:
        """Parse le buffer pour extraire les tokens du µC.
        Le µC répète ses réponses en continu — on ne garde que la PREMIÈRE
        occurrence de chaque token puis on vide le buffer + le port série.
        """
        # Nettoyer les \r \n en tête
        buffer = buffer.lstrip('\r\n')
        if not buffer:
            return ""

        token = None

        # Token "OK" (2 caractères, sans terminateur)
        if "OK" in buffer:
            token = "OK"

        # Signaux d'examen (1 caractère)
        for sig in ("D", "F", "f", "A"):
            if sig in buffer:
                token = sig
                break

        # Version firmware ou autre texte (chercher un motif connu)
        if token is None and "version" in buffer.lower():
            # Extraire la première occurrence de "version X.XX"
            import re
            m = re.search(r'version\s*[\d.]+', buffer, re.IGNORECASE)
            if m:
                token = m.group(0)

        if token:
            self.data_received.emit(token)
            # Vider tout le buffer + le port série (le µC répète en boucle)
            if self.ser and self.ser.is_open:
                self.ser.reset_input_buffer()
            return ""

        return buffer

    def send(self, message: str):
        """Envoie un message au module (Thread-safe). Format PLR : !commande;"""
        if self.ser and self.ser.is_open:
            try:
                # Vider le buffer d'entrée avant d'envoyer (évite de lire des données anciennes)
                self.ser.reset_input_buffer()
                # Le ';' est le terminateur du protocole PLR — pas de \r\n
                self.ser.write(message.encode('utf-8'))
                self.data_sent.emit(message)
                logger.debug(f"TX: {message}")
            except Exception as e:
                logger.error(f"Erreur d'envoi série : {e}")