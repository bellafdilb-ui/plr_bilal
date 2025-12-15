"""
tests/test_coverage_gap.py
==========================
Tests ciblés pour combler les lacunes de couverture (Edge cases & Exceptions).
"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
from PySide6.QtCore import Qt

# --- 1. HARDWARE MANAGER ---
from hardware_manager import HardwareManager

def test_hardware_gaps(qtbot):
    hw = HardwareManager()
    
    # Test déconnexion
    with qtbot.waitSignal(hw.connection_status_changed) as blocker:
        hw.disconnect_device()
    assert blocker.args[0] is False
    assert hw.is_connected is False
    
    # Test send_flash_command en mode NON-simulation (branche else)
    hw.simulation_mode = False
    # On vérifie juste que ça ne plante pas (pass)
    hw.send_flash_command("RED", 100)

# --- 2. PLR ANALYZER ---
from plr_analyzer import PLRAnalyzer

def test_analyzer_edge_cases():
    an = PLRAnalyzer()
    
    # Analyse sans données
    assert an.analyze() == {}
    
    # Analyse avec données mais pas de réponse (flash à la fin)
    an.data = pd.DataFrame({'timestamp_s': [0.0, 0.5], 'diameter_smooth': [5.0, 5.0], 'diameter_mm': [5.0, 5.0], 'velocity_mm_s': [0, 0]})
    assert an.analyze(flash_timestamp=1.0) == {}
    
    # Analyse avec dilatation paradoxale (Amplitude < 0)
    # Baseline 5, Min 6 -> Amp -1 -> ramené à 0
    an.data = pd.DataFrame({
        'timestamp_s': [0.0, 1.0, 2.0], 
        'diameter_smooth': [5.0, 5.0, 6.0],
        'diameter_mm': [5.0, 5.0, 6.0],
        'velocity_mm_s': [0, 0, 0]
    })
    res = an.analyze(flash_timestamp=0.5)
    assert res['amplitude_mm'] == 0.0
    
    # Gestion d'exception globale
    an.data = "Ceci n'est pas un DataFrame" # Provoque une erreur
    assert an.analyze() == {}

# --- 3. PLR TEST ENGINE ---
from plr_test_engine import PLRTestEngine

def test_engine_gaps():
    # Cas : Caméra non prête au lancement
    mock_cam = MagicMock()
    mock_cam.is_ready.return_value = False
    
    eng = PLRTestEngine(mock_cam)
    eng._run_sequence() # Doit logger une erreur et quitter sans planter
    
    # Cas : Exception pendant l'enregistrement
    mock_cam.is_ready.return_value = True
    mock_cam.start_csv_recording.side_effect = Exception("Fail")
    eng._run_sequence()
    assert eng.is_running is False

# --- 4. DB MANAGER ---
from db_manager import DatabaseManager

def test_db_json_error(tmp_path):
    """Vérifie la robustesse si le JSON des résultats est corrompu en base."""
    db_file = tmp_path / "bad_json.db"
    db = DatabaseManager(str(db_file))
    
    # Insertion manuelle de JSON invalide
    conn = db._get_connection()
    cur = conn.cursor()
    db.add_patient("1", "A", "B")
    cur.execute("INSERT INTO exams (patient_id, results_json) VALUES (1, '{bad_json:')")
    conn.commit()
    conn.close()
    
    # La récupération ne doit pas planter, mais renvoyer un dict vide
    hist = db.get_patient_history(1)
    assert hist[0]['results_data'] == {}

# --- 5. MAIN APPLICATION ---
from main_application import MainWindow

def test_main_app_gaps(qtbot, tmp_path):
    # Mock complet des dépendances
    with patch("main_application.DatabaseManager"), \
         patch("main_application.ConfigManager"), \
         patch("main_application.HardwareManager"), \
         patch("main_application.CameraThread"):
             
        patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
        win = MainWindow(patient)
        qtbot.addWidget(win)
        
        # Test : Exception lors de l'export Excel
        win.selected_historical_exam = {'id': 1, 'csv_path': 'dummy.csv', 'exam_date': '2023', 'laterality': 'OD'}
        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("test.xlsx", "Excel")):
            with patch("os.path.exists", return_value=True):
                with patch("pandas.DataFrame.to_excel", side_effect=Exception("Excel Fail")):
                    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
                        win.export_excel()
                        mock_crit.assert_called()

        # Test : Erreur suppression fichier (ex: fichier ouvert ailleurs)
        ex_data = {'id': 10, 'exam_date': '2023', 'csv_path': 'del.csv'}
        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=16384): # Yes
            win.db.delete_exam.return_value = True
            with patch("os.path.exists", return_value=True):
                with patch("os.remove", side_effect=Exception("File locked")):
                    # Ne doit pas planter
                    win.delete_history_item(ex_data)

        # Test : Exception dans closeEvent (sauvegarde config)
        win.conf.save = MagicMock(side_effect=Exception("Save Fail"))
        win.close() # Doit se fermer quand même

# --- 6. CAMERA ENGINE ---
from camera_engine import CameraEngine

def test_camera_gaps():
    with patch("camera_engine.cv2"), patch("camera_engine.ConfigManager"):
        cam = CameraEngine(0)
        
        # get_roi_rect avec dimensions nulles
        assert cam.get_roi_rect(0, 0) == (0,0,0,0)
        
        # stop_csv_recording avec erreur de fermeture fichier
        cam.csv_file = MagicMock()
        cam.csv_file.close.side_effect = Exception("Close error")
        cam.stop_csv_recording() # Ne doit pas planter
        assert cam.csv_file is None
        
        # grab_and_detect : Image plus petite que la ROI
        cam.cap = MagicMock()
        cam.cap.isOpened.return_value = True
        small_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cam.cap.read.return_value = (True, small_frame)
        
        # On force le passage dans la branche "image trop petite"
        with patch("camera_engine.cv2.cvtColor", return_value=np.zeros((100,100), dtype=np.uint8)):
             cam.grab_and_detect()

# --- 7. ENTRY POINTS (Lancement Application) ---
import main_application
import welcome_screen
import sys

def test_entry_points():
    """Teste les fonctions main() de démarrage (couverture 100%)."""
    with patch("sys.exit"), patch("PySide6.QtWidgets.QApplication.exec"):
        # Main App
        with patch("main_application.WelcomeScreen"), patch("main_application.MainWindow"):
             main_application.main()
        
        # Welcome Screen
        with patch("welcome_screen.WelcomeScreen"):
             welcome_screen.main()