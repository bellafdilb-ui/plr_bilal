"""
tests/test_camera.py
====================
Test du moteur de caméra avec Mocking d'OpenCV.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from camera_engine import CameraEngine

@pytest.fixture
def mock_cv2():
    """Simule le module cv2 pour ne pas avoir besoin de webcam."""
    with patch("camera_engine.cv2") as m_cv2, \
         patch("camera_engine.ConfigManager"): # On mock aussi la config
        
        # Simulation de VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        
        # Simulation d'une frame noire (480x640)
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, dummy_frame)
        
        m_cv2.VideoCapture.return_value = mock_cap
        
        # Constantes OpenCV nécessaires
        m_cv2.CAP_DSHOW = 700
        m_cv2.CAP_MSMF = 1400
        m_cv2.CAP_ANY = 0
        m_cv2.COLOR_BGR2GRAY = 6
        m_cv2.COLOR_GRAY2BGR = 8
        
        # Fonctions de traitement d'image (retournent des images vides)
        m_cv2.cvtColor.return_value = np.zeros((480, 640), dtype=np.uint8)
        m_cv2.GaussianBlur.return_value = np.zeros((480, 640), dtype=np.uint8)
        m_cv2.threshold.return_value = (0, np.zeros((480, 640), dtype=np.uint8))
        m_cv2.findContours.return_value = ([], None)
        
        yield m_cv2

def test_camera_init(mock_cv2):
    cam = CameraEngine(0)
    assert cam.is_ready()
    mock_cv2.VideoCapture.assert_called()

def test_grab_and_detect(mock_cv2):
    cam = CameraEngine(0)
    frame, data = cam.grab_and_detect()
    assert frame is not None
    assert data is None # Pas de pupille sur une image noire

def test_recording_lifecycle(mock_cv2, tmp_path):
    cam = CameraEngine(0)
    csv = tmp_path / "rec.csv"
    cam.start_csv_recording(str(csv))
    assert cam.recording is True
    cam.stop_csv_recording()
    assert cam.recording is False
    assert csv.exists()

def test_display_modes(mock_cv2):
    """Vérifie que les différents modes d'affichage ne plantent pas."""
    cam = CameraEngine(0)
    
    # Mode Binaire
    cam.set_display_mode('binary')
    frame, _ = cam.grab_and_detect()
    assert frame is not None
    
    # Mode Mosaïque
    cam.set_display_mode('mosaic')
    frame, _ = cam.grab_and_detect()
    assert frame is not None
    # La mosaïque doit avoir la même taille que l'originale (640x480)
    assert frame.shape[0] == 480
    assert frame.shape[1] == 640

def test_camera_setters(mock_cv2):
    """Vérifie les setters de configuration."""
    cam = CameraEngine(0)
    cam.set_threshold(100)
    assert cam.threshold_val == 100
    cam.set_blur_kernel(3)
    assert cam.blur_val == 3
    cam.set_blur_kernel(4) # Should be odd
    assert cam.blur_val == 5

def test_roi_calculation(mock_cv2):
    """Vérifie le calcul du rectangle ROI."""
    cam = CameraEngine(0)
    cam.roi_w = 100
    cam.roi_h = 100
    cam.roi_off_x = 0
    cam.roi_off_y = 0
    
    # Center of 640x480 is 320x240
    # ROI should be 270,190 to 370,290
    x1, y1, x2, y2 = cam.get_roi_rect(640, 480)
    assert x1 == 270
    assert y1 == 190
    assert x2 == 370
    assert y2 == 290
    
    # Edge case: image smaller than ROI
    x1, y1, x2, y2 = cam.get_roi_rect(50, 50)
    assert x1 == 0
    assert y1 == 0

def test_camera_open_failure(mock_cv2):
    """Vérifie le comportement si aucune caméra n'est trouvée."""
    # On configure le mock pour que isOpened renvoie toujours False
    mock_cv2.VideoCapture.return_value.isOpened.return_value = False
    
    cam = CameraEngine(0)
    assert cam.cap is not None
    assert not cam.is_ready()

