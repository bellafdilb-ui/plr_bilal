"""
camera_engine.py
================
Moteur de capture ROBUSTE V4.1 (Fix: Crash Attribute Error 'csv_file').
"""

import cv2
import numpy as np
import time
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
        self.recording = False
        self.start_time = 0.0
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
            
            try:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self.cap.set(cv2.CAP_PROP_EXPOSURE, cam_conf.get("exposure", -5))
            except: pass
            
            rw = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            rh = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"[CAMERA] Résolution : {int(rw)}x{int(rh)}")
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
        self.stop_csv_recording()
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

    def start_csv_recording(self, filepath: str): 
        """Démarre l'enregistrement des données pupillométriques dans un CSV."""
        try:
            self.stop_csv_recording()
            self.csv_file = open(filepath, 'w')
            self.csv_file.write("timestamp_s,diameter_mm,quality_score\n")
            self.csv_file.flush()
            self.start_time = time.time()
            self.recording = True
        except Exception as e:
            print(f"[REC] Erreur : {e}")
            self.recording = False

    def stop_csv_recording(self):
        """Arrête l'enregistrement CSV et ferme le fichier."""
        self.recording = False
        time.sleep(0.02)
        
        # --- PROTECTION CONTRE L'ERREUR 'NO ATTRIBUTE' ---
        if hasattr(self, 'csv_file') and self.csv_file:
            try: 
                if not self.csv_file.closed:
                    self.csv_file.close()
            except: pass
            self.csv_file = None

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
        if (now - self.last_time) > 0: self.fps = 1.0 / (now - self.last_time)
        self.last_time = now
        
        try:
            # 1. PRÉPARATION IMAGES
            if len(raw_frame.shape) == 2 or raw_frame.shape[2] == 1:
                vis_frame = cv2.cvtColor(raw_frame, cv2.COLOR_GRAY2BGR)
                gray_frame = raw_frame
            else:
                vis_frame = raw_frame.copy()
                gray_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)

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

            # 3. DÉTECTION
            blurred = cv2.GaussianBlur(roi_gray, (self.blur_val, self.blur_val), 0)
            _, binary = cv2.threshold(blurred, self.threshold_val, 255, cv2.THRESH_BINARY_INV)
            
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            pupil_data = None
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
                diameter_mm = (radius * 2) * self.mm_per_pixel
                
                pupil_data = {
                    'timestamp': time.time(),
                    'diameter_px': radius * 2,
                    'diameter_mm': diameter_mm,
                    'quality_score': 100
                }
                
                # Écriture sécurisée
                if self.recording and hasattr(self, 'csv_file') and self.csv_file and not self.csv_file.closed:
                    try:
                        t_rel = time.time() - self.start_time
                        self.csv_file.write(f"{t_rel:.3f},{diameter_mm:.3f},100\n")
                    except: pass
                
                cv2.circle(roi_vis, center, int(radius), (0, 255, 0), 2)
                cv2.circle(roi_vis, center, 2, (0, 0, 255), 3)
                
                # OSD (Texte Diamètre)
                text = f"{diameter_mm:.2f} mm"
                txt_pos = (center[0] - 40, center[1] - int(radius) - 10)
                cv2.putText(roi_vis, text, txt_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
                cv2.putText(roi_vis, text, txt_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

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