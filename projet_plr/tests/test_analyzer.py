import pytest
import pandas as pd
import numpy as np
from plr_analyzer import PLRAnalyzer

class TestPLRAnalyzer:
    
    def create_dummy_csv(self, filename, duration_s=5.0, fps=30):
        """Génère un CSV simulant une pupille qui se contracte."""
        timestamps = np.linspace(0, duration_s, int(duration_s * fps))
        # Simulation : Baseline 8mm, Flash à 1s, Constriction à 4mm, Retour lent
        diameters = []
        for t in timestamps:
            if t < 1.0: # Baseline
                val = 8.0 + np.random.normal(0, 0.05) # Un peu de bruit
            elif t < 1.5: # Constriction rapide
                val = 8.0 - ((t - 1.0) / 0.5) * 4.0
            else: # Plateau bas puis remontée
                val = 4.0 + (t - 1.5) * 0.5
            diameters.append(max(2.0, val))
            
        df = pd.DataFrame({
            'timestamp_s': timestamps,
            'diameter_mm': diameters,
            'quality_score': [100]*len(timestamps)
        })
        df.to_csv(filename, index=False)
        return filename

    def test_load_data(self, tmp_path):
        """Vérifie que le chargement CSV fonctionne."""
        f = tmp_path / "test_pupil.csv"
        self.create_dummy_csv(f)
        
        analyzer = PLRAnalyzer()
        assert analyzer.load_data(str(f)) == True
        assert analyzer.data is not None
        assert len(analyzer.data) > 0

    def test_metrics_calculation(self, tmp_path):
        """Vérifie les calculs biomédicaux."""
        f = tmp_path / "test_metrics.csv"
        self.create_dummy_csv(f)
        
        analyzer = PLRAnalyzer()
        analyzer.load_data(str(f))
        analyzer.preprocess()
        
        # On dit que le flash a eu lieu à 1.0s
        results = analyzer.analyze(flash_timestamp=1.0)
        
        # Vérifications (avec une marge d'erreur due au bruit/lissage)
        assert 7.8 < results['baseline_mm'] < 8.2  # Devrait être ~8mm
        assert 3.8 < results['min_diameter_mm'] < 4.2 # Devrait être ~4mm
        assert 3.8 < results['amplitude_mm'] < 4.2    # 8 - 4 = 4mm
        assert results['latency_s'] > 0 # La latence doit être positive

    def test_empty_file_handling(self, tmp_path):
        """Vérifie la robustesse face à un fichier vide."""
        f = tmp_path / "empty.csv"
        f.write_text("timestamp_s,diameter_mm,quality_score\n") # Juste le header
        
        analyzer = PLRAnalyzer()
        assert analyzer.load_data(str(f)) == False
