"""
plr_analyzer.py
===============
Module d'analyse des données du Réflexe Photomoteur (PLR).
Version: 1.1.1 (Fix: Pandas FutureWarning Definitif)

Responsabilités :
- Chargement et nettoyage des données brutes (CSV)
- Lissage du signal (suppression des artefacts/clignements)
- Calcul des métriques biomédicales précises
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Any
from scipy.signal import savgol_filter

# Configuration du logger
logger = logging.getLogger(__name__)

class PLRAnalyzer:
    """
    Moteur d'analyse des courbes pupillométriques.
    
    Attributes:
        data (pd.DataFrame): Données brutes et traitées
        results (Dict): Métriques calculées
    """
    
    def __init__(self):
        """Initialise l'analyseur."""
        self.data: Optional[pd.DataFrame] = None
        self.results: Dict[str, Any] = {}
        self.sampling_rate = 30.0  # FPS par défaut
    
    def load_data(self, file_path: str) -> bool:
        """Charge les données depuis un fichier CSV."""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"Fichier introuvable : {path}")
                return False
            
            self.data = pd.read_csv(path)
            
            required_cols = ['timestamp_s', 'diameter_mm', 'quality_score']
            if not all(col in self.data.columns for col in required_cols):
                logger.error("Format CSV invalide")
                return False
            
            if self.data.empty:
                logger.error("Fichier CSV vide")
                return False

            # Recalcul du taux d'échantillonnage réel
            if len(self.data) > 1:
                duration = self.data['timestamp_s'].iloc[-1] - self.data['timestamp_s'].iloc[0]
                self.sampling_rate = len(self.data) / duration if duration > 0 else 30.0
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur chargement données : {e}")
            return False

    def preprocess(self):
        """
        Nettoie et lisse le signal.
        Corrige les clignements et le bruit de mesure.
        """
        if self.data is None:
            return

        # 1. Filtrage des clignements (valeurs aberrantes ou qualité faible)
        mask_invalid = (self.data['diameter_mm'] <= 0.5) | (self.data['quality_score'] < 40)
        
        self.data['diameter_smooth'] = self.data['diameter_mm'].copy()
        self.data.loc[mask_invalid, 'diameter_smooth'] = np.nan
        
        # 2. Interpolation pour combler les trous
        self.data['diameter_smooth'] = self.data['diameter_smooth'].interpolate(method='linear', limit_direction='both')
        
        # --- CORRECTION PANDAS 2.0+ (La ligne qui posait problème) ---
        # Ancienne méthode obsolète : .fillna(method='bfill')
        # Nouvelle méthode : .bfill()
        self.data['diameter_smooth'] = self.data['diameter_smooth'].bfill().ffill()
        # -------------------------------------------------------------

        # 3. Lissage du signal (Savitzky-Golay)
        window_length = int(self.sampling_rate / 2)
        if window_length % 2 == 0: window_length += 1
        window_length = max(5, window_length)
        
        if len(self.data) > window_length:
            try:
                self.data['diameter_smooth'] = savgol_filter(
                    self.data['diameter_smooth'], 
                    window_length=window_length, 
                    polyorder=2
                )
            except Exception as e:
                logger.warning(f"Lissage impossible : {e}")

        # Calcul de la vitesse (mm/s)
        dt = np.gradient(self.data['timestamp_s'])
        dt[dt == 0] = 0.033 # Sécurité division par zéro
        self.data['velocity_mm_s'] = np.gradient(self.data['diameter_smooth'], self.data['timestamp_s'])

    def analyze(self, flash_timestamp: float = 0.0) -> Dict[str, Any]:
        """Calcule les métriques PLR."""
        if self.data is None:
            return {}
            
        try:
            # 1. Baseline (avant flash)
            if flash_timestamp > 0:
                baseline_data = self.data[self.data['timestamp_s'] < flash_timestamp]
                if len(baseline_data) < 5:
                    baseline_val = self.data['diameter_smooth'].iloc[:15].mean()
                else:
                    baseline_val = baseline_data['diameter_smooth'].mean()
                
                response_data = self.data[self.data['timestamp_s'] >= flash_timestamp]
            else:
                baseline_val = self.data['diameter_smooth'].iloc[:15].mean()
                response_data = self.data
                flash_timestamp = self.data['timestamp_s'].iloc[0]

            if response_data.empty:
                return {}

            # 2. Min Diameter
            min_idx = response_data['diameter_smooth'].idxmin()
            min_val = response_data.loc[min_idx, 'diameter_smooth']
            min_time = response_data.loc[min_idx, 'timestamp_s']
            
            # 3. Amplitude
            amplitude = max(0.0, baseline_val - min_val)
            
            # 4. Vitesse Max de Constriction
            constriction_phase = response_data[response_data['timestamp_s'] <= min_time]
            max_constriction_vel_abs = 0.0
            if not constriction_phase.empty:
                max_vel = constriction_phase['velocity_mm_s'].min()
                max_constriction_vel_abs = abs(max_vel)

            # 5. Latence (Début de la chute de 5%)
            latency = 0.0
            threshold_diameter = baseline_val - (0.05 * amplitude)
            latency_points = response_data[response_data['diameter_smooth'] < threshold_diameter]
            
            if not latency_points.empty:
                onset_time = latency_points['timestamp_s'].iloc[0]
                latency = max(0.0, onset_time - flash_timestamp)
            
            # Résultats
            self.results = {
                "baseline_mm": round(float(baseline_val), 2),
                "min_diameter_mm": round(float(min_val), 2),
                "amplitude_mm": round(float(amplitude), 2),
                "latency_s": round(float(latency), 3),
                "constriction_velocity_mm_s": round(float(max_constriction_vel_abs), 2),
                "constriction_duration_s": round(float(min_time - flash_timestamp - latency), 2),
                "constriction_percent": round((amplitude / baseline_val * 100), 1) if baseline_val > 0 else 0.0
            }

            return self.results

        except Exception as e:
            logger.error(f"Erreur analyse : {e}")
            return {}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test basique
    df = pd.DataFrame({'timestamp_s': [0, 1], 'diameter_mm': [5, 5], 'quality_score': [100, 100]})
    an = PLRAnalyzer()
    an.data = df
    an.preprocess()
    print("Test OK")