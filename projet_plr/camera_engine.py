"""
camera_engine.py
================
Moteur de capture ROBUSTE V5.0 (Support caméra USB3 Vision via IC4 + fallback OpenCV).
"""

import cv2
import numpy as np
import time
import os
import logging
from typing import Optional, Tuple, Dict, Any
from settings_dialog import ConfigManager

logger = logging.getLogger(__name__)

# --- Backend IC4 (The Imaging Source USB3 Vision) ---
_IC4_AVAILABLE = False
try:
    # S'assurer que le GenTL path est défini (nécessaire si lancé depuis un shell sans héritage)
    _gentl_path = os.environ.get("GENICAM_GENTL64_PATH", "")
    _tis_base = r"C:\Program Files\The Imaging Source Europe GmbH"
    if os.path.isdir(_tis_base):
        for _d in os.listdir(_tis_base):
            _cti_dir = os.path.join(_tis_base, _d, "bin")
            if os.path.isdir(_cti_dir) and _cti_dir not in _gentl_path:
                _gentl_path = (_gentl_path + ";" + _cti_dir) if _gentl_path else _cti_dir
        os.environ["GENICAM_GENTL64_PATH"] = _gentl_path

    import imagingcontrol4 as ic4
    _IC4_AVAILABLE = True
except ImportError:
    pass

