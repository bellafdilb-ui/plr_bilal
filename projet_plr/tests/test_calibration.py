"""
tests/test_calibration.py
=========================
Test de la logique de calibration.
"""
import pytest
from unittest.mock import MagicMock, patch
from calibration_dialog import CalibrationDialog
import numpy as np

@pytest.fixture
def mock_camera_engine():
    cam = MagicMock()
    cam.mm_per_pixel = 0.05
    cam.cap.isOpened.return_value = True
    
    # On simule une détection parfaite d'un cercle de 100px
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dummy_data = {
        'diameter_px': 100.0,
        'ellipse': ((320, 240), (100, 100), 0),
        'center_x': 320, 'center_y': 240
    }
    cam.grab_and_detect.return_value = (dummy_frame, dummy_data)
    return cam

def test_calibration_logic(qtbot, mock_camera_engine):
    # On mock ConfigManager pour ne pas écrire sur le disque
    with patch("calibration_dialog.ConfigManager"):
        dlg = CalibrationDialog(mock_camera_engine)
        qtbot.addWidget(dlg)
        
        # 1. Mise à jour manuelle (simule le Timer)
        dlg.update_frame()
        assert dlg.current_px_diameter == 100.0
        assert dlg.lbl_px_size.text() == "100.0 px"
        
        # 2. Test du calcul (10mm réel / 100px mesuré = 0.1 ratio)
        dlg.spin_real_size.setValue(10.0)
        
        # On mock la boite de dialogue de confirmation (répondre OUI)
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_q:
            mock_q.return_value = 16384 # QMessageBox.Yes
            
            # On vérifie que le signal est émis avec la bonne valeur
            with qtbot.waitSignal(dlg.calibration_saved) as blocker:
                dlg.perform_calibration()
            
            assert blocker.args[0] == 0.1