"""
tests/test_analyzer.py
Test des algorithmes mathématiques (Baseline et Constriction).
Correction : Ajout de la colonne 'velocity_mm_s' requise par l'analyseur.
"""
import pytest
import pandas as pd
import numpy as np
from plr_analyzer import PLRAnalyzer

def test_baseline_maths():
    """Vérifie que la baseline est bien la moyenne avant le flash."""
    an = PLRAnalyzer()
    
    # On crée 2 secondes de données stables à 5.0 mm
    # 60 points (30 fps * 2s)
    an.data = pd.DataFrame({
        'timestamp_s': np.linspace(0, 2, 60),
        'diameter_mm': np.ones(60) * 5.0,
        'diameter_smooth': np.ones(60) * 5.0,
        # CORRECTION : On ajoute une vitesse nulle pour que l'analyseur ne plante pas
        'velocity_mm_s': np.zeros(60) 
    })
    
    # On simule un flash à 1.5s
    # L'algo doit prendre la moyenne entre 0 et 1.5s -> donc 5.0
    metrics = an.analyze(flash_timestamp=1.5)
    
    # Vérification
    assert metrics.get('baseline_mm') == 5.0

def test_constriction_percentage():
    """Vérifie le calcul du pourcentage de constriction."""
    an = PLRAnalyzer()
    
    # Scénario simple :
    # Avant flash : 10 mm
    # Après flash : descend jusqu'à 6 mm
    # Calcul attendu : (10 - 6) / 10 = 40%
    
    times = [0, 1, 2, 3]
    diams = [10.0, 10.0, 6.0, 7.0] # Le min est 6.0
    
    an.data = pd.DataFrame({
        'timestamp_s': times,
        'diameter_mm': diams,
        'diameter_smooth': diams,
        # CORRECTION : Ajout vitesse (factice ici, car on teste juste le % de diamètre)
        'velocity_mm_s': [0.0, 0.0, -4.0, 1.0] 
    })
    
    # Flash à t=0.5 (donc baseline sur t=0 -> 10.0)
    metrics = an.analyze(flash_timestamp=0.5)
    
    # Vérifications
    assert metrics.get('constriction_percent') == 40.0
    assert metrics.get('min_diameter_mm') == 6.0