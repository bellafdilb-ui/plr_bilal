"""
test_camera_engine.py
=====================
Tests du CameraEngine : init, détection pupillaire, ROI, enregistrement.
On mocke cv2 et IC4 pour ne pas dépendre du hardware.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock


@pytest.fixture
def cam():
    """Crée un CameraEngine avec OpenCV mocké (pas de caméra physique)."""
    with patch("camera_engine._IC4_AVAILABLE", False), \
         patch("camera_engine.cv2") as m_cv2, \
         patch("camera_engine.ConfigManager") as MockConf:

        # Config par défaut
        MockConf.return_value.config = {
            "camera": {"index": 0, "width": 640, "height": 480},
            "detection": {
                "canny_threshold1": 50, "gaussian_blur": 5,
                "roi_width": 400, "roi_height": 400,
                "roi_offset_x": 0, "roi_offset_y": 0
            }
        }

        # Mock VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640  # Pour CAP_PROP_FRAME_WIDTH etc.

        # Frame noire 640x480 BGR
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, dummy_frame)
        m_cv2.VideoCapture.return_value = mock_cap

        # Constantes OpenCV
        m_cv2.CAP_DSHOW = 700
        m_cv2.CAP_MSMF = 1400
        m_cv2.CAP_ANY = 0
        m_cv2.CAP_PROP_FRAME_WIDTH = 3
        m_cv2.CAP_PROP_FRAME_HEIGHT = 4
        m_cv2.CAP_PROP_FPS = 5
        m_cv2.CAP_PROP_AUTO_EXPOSURE = 21
        m_cv2.CAP_PROP_EXPOSURE = 15
        m_cv2.COLOR_BGR2GRAY = 6
        m_cv2.COLOR_GRAY2BGR = 8
        m_cv2.THRESH_BINARY_INV = 1
        m_cv2.RETR_EXTERNAL = 0
        m_cv2.CHAIN_APPROX_SIMPLE = 2
        m_cv2.FONT_HERSHEY_SIMPLEX = 0

        # Fonctions de traitement
        m_cv2.cvtColor.return_value = np.zeros((480, 640), dtype=np.uint8)
        m_cv2.GaussianBlur.return_value = np.zeros((480, 640), dtype=np.uint8)
        m_cv2.threshold.return_value = (0, np.zeros((480, 640), dtype=np.uint8))
        m_cv2.findContours.return_value = ([], None)
        m_cv2.rectangle = MagicMock()
        m_cv2.circle = MagicMock()
        m_cv2.putText = MagicMock()
        m_cv2.resize.side_effect = lambda img, sz: np.zeros((sz[1], sz[0], 3), dtype=np.uint8)

        from camera_engine import CameraEngine
        engine = CameraEngine(0)
        engine._cv2 = m_cv2  # Garder la ref pour les tests
        yield engine


# ─── Initialisation ──────────────────────────────────────────────────

class TestInit:
    def test_camera_ready(self, cam):
        assert cam.is_ready()

    def test_default_params(self, cam):
        assert cam.threshold_val == 50
        assert cam.blur_val == 5
        assert cam.display_mode == 'normal'

    def test_camera_not_ready_if_closed(self, cam):
        cam.cap.isOpened.return_value = False
        assert not cam.is_ready()


# ─── Setters ─────────────────────────────────────────────────────────

class TestSetters:
    def test_set_threshold(self, cam):
        cam.set_threshold(100)
        assert cam.threshold_val == 100

    def test_set_blur_odd(self, cam):
        cam.set_blur_kernel(7)
        assert cam.blur_val == 7

    def test_set_blur_even_rounds_up(self, cam):
        cam.set_blur_kernel(4)
        assert cam.blur_val == 5

    def test_set_display_mode(self, cam):
        cam.set_display_mode('binary')
        assert cam.display_mode == 'binary'


# ─── ROI ─────────────────────────────────────────────────────────────

class TestROI:
    def test_roi_centered(self, cam):
        cam.roi_w = 100
        cam.roi_h = 100
        cam.roi_off_x = 0
        cam.roi_off_y = 0
        x1, y1, x2, y2 = cam.get_roi_rect(640, 480)
        assert x1 == 270
        assert y1 == 190
        assert x2 == 370
        assert y2 == 290

    def test_roi_with_offset(self, cam):
        cam.roi_w = 100
        cam.roi_h = 100
        cam.roi_off_x = 50
        cam.roi_off_y = -20
        x1, y1, x2, y2 = cam.get_roi_rect(640, 480)
        assert x1 == 320
        assert y1 == 170

    def test_roi_clamped_to_image(self, cam):
        cam.roi_w = 1000
        cam.roi_h = 1000
        cam.roi_off_x = 0
        cam.roi_off_y = 0
        x1, y1, x2, y2 = cam.get_roi_rect(640, 480)
        assert x1 == 0
        assert y1 == 0
        assert x2 == 640
        assert y2 == 480

    def test_roi_zero_image(self, cam):
        x1, y1, x2, y2 = cam.get_roi_rect(0, 0)
        assert (x1, y1, x2, y2) == (0, 0, 0, 0)


# ─── Grab & Detect ──────────────────────────────────────────────────

class TestGrabAndDetect:
    def test_grab_returns_frame(self, cam):
        frame, data = cam.grab_and_detect()
        assert frame is not None

    def test_no_pupil_on_black_image(self, cam):
        """Image noire → pas de pupille détectée (contours vides)."""
        frame, data = cam.grab_and_detect()
        # Avec une image entièrement noire, soit black frame, soit pas de contours
        # Dans les deux cas, pas de pupille avec centre
        if data is not None:
            assert data.get('quality_score', 0) == 0

    def test_grab_failure(self, cam):
        cam.cap.read.return_value = (False, None)
        frame, data = cam.grab_and_detect()
        assert frame is None
        assert data is None

    def test_grab_exception(self, cam):
        cam.cap.read.side_effect = Exception("Boom")
        frame, data = cam.grab_and_detect()
        assert frame is None
        assert data is None

    def test_not_ready_returns_none(self, cam):
        cam.cap.isOpened.return_value = False
        frame, data = cam.grab_and_detect()
        assert frame is None
        assert data is None


# ─── Grayscale input (caméra mono) ──────────────────────────────────

class TestGrayscaleInput:
    def test_mono_frame_converted_to_bgr(self, cam):
        gray_frame = np.zeros((480, 640), dtype=np.uint8)
        cam.cap.read.return_value = (True, gray_frame)
        # cvtColor doit retourner une image BGR
        cam._cv2.cvtColor.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
        frame, data = cam.grab_and_detect()
        assert frame is not None


# ─── Enregistrement CSV/Vidéo ────────────────────────────────────────

class TestRecording:
    def test_start_stop_recording(self, cam, tmp_path):
        base = str(tmp_path / "rec")
        cam._cv2.VideoWriter.return_value = MagicMock(isOpened=MagicMock(return_value=True))
        cam._cv2.VideoWriter_fourcc.return_value = 0
        cam.start_recording(base)
        assert cam.recording is True
        cam.stop_recording()
        assert cam.recording is False

    def test_csv_file_created(self, cam, tmp_path):
        base = str(tmp_path / "rec")
        cam._cv2.VideoWriter.return_value = MagicMock(isOpened=MagicMock(return_value=True))
        cam._cv2.VideoWriter_fourcc.return_value = 0
        cam.start_recording(base)
        cam.stop_recording()
        csv_path = tmp_path / "rec.csv"
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "timestamp_s" in content

    def test_double_stop_no_crash(self, cam):
        cam.stop_recording()
        cam.stop_recording()  # Ne doit pas lever d'exception


# ─── Release ─────────────────────────────────────────────────────────

class TestRelease:
    def test_release_calls_cap_release(self, cam):
        cam.release()
        cam.cap.release.assert_called()

    def test_release_stops_recording(self, cam, tmp_path):
        base = str(tmp_path / "rec")
        cam._cv2.VideoWriter.return_value = MagicMock(isOpened=MagicMock(return_value=True))
        cam._cv2.VideoWriter_fourcc.return_value = 0
        cam.start_recording(base)
        cam.release()
        assert cam.recording is False
