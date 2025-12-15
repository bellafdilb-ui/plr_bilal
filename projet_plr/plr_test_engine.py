"""
plr_test_engine.py
==================
Moteur de test PLR V2 (Support Flash en Secondes).
"""

import time
import logging
from typing import Dict, Any, Optional
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class PLRTestEngine(QObject):
    """
    Moteur d'exécution du protocole de test PLR (Pupillary Light Reflex).
    
    Gère la séquence temporelle : Baseline -> Flash -> Réponse.
    Synchronise l'enregistrement caméra et le déclenchement du flash.
    """

    flash_triggered = Signal(bool)  
    test_finished = Signal(dict)    
    progress_updated = Signal(float, str) 

    def __init__(self, camera_engine):
        super().__init__()
        self.camera = camera_engine
        self.is_running = False
        
        # Configuration par défaut (en secondes)
        self.baseline_duration = 2.0
        self.flash_count = 1
        self.flash_duration_s = 0.2 # 200ms
        self.response_duration = 5.0
        self.ref_name = "test"

    def configure(self, baseline_duration: float = 2.0, flash_count: int = 1, 
                  flash_duration_ms: int = 200, response_duration: float = 5.0) -> None:
        """
        Configure les paramètres temporels du protocole.

        Args:
            baseline_duration (float): Durée d'enregistrement avant le flash (sec).
            flash_count (int): Nombre de répétitions du flash.
            flash_duration_ms (int): Durée du flash en millisecondes.
            response_duration (float): Durée d'enregistrement après le flash (sec).
        """
        self.baseline_duration = baseline_duration
        self.flash_count = flash_count
        # Conversion ms -> s pour cohérence interne
        self.flash_duration_s = flash_duration_ms / 1000.0
        self.response_duration = response_duration
        
        logger.info(f"Protocole : Base={self.baseline_duration}s, Flash={self.flash_duration_s}s, Tot={self.baseline_duration+self.flash_duration_s+self.response_duration}s")

    def start_test(self, reference_name: str) -> None:
        """
        Lance la séquence de test dans un thread séparé.

        Args:
            reference_name (str): Identifiant unique pour nommer le fichier CSV.
        """
        self.ref_name = reference_name
        self.is_running = True
        
        # Exécution dans un thread séparé pour ne pas geler l'UI
        import threading
        t = threading.Thread(target=self._run_sequence)
        t.daemon = True
        t.start()

    def stop_test(self):
        """Arrête proprement la séquence en cours et l'enregistrement."""
        self.is_running = False
        if self.camera:
            self.camera.stop_csv_recording()

    def _run_sequence(self):
        try:
            if not self.camera or not self.camera.is_ready():
                logger.error("Caméra non prête")
                return

            # 1. Préparation Fichier
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"data/plr_results/{timestamp}_{self.ref_name}.csv"
            
            logger.info("Démarrage enregistrement...")
            self.camera.start_csv_recording(filename)
            
            # PAUSE DE STABILISATION (0.5s)
            # Permet d'éviter que les premières millisecondes soient vides ou instables
            time.sleep(0.5)
            start_time = time.time()
            
            # 2. Boucle des Flashs
            for i in range(self.flash_count):
                if not self.is_running: break
                
                # PHASE BASELINE
                self.progress_updated.emit(0, "Baseline")
                phase_end = time.time() + self.baseline_duration
                while time.time() < phase_end and self.is_running:
                    elapsed = time.time() - start_time
                    self.progress_updated.emit(elapsed, "Baseline")
                    time.sleep(0.05)

                # PHASE FLASH
                flash_ts = time.time() - self.camera.start_time # Temps relatif pour l'analyse
                self.flash_triggered.emit(True) # Flash ON
                
                phase_end = time.time() + self.flash_duration_s
                while time.time() < phase_end and self.is_running:
                    elapsed = time.time() - start_time
                    self.progress_updated.emit(elapsed, "FLASH")
                    time.sleep(0.01) # Boucle rapide
                
                self.flash_triggered.emit(False) # Flash OFF

                # PHASE REPONSE
                phase_end = time.time() + self.response_duration
                while time.time() < phase_end and self.is_running:
                    elapsed = time.time() - start_time
                    self.progress_updated.emit(elapsed, "Réponse")
                    time.sleep(0.05)

            # 3. Fin
            self.stop_test()
            
            # Métadonnées pour l'analyseur
            meta = {
                'csv_path': filename,
                'flash_timestamp': flash_ts,
                'config': {
                    'baseline_duration': self.baseline_duration,
                    'flash_duration_ms': self.flash_duration_s * 1000,
                    'response_duration': self.response_duration
                }
            }
            self.test_finished.emit(meta)

        except Exception as e:
            logger.error(f"Erreur sequence: {e}")
            self.stop_test()