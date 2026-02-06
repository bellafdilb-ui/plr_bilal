"""
test_full_suite.py
==================
Suite de tests complète pour le projet PLR.
Couvre : CameraEngine, MainWindow, et la robustesse des données.
"""

import sys
import os
import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

# Ajout du dossier parent au path pour importer les modules du projet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Imports du projet
from camera_engine import CameraEngine
from main_application import MainWindow

# --- FIXTURES (Configuration commune) ---

@pytest.fixture
def mock_camera_hardware():
    """Empêche OpenCV d'essayer d'ouvrir une vraie caméra pendant les tests."""
    with patch('cv2.VideoCapture') as mock_cap:
        # On simule une caméra qui s'ouvre correctement
        mock_instance = mock_cap.return_value
        mock_instance.isOpened.return_value = True
        mock_instance.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_instance.get.return_value = 640.0 # Width/Height simulation
        yield mock_cap

@pytest.fixture
def engine(mock_camera_hardware):
    """Retourne une instance de CameraEngine isolée."""
    eng = CameraEngine(camera_index=0)
    return eng

@pytest.fixture
def main_window(qtbot, mock_camera_hardware):
    """Retourne l'interface graphique montée pour le test."""
    # On mocke la base de données pour ne pas toucher à la vraie prod
    with patch('main_application.DatabaseManager') as MockDB:
        # Simulation d'un patient
        patient_data = {'id': 1, 'name': 'TestUnit', 'species': 'Robot', 'tattoo_id': 'T1000'}
        
        window = MainWindow(patient_data)
        qtbot.addWidget(window) # Enregistre la fenêtre pour le bot de test
        return window

# --- TESTS UNITAIRES : CAMERA ENGINE ---

def test_roi_calculation(engine):
    """Vérifie que le calcul de la zone d'intérêt (ROI) est mathématiquement correct."""
    engine.roi_w = 200
    engine.roi_h = 200
    engine.roi_off_x = 0
    engine.roi_off_y = 0
    
    # Image 1000x1000. Centre = 500,500.
    # ROI attendue : x1=400, y1=400, x2=600, y2=600
    x1, y1, x2, y2 = engine.get_roi_rect(1000, 1000)
    
    assert x1 == 400
    assert y1 == 400
    assert (x2 - x1) == 200
    assert (y2 - y1) == 200

def test_recording_lifecycle(engine, tmp_path):
    """Vérifie la création des fichiers CSV et dossiers frames."""
    # Utilisation d'un dossier temporaire fourni par pytest
    base_path = str(tmp_path / "test_exam")
    
    # 1. Démarrage
    engine.start_recording(base_path)
    assert engine.recording is True
    assert engine.csv_file is not None
    assert os.path.exists(base_path + "_frames")
    
    # 2. Simulation d'écriture
    engine.csv_file.write("test_data\n")
    
    # 3. Arrêt
    engine.stop_recording()
    assert engine.recording is False
    assert engine.csv_file is None
    
    # 4. Vérification fichier
    assert os.path.exists(base_path + ".csv")
    with open(base_path + ".csv", 'r') as f:
        content = f.read()
        assert "timestamp_s" in content # Header présent

# --- TESTS D'INTÉGRATION : GUI (INTERFACE) ---

def test_gui_initialization(main_window):
    """Vérifie que la fenêtre s'ouvre avec le bon titre et le patient."""
    assert "TestUnit" in main_window.windowTitle()
    assert main_window.controls.bt.text() == "▶ LANCER EXAMEN"

def test_history_table_columns_fix(main_window):
    """
    TEST CRITIQUE : Vérifie que le tableau a bien 8 colonnes.
    C'est le correctif du bug 'AttributeError: NoneType object has no attribute data'.
    """
    # Le tableau doit avoir 8 colonnes (0 à 7)
    assert main_window.table_hist.columnCount() == 8
    
    # Vérification des headers
    headers = []
    for i in range(main_window.table_hist.columnCount()):
        item = main_window.table_hist.horizontalHeaderItem(i)
        headers.append(item.text() if item else "")
        
    assert "Date & Heure" in headers[0]
    assert "Intensité (%)" in headers[5]
    # Les deux dernières sont vides (icône et data cachée)

def test_start_button_state(main_window, qtbot):
    """Vérifie que le bouton Lancer se grise quand on clique (simulation)."""
    # On force l'état "prêt"
    main_window.is_camera_ready = True
    main_window.is_hardware_ready = True
    main_window.check_ready_state()
    
    assert main_window.controls.bt.isEnabled() is True
    
    # Simulation du clic
    # Note: On ne clique pas vraiment pour éviter de lancer le thread hardware, 
    # on appelle la méthode connectée pour tester la logique UI
    with patch.object(main_window.engine, 'start_test'): # Mock du moteur
        main_window.start_test()
        assert main_window.is_test_running is True
        assert main_window.controls.bt.isEnabled() is False
        assert "EN COURS" in main_window.controls.bt.text()

def test_settings_update(main_window):
    """Vérifie que changer un slider met à jour la configuration."""
    initial_thresh = main_window.camera_thread.camera.threshold_val
    
    # Changement valeur slider Seuil
    main_window.controls.st.setValue(123)
    
    # Vérification propagation
    assert main_window.camera_thread.camera.threshold_val == 123
    assert main_window.camera_thread.camera.threshold_val != initial_thresh