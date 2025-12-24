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

    def __init__(self, port_name, baud_rate=115000):
        super().__init__()
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.running = False
        self.ser = None

    def run(self):
        """Boucle principale du thread (Lecture)."""
        try:
            logger.info(f"Connexion au port {self.port_name} ({self.baud_rate} bauds)...")
            # Timeout court pour rendre la boucle réactive
            self.ser = serial.Serial(self.port_name, self.baud_rate, timeout=0.1, write_timeout=1)
            self.running = True
            
            buffer = ""
            
            while self.running:
                try:
                    # Lecture de tout ce qui est disponible dans le tampon
                    if self.ser.in_waiting > 0:
                        raw = self.ser.read(self.ser.in_waiting)
                        text = raw.decode('utf-8', errors='replace')
                        buffer += text
                        
                        # Si le buffer contient des mots-clés ou une fin de ligne, on émet
                        if "Ok" in buffer or "ok" in buffer or "None" in buffer or "\n" in buffer or "TRIG" in buffer or "bt1" in buffer or "BT1" in buffer:
                            self.data_received.emit(buffer.strip())
                            buffer = "" # On vide le buffer une fois traité
                    else:
                        time.sleep(0.05) # Petite pause pour ne pas surcharger le CPU
                        
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
            
    def send(self, message: str):
        """Envoie un message au module (Thread-safe)."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((message + "\n").encode('utf-8'))
            except Exception as e:
                logger.error(f"Erreur d'envoi série : {e}")