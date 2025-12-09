"""
tests/test_analyzer.py
Test de la logique mathématique (sans interface graphique).
"""
import pytest
import pandas as pd
import numpy as np
from plr_analyzer import PLRAnalyzer

def test_baseline_calculation():
    """Vérifie que la baseline est bien la moyenne des valeurs avant le flash."""
    analyzer = PLRAnalyzer()
    
    # 1. On fabrique de fausses données (Mock)
    # 5 secondes de données à 30 FPS
    # De 0 à 2s (Baseline) : Diamètre constant à 8mm
    # Après 2s : Diamètre descend
    timestamps = np.linspace(0, 5, 150)
    diameters = np.ones(150) * 8.0 # Tout à 8mm par défaut
    
    # On met tout ça dans le DataFrame interne de l'analyseur
    analyzer.data = pd.DataFrame({
        'timestamp_s': timestamps,
        'diameter_mm': diameters,
        'diameter_smooth': diameters # On simule que c'est déjà lissé
    })
    
    # 2. On lance l'analyse (Flash à 2.0 secondes)
    metrics = analyzer.analyze(flash_timestamp=2.0)
    
    # 3. ASSERTION (Le Verdict)
    # La baseline doit être exactement 8.0
    assert metrics['baseline_mm'] == 8.0

def test_constriction_amplitude():
    """Vérifie que le % de constriction est correct."""
    analyzer = PLRAnalyzer()
    
    # Scénario : Baseline à 10mm, descend à 5mm (donc 50% de constriction)
    timestamps = [0, 1, 2, 3, 4]     # Temps
    diameters =  [10, 10, 10, 5, 5]  # Diamètres
    
    analyzer.data = pd.DataFrame({
        'timestamp_s': timestamps,
        'diameter_mm': diameters,
        'diameter_smooth': diameters 
    })
    
    # Flash à t=1.5s (donc baseline calculée sur 0 et 1s -> moyenne 10)
    # Minimum ensuite est 5.
    metrics = analyzer.analyze(flash_timestamp=1.5)
    
    # Calcul attendu : (10 - 5) / 10 * 100 = 50%
    assert metrics['constriction_percent'] == 50.0
    assert metrics['min_diameter_mm'] == 5.0