class CameraEngine:
    """
    Moteur de capture vidéo et de traitement d'image pour la pupillométrie.
    
    Gère l'acquisition caméra, le prétraitement (ROI, flou, seuillage),
    la détection de contours et l'enregistrement des données.
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.config_manager = ConfigManager()
        self.fps = 0.0
        self.last_time = time.time()

        # Backend IC4 (The Imaging Source USB3 Vision)
        self._use_ic4 = False
        self._ic4_grabber = None
        self._ic4_sink = None

        # Params Détection
        self.threshold_val = 50
        self.blur_val = 5
        self.display_mode = 'normal'
        self.mm_per_pixel = 0.05

        # Params ROI
        self.roi_w = 400
        self.roi_h = 400
        self.roi_off_x = 0
        self.roi_off_y = 0

        # --- INITIALISATION CRITIQUE ---
        self.csv_file = None
        self.video_writer = None
        self.recording = False
        self.start_time = 0.0
        self.last_valid_diameter = 0.0
        self.record_skip = 1
        self._record_counter = 0
        self._frame_width = 640
        self._frame_height = 480
        # -------------------------------------------------------

        self.open_camera()
        self.load_config()

    def open_camera(self):
        """Tente d'ouvrir la caméra : IC4 (USB3 Vision) puis fallback OpenCV."""
        print(f"[CAMERA] Ouverture index {self.camera_index}...")

        # --- 1. Tentative IC4 (The Imaging Source USB3 Vision) ---
        if _IC4_AVAILABLE:
            try:
                ic4.Library.init()
                devs = ic4.DeviceEnum.devices()
                if len(devs) > 0:
                    dev = devs[min(self.camera_index, len(devs) - 1)]
                    self._ic4_grabber = ic4.Grabber()
                    self._ic4_grabber.device_open(dev)
                    self._ic4_sink = ic4.SnapSink()
                    self._ic4_grabber.stream_setup(self._ic4_sink)

                    m = self._ic4_grabber.device_property_map
                    self._frame_width = m.get_value_int(ic4.PropId.WIDTH)
                    self._frame_height = m.get_value_int(ic4.PropId.HEIGHT)
                    try:
                        rf = m.get_value_float(ic4.PropId.ACQUISITION_FRAME_RATE)
                    except Exception:
                        rf = 15.0

                    self._use_ic4 = True
                    print(f"[CAMERA] IC4 : {dev.model_name} ({dev.serial})")
                    print(f"[CAMERA] Resolution : {self._frame_width}x{self._frame_height} @ {rf:.0f}fps")
                    return
                else:
                    print("[CAMERA] IC4 : aucune camera USB3 Vision detectee.")
            except Exception as e:
                print(f"[CAMERA] IC4 : echec ({e})")

        # --- 2. Fallback OpenCV (webcams UVC classiques) ---
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        backend_names = ["DSHOW", "MSMF", "ANY"]

        for backend, name in zip(backends, backend_names):
            self.cap = cv2.VideoCapture(self.camera_index, backend)
            if self.cap.isOpened():
                print(f"[CAMERA] OpenCV : connecte via {name}")
                break
            print(f"[CAMERA] OpenCV : echec {name}...")

        if not self.cap or not self.cap.isOpened():
            print(f"[CAMERA] ERREUR FATALE : Aucune camera trouvee.")
            return

        try:
            cam_conf = self.config_manager.config.get("camera", {})
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_conf.get("width", 640))
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_conf.get("height", 480))

            target_fps = cam_conf.get("target_fps", 0)
            if target_fps > 0:
                self.cap.set(cv2.CAP_PROP_FPS, target_fps)

            try:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self.cap.set(cv2.CAP_PROP_EXPOSURE, cam_conf.get("exposure", -5))
            except: pass

            self._frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            rf = self.cap.get(cv2.CAP_PROP_FPS)
            print(f"[CAMERA] Resolution : {self._frame_width}x{self._frame_height} @ {rf:.0f}fps")
        except Exception as e:
            print(f"[CAMERA] Erreur config : {e}")

    def load_config(self):
        """Charge les paramètres de détection depuis le ConfigManager."""
        det = self.config_manager.config.get("detection", {})
        self.threshold_val = int(det.get("canny_threshold1", 50))
        self.blur_val = int(det.get("gaussian_blur", 5))
        self.roi_w = int(det.get("roi_width", 400))
        self.roi_h = int(det.get("roi_height", 400))
        self.roi_off_x = int(det.get("roi_offset_x", 0))
        self.roi_off_y = int(det.get("roi_offset_y", 0))

    def release(self):
        """Libère les ressources (caméra et fichier CSV)."""
        self.stop_recording()
        if self._use_ic4:
            try:
                if self._ic4_grabber:
                    self._ic4_grabber.stream_stop()
                    self._ic4_grabber.device_close()
            except Exception:
                pass
            self._ic4_grabber = None
            self._ic4_sink = None
            self._use_ic4 = False
        if self.cap:
            self.cap.release()

    def is_ready(self) -> bool:
        """Vérifie si la caméra est ouverte et prête."""
        if self._use_ic4:
            return self._ic4_grabber is not None and self._ic4_sink is not None
        return self.cap is not None and self.cap.isOpened()

    def set_threshold(self, val: int):
        """Définit le seuil de binarisation."""
        self.threshold_val = val

    def set_blur_kernel(self, val: int):
        """Définit la taille du noyau de flou (doit être impair)."""
        self.blur_val = val if val % 2 != 0 else val + 1

    def set_display_mode(self, mode: str):
        """Change le mode d'affichage ('normal', 'roi', 'binary', 'mosaic')."""
        self.display_mode = mode

    def set_fps_target(self, fps: int):
        """Mémorise le FPS cible dans la config (sera appliqué au prochain open_camera)."""
        self.config_manager.config.setdefault("camera", {})["target_fps"] = fps

    def start_recording(self, base_path: str):
        """Démarre l'enregistrement CSV + VIDÉO AVI."""
        try:
            self.stop_recording()

            # 1. CSV
            self.csv_file = open(base_path + ".csv", 'w')
            self.csv_file.write("timestamp_s,diameter_mm,quality_score,brightness\n")

            # 2. VIDÉO AVI
            w = self._frame_width
            h = self._frame_height
            if w > 0 and h > 0:
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                self.video_writer = cv2.VideoWriter(base_path + ".avi", fourcc, 30.0, (w, h))
                if not self.video_writer.isOpened():
                    self.video_writer = None
                    print("[REC] Avertissement : impossible d'ouvrir le VideoWriter AVI.")

            self._record_counter = 0
            self.start_time = time.time()
            self.recording = True
        except Exception as e:
            print(f"[REC] Erreur : {e}")
            self.recording = False

    def stop_recording(self):
        """Arrête l'enregistrement CSV, vidéo AVI et ferme les fichiers."""
        self.recording = False
        time.sleep(0.02)

        # --- PROTECTION CONTRE L'ERREUR 'NO ATTRIBUTE' ---
        if hasattr(self, 'csv_file') and self.csv_file:
            try:
                if not self.csv_file.closed:
                    self.csv_file.close()
            except: pass
            self.csv_file = None

        if hasattr(self, 'video_writer') and self.video_writer:
            try:
                self.video_writer.release()
            except: pass
            self.video_writer = None

    def get_roi_rect(self, w: int, h: int) -> Tuple[int, int, int, int]:
        """
        Calcule les coordonnées du rectangle de la ROI (Region of Interest).

        Args:
            w (int): Largeur totale de l'image.
            h (int): Hauteur totale de l'image.
        Returns:
            Tuple[int, int, int, int]: (x1, y1, x2, y2)
        """
        if w == 0 or h == 0: return 0,0,0,0
        cx = (w // 2) + self.roi_off_x
        cy = (h // 2) + self.roi_off_y
        hw, hh = self.roi_w // 2, self.roi_h // 2
        x1, y1 = max(0, int(cx - hw)), max(0, int(cy - hh))
        x2, y2 = min(w, int(cx + hw)), min(h, int(cy + hh))
        return x1, y1, x2, y2

    def grab_and_detect(self) -> Tuple[Optional[np.ndarray], Optional[Dict[str, Any]]]:
        """
        Capture une frame, applique le traitement d'image et détecte la pupille.

        Returns:
            Tuple[Optional[np.ndarray], Optional[Dict[str, Any]]]:
                - L'image traitée pour affichage (BGR).
                - Un dictionnaire contenant les données de la pupille (ou None).
        """
        if not self.is_ready(): return None, None

        try:
            if self._use_ic4:
                frame_buf = self._ic4_sink.snap_single(1000)
                if frame_buf is None: return None, None
                raw_frame = frame_buf.numpy_copy()
                if raw_frame.ndim == 3 and raw_frame.shape[2] == 1:
                    raw_frame = raw_frame[:, :, 0]  # (H, W, 1) → (H, W) mono
            else:
                ret, raw_frame = self.cap.read()
                if not ret: return None, None
        except Exception:
            return None, None
        
        now = time.time()
        if (now - self.last_time) > 0:
            instant = 1.0 / (now - self.last_time)
            self.fps = instant if self.fps == 0.0 else (0.8 * self.fps + 0.2 * instant)
        self.last_time = now
        
        try:
            # 1. PRÉPARATION IMAGES
            if len(raw_frame.shape) == 2 or raw_frame.shape[2] == 1:
                vis_frame = cv2.cvtColor(raw_frame, cv2.COLOR_GRAY2BGR)
                gray_frame = raw_frame
            else:
                vis_frame = raw_frame.copy()
                gray_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)

            # --- DETECTION BLACK FRAME (SYNCHRO) ---
            avg_brightness = np.mean(gray_frame)
            is_black_frame = avg_brightness < 10.0 # Seuil de détection du "trou noir" (Black Frame hardware)

            # 2. ROI CROP
            h, w = vis_frame.shape[:2]
            x1, y1, x2, y2 = self.get_roi_rect(w, h)
            
            if (x2 - x1) < 10 or (y2 - y1) < 10:
                roi_gray = gray_frame
                roi_vis = vis_frame
                x1, y1, x2, y2 = 0, 0, w, h
            else:
                roi_gray = gray_frame[y1:y2, x1:x2]
                roi_vis = vis_frame[y1:y2, x1:x2]

            pupil_data = None

            if is_black_frame:
                # ROBUSTESSE : Si frame noire, on ne détecte pas, on garde la dernière valeur
                pupil_data = {
                    'timestamp': time.time(),
                    'diameter_px': 0,
                    'diameter_mm': np.nan, # Marqueur pour interpolation ultérieure
                    'quality_score': 0,
                    'brightness': avg_brightness
                }
                # Pas de dessin sur frame noire
            else:
                # 3. DÉTECTION NORMALE
                blurred = cv2.GaussianBlur(roi_gray, (self.blur_val, self.blur_val), 0)
                _, binary = cv2.threshold(blurred, self.threshold_val, 255, cv2.THRESH_BINARY_INV)
                
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                max_area = 0
                best_cnt = None
                
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area < 50: continue
                    perim = cv2.arcLength(cnt, True)
                    if perim == 0: continue
                    circ = 4 * np.pi * (area / (perim**2))
                    if circ > 0.5 and area > max_area:
                        max_area = area
                        best_cnt = cnt
                
                # 4. RÉSULTATS & DESSIN
                if best_cnt is not None:
                    (cx, cy), radius = cv2.minEnclosingCircle(best_cnt)
                    center = (int(cx), int(cy))
                    # On garde la précision (3 décimales) pour éviter l'effet "escalier"
                    diameter_mm = round((radius * 2) * self.mm_per_pixel, 3)
                    self.last_valid_diameter = diameter_mm # Mise à jour valeur valide
                    
                    pupil_data = {
                        'timestamp': time.time(),
                        'diameter_px': radius * 2,
                        'diameter_mm': diameter_mm,
                        'quality_score': 100,
                        'brightness': avg_brightness
                    }
                    
                    cv2.circle(roi_vis, center, int(radius), (0, 255, 0), 2)
                    cv2.circle(roi_vis, center, 2, (0, 0, 255), 3)
                    
                    # OSD (Texte Diamètre)
                    text = f"{diameter_mm:.1f} mm"
                    txt_pos = (center[0] - 40, center[1] - int(radius) - 10)
                    cv2.putText(roi_vis, text, txt_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
                    cv2.putText(roi_vis, text, txt_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # ENREGISTREMENT
            if self.recording:
                self._record_counter += 1
                if self._record_counter % self.record_skip == 0:
                    # CSV
                    if pupil_data and hasattr(self, 'csv_file') and self.csv_file and not self.csv_file.closed:
                        try:
                            t_rel = time.time() - self.start_time
                            self.csv_file.write(f"{t_rel:.3f},{pupil_data['diameter_mm']:.3f},{pupil_data['quality_score']},{avg_brightness:.1f}\n")
                        except: pass
                    # VIDÉO AVI
                    if hasattr(self, 'video_writer') and self.video_writer:
                        try:
                            self.video_writer.write(vis_frame)
                        except: pass

            # 5. RECONSTRUCTION
            cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            vis_frame[y1:y2, x1:x2] = roi_vis
            
            if self.display_mode == 'binary':
                bin_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                return bin_bgr, pupil_data
            elif self.display_mode == 'roi':
                return roi_vis, pupil_data
            elif self.display_mode == 'mosaic':
                h_out, w_out = vis_frame.shape[:2]
                half_w, half_h = w_out // 2, h_out // 2
                mosaic = np.zeros((h_out, w_out, 3), dtype=np.uint8)
                
                small_global = cv2.resize(vis_frame, (half_w, half_h))
                small_roi = cv2.resize(roi_vis, (half_w, half_h))
                bin_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                small_bin = cv2.resize(bin_bgr, (half_w, half_h))
                
                mosaic[0:half_h, 0:half_w] = small_global
                mosaic[0:half_h, half_w:half_w*2] = small_roi
                mosaic[half_h:half_h*2, 0:half_w] = small_bin
                
                return mosaic, pupil_data
                
            return vis_frame, pupil_data

        except Exception as e:
            if len(raw_frame.shape) == 2:
                return cv2.cvtColor(raw_frame, cv2.COLOR_GRAY2BGR), None
            return raw_frame, None