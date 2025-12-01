"""
plr_test_engine.py
==================
Moteur d'orchestration des tests PLR (Pupillary Light Reflex).
Version: 1.1.0 (Multi-Flash Support)
"""

import time
import logging
from enum import Enum
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

class TestPhase(Enum):
    """Phases du protocole PLR."""
    IDLE = "Prêt"
    BASELINE = "Baseline"
    FLASH = "Stimulation"
    RESPONSE = "Réponse"
    FINISHED = "Terminé"

class PLRTestEngine(QObject):
    """
    Orchestrateur de test PLR.
    Supporte les protocoles multi-flash.
    """
    
    # Signaux
    test_started = Signal()
    test_finished = Signal(dict)
    test_aborted = Signal()
    phase_changed = Signal(str)
    flash_triggered = Signal(bool)
    progress_updated = Signal(float, str)
    error_occurred = Signal(str)

    def __init__(self, camera_engine):
        super().__init__()
        self.camera = camera_engine
        
        # Configuration par défaut
        self.config = {
            "baseline_duration": 2.0,
            "flash_count": 1,
            "flash_duration_ms": 200,
            "response_duration": 5.0
        }
        
        self.current_phase = TestPhase.IDLE
        self.start_time = 0.0
        self.phase_start_time = 0.0
        self.flash_timestamp = 0.0
        self.current_flash_idx = 0  # Compteur de flashs
        self.csv_path = ""
        
        self.timer = QTimer()
        self.timer.setInterval(20)  # 50 Hz
        self.timer.timeout.connect(self._update_loop)

    def configure(self, baseline_duration=2.0, flash_count=1, flash_duration_ms=200, response_duration=5.0, **kwargs):
        """Met à jour le protocole."""
        self.config["baseline_duration"] = float(baseline_duration)
        self.config["flash_count"] = int(flash_count)
        self.config["flash_duration_ms"] = int(flash_duration_ms)
        self.config["response_duration"] = float(response_duration)
        logger.info(f"Protocole configuré : {self.config}")

    def start_test(self, patient_id: str = "Test"):
        if not self.camera or not self.camera.is_ready():
            self.error_occurred.emit("Caméra non prête.")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"PLR_{patient_id}_{timestamp}.csv"
            output_dir = Path("data/plr_results")
            output_dir.mkdir(parents=True, exist_ok=True)
            self.csv_path = str(output_dir / filename)
            
            logger.info("Démarrage enregistrement...")
            self.camera.start_csv_recording(self.csv_path)
            
            # Reset
            self.start_time = time.time()
            self.current_flash_idx = 0
            self._set_phase(TestPhase.BASELINE)
            
            self.timer.start()
            self.test_started.emit()
            
        except Exception as e:
            logger.error(f"Erreur démarrage: {e}")
            self.error_occurred.emit(str(e))
            self.abort_test()

    def stop_test(self):
        self.timer.stop()
        if self.camera:
            self.camera.stop_csv_recording()
        
        self._set_phase(TestPhase.FINISHED)
        self.flash_triggered.emit(False)
        
        result_meta = {
            "csv_path": self.csv_path,
            "flash_timestamp": self.flash_timestamp,
            "duration": time.time() - self.start_time,
            "config": self.config
        }
        
        self.test_finished.emit(result_meta)
        QTimer.singleShot(2000, lambda: self._set_phase(TestPhase.IDLE))

    def abort_test(self):
        self.timer.stop()
        if self.camera:
            self.camera.stop_csv_recording()
        self._set_phase(TestPhase.IDLE)
        self.flash_triggered.emit(False)
        self.test_aborted.emit()

    def _set_phase(self, phase: TestPhase):
        self.current_phase = phase
        self.phase_start_time = time.time()
        self.phase_changed.emit(phase.value)

    def _update_loop(self):
        current = time.time()
        elapsed_total = current - self.start_time
        elapsed_phase = current - self.phase_start_time
        
        self.progress_updated.emit(elapsed_total, self.current_phase.value)
        
        # Machine à états
        if self.current_phase == TestPhase.BASELINE:
            if elapsed_phase >= self.config["baseline_duration"]:
                # Fin Baseline -> Premier Flash
                self.current_flash_idx = 1
                self._set_phase(TestPhase.FLASH)
                self.flash_triggered.emit(True)
                # On note le timestamp du PREMIER flash pour l'analyse
                if self.current_flash_idx == 1:
                    self.flash_timestamp = elapsed_total

        elif self.current_phase == TestPhase.FLASH:
            # Durée flash en secondes (ms / 1000)
            duration_s = self.config["flash_duration_ms"] / 1000.0
            if elapsed_phase >= duration_s:
                self.flash_triggered.emit(False)
                self._set_phase(TestPhase.RESPONSE)

        elif self.current_phase == TestPhase.RESPONSE:
            if elapsed_phase >= self.config["response_duration"]:
                # Fin d'un cycle Réponse
                if self.current_flash_idx < self.config["flash_count"]:
                    # Encore des flashs à faire -> Retour FLASH
                    self.current_flash_idx += 1
                    self._set_phase(TestPhase.FLASH)
                    self.flash_triggered.emit(True)
                else:
                    # Tous les flashs faits -> FIN
                    self.stop_test()