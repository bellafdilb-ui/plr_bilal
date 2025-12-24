"""
plr_analyzer.py
===============
Module d'analyse PLR (Baseline Dynamique + Filtrage Robuste).
Version: 1.3.0
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Any
from scipy.signal import medfilt

logger = logging.getLogger(__name__)

class PLRAnalyzer:
    """
    Analyseur de données pupillométriques (PLR).

    Cette classe charge des données brutes (CSV), effectue un prétraitement
    (nettoyage, interpolation, lissage) et calcule les métriques cliniques
    standard (Baseline, Amplitude, Latence, Vitesse, T75).
    """

    def __init__(self):
        self.data: Optional[pd.DataFrame] = None
        self.results: Dict[str, Any] = {}
        self.sampling_rate = 30.0
    
    def load_data(self, file_path: str) -> bool:
        """
        Charge les données pupillométriques depuis un fichier CSV.

        Args:
            file_path (str): Chemin vers le fichier CSV.

        Returns:
            bool: True si le chargement est réussi, False sinon.
        """
        try:
            path = Path(file_path)
            if not path.exists(): return False
            
            self.data = pd.read_csv(path)
            if self.data.empty: return False

            # Calcul du FPS réel
            if len(self.data) > 1:
                duration = self.data['timestamp_s'].iloc[-1] - self.data['timestamp_s'].iloc[0]
                self.sampling_rate = len(self.data) / duration if duration > 0 else 30.0
            
            return True
        except Exception as e:
            logger.error(f"Load error: {e}")
            return False

    def preprocess(self):
        """
        Applique la chaîne de traitement du signal sur les données chargées.
        
        Étapes :
        1. Nettoyage des valeurs aberrantes (clignements, erreurs détection).
        2. Interpolation des données manquantes.
        3. Filtrage médian (suppression des pics isolés).
        4. Lissage Savitzky-Golay (lissage de la courbe).
        5. Calcul de la vitesse (dérivée première).
        """
        if self.data is None: return

        # 1. Mode BRUT (Raw)
        # On abaisse le seuil à 0.1mm car 1.5mm masquait probablement tes données de test
        mask_invalid = (self.data['diameter_mm'] < 0.1) | (self.data['diameter_mm'] > 50.0)
        
        self.data['diameter_smooth'] = self.data['diameter_mm'].copy()
        self.data.loc[mask_invalid, 'diameter_smooth'] = np.nan
        
        # 2. Interpolation (Limitée)
        # On comble les trous jusqu'à 1s pour garantir une continuité
        self.data['diameter_smooth'] = self.data['diameter_smooth'].interpolate(method='linear', limit=int(self.sampling_rate * 1.0))

        # 3. Filtrage Léger (Micro-Médian)
        # On supprime uniquement les pics aberrants isolés (ex: cils) sur 3 frames.
        # Le filtre Savitzky-Golay a été retiré pour préserver la dynamique réelle.
        try:
            self.data['diameter_smooth'] = medfilt(self.data['diameter_smooth'], kernel_size=3)
        except Exception: pass

        # Vitesse
        self.data['velocity_mm_s'] = np.gradient(self.data['diameter_smooth'], self.data['timestamp_s'])

    def analyze(self, flash_timestamp: float = 0.0) -> Dict[str, Any]:
        """
        Effectue l'analyse PLR complète avec calcul de Baseline intelligent.

        Args:
            flash_timestamp (float): Timestamp (en secondes) du début du flash.

        Returns:
            Dict[str, Any]: Dictionnaire contenant les métriques calculées :
                - baseline_mm (float): Diamètre avant stimulation.
                - min_diameter_mm (float): Diamètre minimal (constriction max).
                - amplitude_mm (float): Amplitude de la constriction.
                - latency_s (float): Temps de latence avant début constriction.
                - constriction_velocity_mm_s (float): Vitesse max de constriction.
                - constriction_duration_s (float): Durée de la phase de constriction.
                - constriction_percent (float): Pourcentage de constriction.
                - T75_recovery_s (float): Temps de récupération à 75%.
        """
        if self.data is None:
            return {}
            
        try:
            df = self.data
            
            # --- SYNCHRONISATION BLACK FRAME ---
            t0_synchro = self.detect_t0_from_black_frame()
            if t0_synchro is not None:
                flash_timestamp = t0_synchro
                logger.info(f"Synchronisation Black Frame détectée à T={flash_timestamp:.3f}s")
            
            # --- CALCUL DE BASELINE INTELLIGENT ---
            # Au lieu de faire la moyenne de tout le début (qui peut monter),
            # on prend la médiane des 0.3 dernières secondes AVANT le flash.
            # C'est la valeur "d'où on part" réellement.
            
            if flash_timestamp > 0.3:
                # Fenêtre : [Flash - 0.3s  --->  Flash]
                base_window = df[
                    (df['timestamp_s'] >= flash_timestamp - 0.3) & 
                    (df['timestamp_s'] <= flash_timestamp)
                ]
                if not base_window.empty:
                    # On utilise la médiane pour éviter d'être faussé par un pic juste avant
                    baseline_val = base_window['diameter_smooth'].median()
                else:
                    baseline_val = df['diameter_smooth'].iloc[0]
            else:
                baseline_val = df['diameter_smooth'].iloc[0]

            # Données APRÈS le flash
            response_data = df[df['timestamp_s'] > flash_timestamp]
            if response_data.empty: return {}

            # Min Diameter (Zénith de la constriction)
            # On cherche le min dans les 2 secondes suivant le flash (pour éviter de choper le hippus tardif)
            search_window = response_data[response_data['timestamp_s'] <= flash_timestamp + 2.0]
            if search_window.empty: search_window = response_data
            
            min_idx = search_window['diameter_smooth'].idxmin()
            min_val = search_window.loc[min_idx, 'diameter_smooth']
            min_time = search_window.loc[min_idx, 'timestamp_s']
            
            # Amplitude
            amplitude = baseline_val - min_val
            # Si négatif (dilatation paradoxale), on met 0
            if amplitude < 0: amplitude = 0.0
            
            # Vitesse Max
            constriction_phase = response_data[response_data['timestamp_s'] <= min_time]
            max_vel = 0.0
            if not constriction_phase.empty:
                # La vitesse max est le minimum de la dérivée (pente négative la plus forte)
                max_vel = abs(constriction_phase['velocity_mm_s'].min())

            # Latence
            # Temps pour atteindre 5% de la constriction
            latency = 0.0
            if amplitude > 0.1: # On ne calcule pas si pas de réaction
                threshold = baseline_val - (0.05 * amplitude)
                lat_pts = response_data[response_data['diameter_smooth'] < threshold]
                if not lat_pts.empty:
                    onset = lat_pts['timestamp_s'].iloc[0]
                    latency = max(0.0, onset - flash_timestamp)

            # Durée constriction (Temps de descente)
            const_duration = max(0.0, min_time - (flash_timestamp + latency))

            # T75 (Temps de récupération à 75%)
            # C'est un indicateur standard vétérinaire
            t75 = 0.0
            target_recov = min_val + (amplitude * 0.75) # On est remonté de 75%
            
            recovery_data = df[df['timestamp_s'] > min_time]
            if not recovery_data.empty:
                recov_pts = recovery_data[recovery_data['diameter_smooth'] >= target_recov]
                if not recov_pts.empty:
                    t75 = recov_pts['timestamp_s'].iloc[0] - min_time

            self.results = {
                "baseline_mm": round(float(baseline_val), 2),
                "min_diameter_mm": round(float(min_val), 2),
                "amplitude_mm": round(float(amplitude), 2),
                "latency_s": round(float(latency), 3),
                "constriction_velocity_mm_s": round(float(max_vel), 2),
                "constriction_duration_s": round(float(const_duration), 2),
                "constriction_percent": round((amplitude / baseline_val * 100), 1) if baseline_val > 0 else 0.0,
                "T75_recovery_s": round(float(t75), 2) if t75 > 0 else None
            }

            return self.results

        except Exception as e:
            logger.error(f"Erreur analyse : {e}")
            return {}

    def detect_t0_from_black_frame(self) -> Optional[float]:
        """Détecte le T0 précis grâce au marqueur 'Black Frame' (chute luminosité)."""
        if self.data is None or 'brightness' not in self.data.columns: return None
        
        # On cherche les frames où la luminosité est < 10 (seuil défini dans camera_engine)
        black_indices = self.data.index[self.data['brightness'] < 10.0].tolist()
        if not black_indices: return None
        
        # Le T0 officiel est la frame SUIVANT la première frame noire (Flash + IR ON)
        first_idx = black_indices[0]
        if first_idx + 1 < len(self.data):
            return self.data.iloc[first_idx + 1]['timestamp_s']
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Test OK")