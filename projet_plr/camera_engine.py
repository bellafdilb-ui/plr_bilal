"""
camera_engine.py
================
Moteur de capture ROBUSTE V4.1 (Fix: Crash Attribute Error 'csv_file').
"""

import cv2
import numpy as np
import time
import os
import logging
from typing import Optional, Tuple, Dict, Any
from settings_dialog import ConfigManager

logger = logging.getLogger(__name__)

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
        
        # --- INITIALISATION CRITIQUE (C'est ce qui manquait) ---
        self.csv_file = None
        self.video_writer = None
        self.recording = False
        self.start_time = 0.0
        self.last_valid_diameter = 0.0 # Pour la continuité lors de la Black Frame
        self.start_time = 0.0
        self.record_skip = 1       # 1 = 30fps, 2 = 15fps (une frame sur deux)
        self._record_counter = 0
        # -------------------------------------------------------
        
        self.open_camera()
        self.load_config()

    def open_camera(self):
        """Tente d'ouvrir la caméra avec différents backends (DSHOW, MSMF, ANY)."""
        print(f"[CAMERA] Ouverture index {self.camera_index}...")

        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        backend_names = ["DSHOW", "MSMF", "ANY"]

        for backend, name in zip(backends, backend_names):
            self.cap = cv2.VideoCapture(self.camera_index, backend)
            if self.cap.isOpened():
                print(f"[CAMERA] ✅ Connecté via {name}")
                break
            print(f"[CAMERA] ⚠️ Echec {name}...")

        if not self.cap.isOpened():
            print(f"[CAMERA] ❌ ERREUR FATALE : Aucune caméra trouvée.")
            return

        try:
            cam_conf = self.config_manager.config.get("camera", {})
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_conf.get("width", 640))
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_conf.get("height", 480))

            # FPS cible : doit être défini AU DÉMARRAGE (DSHOW ne supporte pas le changement à chaud)
            target_fps = cam_conf.get("target_fps", 0)
            if target_fps > 0:
                self.cap.set(cv2.CAP_PROP_FPS, target_fps)

            try:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self.cap.set(cv2.CAP_PROP_EXPOSURE, cam_conf.get("exposure", -5))
            except: pass

            rw = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            rh = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            rf = self.cap.get(cv2.CAP_PROP_FPS)
            print(f"[CAMERA] Résolution : {int(rw)}x{int(rh)} @ {rf:.0f}fps")
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
        if self.cap:
            self.cap.release()

    def is_ready(self) -> bool:
        """Vérifie si la caméra est ouverte et prête."""
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
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
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