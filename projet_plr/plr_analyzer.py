"""
plr_analyzer.py
===============
Module d'analyse des données du Réflexe Photomoteur (PLR).

Responsabilités :
- Chargement et nettoyage des données brutes (CSV)
- Lissage du signal (suppression des artefacts/clignements)
- Calcul des métriques biomédicales précises
- Export des résultats d'analyse

Métriques calculées :
- Baseline (mm) : Diamètre moyen avant stimulation
- Latency (s) : Temps de réaction après stimulation
- Constriction Velocity (mm/s) : Vitesse max de contraction
- Constriction Amplitude (mm) : Différence Baseline - Min
- Min Diameter (mm) : Diamètre minimal atteint
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
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
        self.sampling_rate = 30.0  # FPS par défaut, sera recalculé
    
    def load_data(self, file_path: str) -> bool:
        """
        Charge les données depuis un fichier CSV généré par CameraEngine.
        
        Args:
            file_path: Chemin vers le fichier CSV
            
        Returns:
            bool: True si chargement réussi
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"Fichier introuvable : {path}")
                return False
            
            # Lecture du CSV
            self.data = pd.read_csv(path)
            
            # Vérification des colonnes requises (format défini dans camera_engine.py)
            required_cols = ['timestamp_s', 'diameter_mm', 'quality_score']
            if not all(col in self.data.columns for col in required_cols):
                logger.error("Format CSV invalide : colonnes manquantes")
                return False
            
            if self.data.empty:
                logger.error("Fichier CSV vide")
                return False

            # Recalcul du taux d'échantillonnage réel
            if len(self.data) > 1:
                duration = self.data['timestamp_s'].iloc[-1] - self.data['timestamp_s'].iloc[0]
                self.sampling_rate = len(self.data) / duration if duration > 0 else 30.0
            
            logger.info(f"Données chargées : {len(self.data)} échantillons (Fs={self.sampling_rate:.1f}Hz)")
            return True
            
        except Exception as e:
            logger.error(f"Erreur chargement données : {e}")
            return False

    def preprocess(self, blink_threshold: float = 0.5) -> None:
        """
        Nettoie et lisse le signal.
        
        Étapes :
        1. Filtrage des clignements (diamètre=0 ou chute brutale)
        2. Interpolation des données manquantes
        3. Lissage Savitzky-Golay
        
        Args:
            blink_threshold: Seuil de variation brutale (mm/frame)
        """
        if self.data is None:
            return

        # 1. Gestion des clignements et pertes de tracking
        # On considère comme artefact : diamètre <= 0 ou qualité faible
        mask_invalid = (self.data['diameter_mm'] <= 0.5) | (self.data['quality_score'] < 40)
        
        # Copie pour traitement
        self.data['diameter_smooth'] = self.data['diameter_mm'].copy()
        self.data.loc[mask_invalid, 'diameter_smooth'] = np.nan
        
        # 2. Interpolation linéaire pour combler les trous (clignements)
        self.data['diameter_smooth'] = self.data['diameter_smooth'].interpolate(method='linear', limit_direction='both')
        
        # Si après interpolation il reste des NaNs (ex: début/fin invalides), on remplit
        self.data['diameter_smooth'] = self.data['diameter_smooth'].fillna(method='bfill').fillna(method='ffill')

        # 3. Lissage du signal (Savitzky-Golay filter)
        # Fenêtre adaptée au FPS (env. 0.5s)
        window_length = int(self.sampling_rate / 2)
        if window_length % 2 == 0: window_length += 1  # Doit être impair
        window_length = max(5, window_length)  # Minimum 5
        
        if len(self.data) > window_length:
            try:
                self.data['diameter_smooth'] = savgol_filter(
                    self.data['diameter_smooth'], 
                    window_length=window_length, 
                    polyorder=2
                )
            except Exception as e:
                logger.warning(f"Lissage impossible (signal trop court?) : {e}")

        # Calcul de la dérivée (Vitesse en mm/s)
        # diff / dt
        dt = np.gradient(self.data['timestamp_s'])
        # Éviter division par zéro
        dt[dt == 0] = 0.033 
        
        self.data['velocity_mm_s'] = np.gradient(self.data['diameter_smooth'], self.data['timestamp_s'])

    def analyze(self, flash_timestamp: float = 0.0) -> Dict[str, Any]:
        """
        Calcule les métriques PLR.
        
        Args:
            flash_timestamp: Temps (s) où le flash a été déclenché (normalement géré par le protocole)
                             Si 0.0, on suppose que le flash est au début ou détecté automatiquement.
        
        Returns:
            Dict contenant les résultats
        """
        if self.data is None:
            return {}
            
        # Par défaut, on analyse tout, mais l'idéal est de connaître le moment du flash
        # On définit une fenêtre "Baseline" avant le flash (ex: 0 à flash_timestamp)
        # Et une fenêtre "Response" après
        
        # Pour simplifier ici, on cherche le min global après le début
        # Dans un vrai scénario, flash_timestamp viendrait de plr_test_engine
        
        try:
            # --- 1. Baseline (Moyenne sur les premiers 10% ou avant flash) ---
            # Si flash_timestamp est fourni et > 0
            if flash_timestamp > 0:
                baseline_data = self.data[self.data['timestamp_s'] < flash_timestamp]
                # Si pas assez de données avant, on prend les 500ms premières
                if len(baseline_data) < 5:
                    baseline_val = self.data['diameter_smooth'].iloc[:15].mean()
                else:
                    baseline_val = baseline_data['diameter_smooth'].mean()
                
                # Zone de recherche de réponse : après le flash
                response_data = self.data[self.data['timestamp_s'] >= flash_timestamp]
            else:
                # Si pas de timestamp flash, on suppose baseline = début
                baseline_val = self.data['diameter_smooth'].iloc[:15].mean() # ~500ms à 30fps
                response_data = self.data
                flash_timestamp = self.data['timestamp_s'].iloc[0]

            if response_data.empty:
                logger.warning("Pas de données de réponse")
                return {}

            # --- 2. Minimum Diameter (Constriction maximale) ---
            min_idx = response_data['diameter_smooth'].idxmin()
            min_val = response_data.loc[min_idx, 'diameter_smooth']
            min_time = response_data.loc[min_idx, 'timestamp_s']
            
            # --- 3. Amplitude ---
            amplitude = baseline_val - min_val
            # Si amplitude négative (dilatation ??), on met 0
            amplitude = max(0.0, amplitude)
            
            # --- 4. Constriction Velocity (Vitesse Max de fermeture) ---
            # On cherche la vitesse minimale (la plus négative) dans la phase de constriction
            # La constriction se passe entre le flash et le min_time
            constriction_phase = response_data[response_data['timestamp_s'] <= min_time]
            if not constriction_phase.empty:
                max_constriction_vel = constriction_phase['velocity_mm_s'].min() # Le plus négatif
                # On le stocke en valeur absolue pour la lisibilité
                max_constriction_vel_abs = abs(max_constriction_vel)
            else:
                max_constriction_vel_abs = 0.0

            # --- 5. Latency (Temps de réaction) ---
            # Définition : Moment où la vitesse dépasse un seuil (ex: 10% de la vitesse max)
            # ou moment où le diamètre quitte la baseline de 5%
            latency = 0.0
            threshold_diameter = baseline_val - (0.05 * amplitude) # 5% de chute
            
            latency_points = response_data[response_data['diameter_smooth'] < threshold_diameter]
            if not latency_points.empty:
                onset_time = latency_points['timestamp_s'].iloc[0]
                latency = onset_time - flash_timestamp
                latency = max(0.0, latency)
            
            # --- Compilation des résultats ---
            self.results = {
                "baseline_mm": round(float(baseline_val), 2),
                "min_diameter_mm": round(float(min_val), 2),
                "amplitude_mm": round(float(amplitude), 2),
                "latency_s": round(float(latency), 3),
                "constriction_velocity_mm_s": round(float(max_constriction_vel_abs), 2),
                "constriction_duration_s": round(float(min_time - flash_timestamp - latency), 2)
            }
            
            # % de constriction
            if baseline_val > 0:
                self.results["constriction_percent"] = round((amplitude / baseline_val) * 100, 1)
            else:
                self.results["constriction_percent"] = 0.0

            logger.info(f"Analyse terminée : {self.results}")
            return self.results

        except Exception as e:
            logger.error(f"Erreur durant l'analyse : {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {}

# ===========================
# TEST STANDALONE
# ===========================
if __name__ == "__main__":
    # Configuration basic du logging pour le test
    logging.basicConfig(level=logging.INFO)
    
    analyzer = PLRAnalyzer()
    
    # Simulation ou chargement d'un fichier réel
    # Pour tester, assurez-vous d'avoir un fichier CSV dans recordings/
    # test_file = "recordings/test_recording_2023....csv"
    
    # Création de données dummy pour tester le code sans fichier
    print("--- Test avec données simulées ---")
    t = np.linspace(0, 5, 150) # 5 secondes, 30 fps
    # Simulation: Baseline 5mm, Flash à 1s, Constriction à 3mm, Retour
    d = 5.0 - 2.0 * np.exp(-((t - 1.5)**2) / 0.2) 
    d[t < 1.0] = 5.0 # Baseline stable avant 1s
    # Ajout bruit
    d_noisy = d + np.random.normal(0, 0.05, size=len(t))
    
    # Création DataFrame
    df = pd.DataFrame({
        'timestamp_s': t,
        'diameter_mm': d_noisy,
        'quality_score': [100]*len(t)
    })
    
    # Sauvegarde temporaire
    df.to_csv("temp_test_plr.csv", index=False)
    
    # Test chargement
    if analyzer.load_data("temp_test_plr.csv"):
        # Test Preprocessing
        analyzer.preprocess()
        
        # Test Analyse (Flash simulé à 1.0s)
        res = analyzer.analyze(flash_timestamp=1.0)
        
        print("\nRésultats de l'analyse :")
        for k, v in res.items():
            print(f"  - {k}: {v}")
            
    # Nettoyage
    try:
        import os
        os.remove("temp_test_plr.csv")
    except:
        pass