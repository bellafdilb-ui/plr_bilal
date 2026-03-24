"""
plr_test_engine.py
==================
Moteur de test PLR V3 - Architecture événementielle.

Le moteur ne commande PAS le flash. Il :
1. Démarre l'enregistrement caméra
2. Attend le retard flash (flash_delay), puis émet delay_complete
3. ATTEND que le flash soit détecté (signal du µC via notify_flash_fired)
4. Enregistre la phase de réponse
5. Termine et émet les métadonnées
"""

import time
import threading
import logging
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class PLRTestEngine(QObject):
    delay_complete = Signal()           # Retard flash termine, pret pour le flash
    flash_detected = Signal()           # Flash détecté (pour l'UI)
    test_finished = Signal(dict)        # Examen terminé avec métadonnées
    progress_updated = Signal(float, str)  # (elapsed_s, phase_name)

    def __init__(self, camera_engine):
        super().__init__()
        self.camera = camera_engine
        self.is_running = False

        # Configuration par défaut
        self.flash_delay = 2.0
        self.flash_count = 1
        self.flash_duration_s = 0.2
        self.response_duration = 5.0
        self.ref_name = "test"

        # Synchronisation inter-thread pour le flash
        self._flash_event = threading.Event()
        self._flash_timestamp = None

    def configure(self, flash_delay: float = 2.0, flash_count: int = 1,
                  flash_duration_ms: int = 200, response_duration: float = 5.0) -> None:
        self.flash_delay = flash_delay
        self.flash_count = flash_count
        self.flash_duration_s = flash_duration_ms / 1000.0
        self.response_duration = response_duration
        logger.info(f"Protocole : Retard={self.flash_delay}s, Flash={self.flash_duration_s}s, "
                    f"Réponse={self.response_duration}s")

    def start_test(self, reference_name: str) -> None:
        """Lance la séquence de test dans un thread séparé."""
        self.ref_name = reference_name
        self.is_running = True
        self._flash_event.clear()
        self._flash_timestamp = None

        t = threading.Thread(target=self._run_sequence)
        t.daemon = True
        t.start()

    def notify_flash_fired(self):
        """
        Appelé par MainWindow quand le µC envoie F ou f.
        Capture le timestamp série (fallback) et débloque la séquence.
        Le T0 réel est déterminé à l'analyse via la black frame hardware
        (coupure IR d'1 frame déclenchée par HardwareManager).
        """
        if self.is_running and self.camera and self.camera.recording:
            self._flash_timestamp = time.time() - self.camera.start_time
            logger.info(f"Flash détecté à t={self._flash_timestamp:.3f}s")
        self._flash_event.set()
        self.flash_detected.emit()

    def stop_test(self):
        """Arrête proprement la séquence en cours."""
        self.is_running = False
        self._flash_event.set()  # Débloquer si en attente
        if self.camera:
            self.camera.stop_recording()

    def _run_sequence(self):
        try:
            if not self.camera or not self.camera.is_ready():
                logger.error("Caméra non prête")
                return

            # 1. Préparation
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_path = f"data/plr_results/{timestamp}_{self.ref_name}"

            logger.info("Démarrage enregistrement...")
            self.camera.start_recording(base_path)
            time.sleep(0.3)  # Stabilisation caméra
            start_time = time.time()

            # 2. Envoyer immediatement le depart au µC
            #    Le retard flash est gere par le µC (commande !retard flash=XXX;)
            self.delay_complete.emit()
            self.progress_updated.emit(0, "Attente flash...")
            logger.info("Depart envoye au µC — attente du flash...")

            # 3. ATTENTE DU FLASH (signal F/f du µC)
            #    Le µC gere le retard en interne, puis déclenche le flash
            total_timeout = self.flash_delay + 30.0  # retard µC + marge
            if not self._flash_event.wait(timeout=total_timeout):
                logger.warning(f"Timeout : Aucun flash detecte apres {total_timeout:.0f}s")
                self.stop_test()
                return

            if not self.is_running:
                self.stop_test()
                return

            flash_ts = self._flash_timestamp or (time.time() - self.camera.start_time)

            # 4. PHASE FLASH (indicateur visuel)
            elapsed = time.time() - start_time
            self.progress_updated.emit(elapsed, "FLASH")
            time.sleep(self.flash_duration_s)

            # 5. PHASE RÉPONSE
            phase_end = time.time() + self.response_duration
            while time.time() < phase_end and self.is_running:
                elapsed = time.time() - start_time
                self.progress_updated.emit(elapsed, "Réponse")
                time.sleep(0.05)

            # 6. Fin
            self.stop_test()

            meta = {
                'csv_path': base_path + ".csv",
                'video_path': base_path + ".avi",
                'flash_timestamp': flash_ts,
                'config': {
                    'flash_delay_s': self.flash_delay,
                    'flash_duration_ms': self.flash_duration_s * 1000,
                    'response_duration': self.response_duration
                }
            }
            self.test_finished.emit(meta)

        except Exception as e:
            logger.error(f"Erreur séquence : {e}")
            self.stop_test()