def test_grab_and_detect_contours(mock_cv2):
    """Vérifie la logique de filtrage des contours."""
    cam = CameraEngine(0)
    
    # On simule un contour carré (bruit)
    cnt = np.array([[[0,0]], [[0,10]], [[10,10]], [[10,0]]], dtype=np.int32)
    mock_cv2.findContours.return_value = ([cnt], None)
    
    # Cas 1: Trop petit (Area < 50)
    mock_cv2.contourArea.return_value = 10.0
    _, data = cam.grab_and_detect()
    assert data is None
    
    # Cas 2: Bon contour (Area > 50, Circulaire)
    mock_cv2.contourArea.return_value = 1000.0
    mock_cv2.arcLength.return_value = 100.0
    mock_cv2.minEnclosingCircle.return_value = ((50,50), 20.0)
    _, data = cam.grab_and_detect()
    assert data is not None

def test_camera_backend_fallback(mock_cv2):
    """Vérifie que le moteur essaie plusieurs backends en cas d'échec."""
    # Mock VideoCapture pour échouer au 1er appel, réussir au 2ème
    mock_cap_fail = MagicMock()
    mock_cap_fail.isOpened.return_value = False
    
    mock_cap_ok = MagicMock()
    mock_cap_ok.isOpened.return_value = True
    
    # side_effect permet de retourner des valeurs différentes à chaque appel
    mock_cv2.VideoCapture.side_effect = [mock_cap_fail, mock_cap_ok, mock_cap_fail]
    
    cam = CameraEngine(0)
    assert cam.is_ready()
    # Doit avoir appelé VideoCapture au moins 2 fois
    assert mock_cv2.VideoCapture.call_count >= 2

def test_camera_release(mock_cv2):
    """Vérifie la libération des ressources."""
    cam = CameraEngine(0)
    cam.release()
    cam.cap.release.assert_called()

def test_camera_config_loading():
    """Vérifie le chargement de la configuration."""
    with patch("camera_engine.cv2"), \
         patch("camera_engine.ConfigManager") as MockConf:
        MockConf.return_value.config = {"detection": {"canny_threshold1": 99}}
        cam = CameraEngine(0)
        assert cam.threshold_val == 99

def test_grab_exception(mock_cv2):
    """Vérifie la robustesse en cas d'erreur de lecture."""
    cam = CameraEngine(0)
    # Force read to raise exception
    cam.cap.read.side_effect = Exception("Boom")
    frame, data = cam.grab_and_detect()
    assert frame is None
    assert data is None

def test_open_camera_loop(mock_cv2):
    """Vérifie la boucle d'ouverture de caméra (DSHOW, MSMF...)."""
    # On veut que le 1er backend échoue, le 2eme réussisse
    cap_fail = MagicMock()
    cap_fail.isOpened.return_value = False
    cap_ok = MagicMock()
    cap_ok.isOpened.return_value = True
    
    mock_cv2.VideoCapture.side_effect = [cap_fail, cap_ok]
    
    cam = CameraEngine(0)
    assert cam.is_ready()
    assert mock_cv2.VideoCapture.call_count == 2

def test_grayscale_input(mock_cv2):
    """Vérifie le support des caméras monochromes (input 2D)."""
    cam = CameraEngine(0)
    
    # Simulation d'une frame en niveaux de gris (2D array)
    gray_frame = np.zeros((480, 640), dtype=np.uint8)
    mock_cv2.VideoCapture.return_value.read.return_value = (True, gray_frame)
    
    # On doit mocker cvtColor pour qu'il retourne du BGR (3 canaux) quand on lui donne du Gris
    # Sinon le code plantera plus loin quand il essaiera de dessiner en couleur
    def side_effect_cvtColor(src, code):
        return np.zeros((src.shape[0], src.shape[1], 3), dtype=np.uint8)
    
    mock_cv2.cvtColor.side_effect = side_effect_cvtColor
    
    frame, data = cam.grab_and_detect()
    assert frame is not None
    assert frame.shape[2] == 3 # Doit avoir été converti en BGR