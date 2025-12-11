"""
hardware_manager.py
===================
Gestionnaire de communication avec le dispositif électronique.
Mode Simulation activé.
"""
import logging
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("Hardware")

class HardwareManager(QObject):
    # Signaux émis vers l'interface
    connection_status_changed = Signal(bool) # True=Connecté, False=Déconnecté
    trigger_pressed = Signal()               # Quand la gâchette est appuyée
    
    def __init__(self):
        super().__init__()
        self.is_connected = False
        self.simulation_mode = True

    def connect_device(self):
        """Tente de se connecter au port Série (Simulation pour l'instant)."""
        logger.info("Recherche du dispositif Hardware...")
        # --- SIMULATION ---
        self.is_connected = True
        self.connection_status_changed.emit(True)
        return True

    def disconnect_device(self):
        self.is_connected = False
        self.connection_status_changed.emit(False)

    def send_flash_command(self, color: str, duration_ms: int):
        """Envoie l'ordre d'allumer le flash."""
        if self.simulation_mode:
            logger.info(f">>> HARDWARE SIMULATION : FLASH {color} pendant {duration_ms}ms <<<")
        else:
            # Plus tard : serial.write(f"FLASH:{color}:{duration_ms}\n".encode())
            pass

    def simulate_trigger_press(self):
        """Appelé par la touche ESPACE pour simuler le clic gâchette."""
        logger.info(">>> HARDWARE SIMULATION : GÂCHETTE APPUYÉE <<<")
        self.trigger_pressed.emit()