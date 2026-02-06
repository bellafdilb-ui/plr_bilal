"""
acquisition_camera_IR.py
DÉTECTION PUPILLAIRE IR - Avec calibration mm + contrôle temps réel
Version 4.1 avec conversion pixels → millimètres
"""

import cv2
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from collections import deque
import csv


def px_to_mm(diameter_px, ratio_mm_per_px):
    """Convertit pixels en millimètres"""
    if ratio_mm_per_px is None:
        return None
    return diameter_px * ratio_mm_per_px


class PupilDetectorIR:
    """Détecteur de pupille optimisé pour caméra IR"""
    
    def __init__(self, camera_id=0):
        """Initialisation du détecteur"""
        
        print("🔬 Initialisation PupilDetectorIR v4.1")
        
        # Chemins
        self.project_root = Path(__file__).parent
        self.config_file = self.project_root / "shared_params.json"
        self.calibration_file = self.project_root / "calibration_data.json"
        self.data_folder = self.project_root / "data"
        self.data_folder.mkdir(exist_ok=True)
        
        # Caméra
        self.camera_id = camera_id
        self.cap = None
        
        
        # Paramètres par défaut
        self.exposure = -6.0
        self.brightness = 128
        self.contrast = 32
        self.blur_kernel = 5
        self.threshold_value = 50
        self.morph_kernel = 3
        self.morph_iterations = 1
        self.min_area = 300
        self.max_area = 5000
        self.min_circularity = 0.7
        self.roi_x = 200
        self.roi_y = 150
        self.roi_width = 240
        self.roi_height = 180
        self.view_mode = 1
        self.ratio_mm_per_px = self.load_calibration()  # ✅ Charge au démarrage

        # Affiche l'état
        if self.ratio_mm_per_px:
            print(f"📏 Calibration chargée : {self.ratio_mm_per_px:.4f} mm/px")
        else:
            print("⚠️ Calibration non disponible (mode pixels uniquement)")


        
        # État
        self.recording = False
        self.shutdown = False  # Flag pour arrêt depuis parameter_controller
        self.csv_file = None
        self.csv_writer = None
        
        # Performance
        self.fps_buffer = deque(maxlen=30)
        self.last_params_check = datetime.now()
        
        # Charger paramètres
        self.load_parameters()
        
        # Initialiser caméra
        self.init_camera()
        
        print("✅ Détecteur initialisé")
    
    
    def load_parameters(self):
        """Charge les paramètres depuis JSON"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    params = data.get("params", {})
                    
                    self.exposure = params.get("exposure", self.exposure)
                    self.brightness = params.get("brightness", self.brightness)
                    self.contrast = params.get("contrast", self.contrast)
                    self.blur_kernel = params.get("blur_kernel", self.blur_kernel)
                    self.threshold_value = params.get("threshold_value", self.threshold_value)
                    self.morph_kernel = params.get("morph_kernel", self.morph_kernel)
                    self.morph_iterations = params.get("morph_iterations", self.morph_iterations)
                    self.min_area = params.get("min_area", self.min_area)
                    self.max_area = params.get("max_area", self.max_area)
                    self.min_circularity = params.get("min_circularity", self.min_circularity)
                    self.roi_x = params.get("roi_x", self.roi_x)
                    self.roi_y = params.get("roi_y", self.roi_y)
                    self.roi_width = params.get("roi_width", self.roi_width)
                    self.roi_height = params.get("roi_height", self.roi_height)
                    self.recording = params.get("recording", self.recording)
                    self.view_mode = params.get("view_mode", self.view_mode)
                    self.shutdown = params.get("shutdown", self.shutdown)
                    self.ratio_mm_per_px = params.get("ratio_mm_per_px", self.ratio_mm_per_px)
                    
                    # ✅ AJOUT : Rechargement dynamique calibration
                    new_ratio = self.load_calibration()
                    if new_ratio != self.ratio_mm_per_px:
                        self.ratio_mm_per_px = new_ratio
                        if new_ratio is not None:
                            print(f"🔄 Calibration mise à jour : {new_ratio:.4f} mm/px")
                        else:
                            print("⚠️ Calibration désactivée")


                    # Mise à jour exposition caméra si changée
                    # Mise à jour paramètres caméra si changés
                    if self.cap is not None:
                        current_exposure = self.cap.get(cv2.CAP_PROP_EXPOSURE)
                        if abs(current_exposure - self.exposure) > 0.1:
                            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
                        
                        current_brightness = self.cap.get(cv2.CAP_PROP_BRIGHTNESS)
                        if abs(current_brightness - self.brightness) > 1:
                            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, self.brightness)
                        
                        current_contrast = self.cap.get(cv2.CAP_PROP_CONTRAST)
                        if abs(current_contrast - self.contrast) > 1:
                            self.cap.set(cv2.CAP_PROP_CONTRAST, self.contrast)

                    
        except Exception as e:
            print(f"⚠️ Erreur chargement paramètres : {e}")
    
    def load_calibration(self):
        """
        Charge le ratio de calibration depuis calibration_data.json
        Returns:
            float ou None: ratio mm/px ou None si pas de calibration
        """
        try:
            if self.calibration_file.exists():
                with open(self.calibration_file, 'r') as f:
                    data = json.load(f)
                    ratio = data.get("ratio_mm_per_px")
                    
                    if ratio is not None and ratio > 0:
                        return float(ratio)
                    else:
                        return None
            else:
                return None
                
        except Exception as e:
            print(f"⚠️ Erreur chargement calibration : {e}")
            return None
    
    
    def init_camera(self):
        """Initialise la caméra"""
        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"❌ Impossible d'ouvrir la caméra {self.camera_id}")
        
        # Configuration
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, self.brightness)
        self.cap.set(cv2.CAP_PROP_CONTRAST, self.contrast)

        
        print(f"✅ Caméra {self.camera_id} initialisée")
    
    
    def detect_pupil(self, roi):
        """Détecte la pupille dans la ROI"""
        
        # 1. Prétraitement
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        
        # Flou pour réduire bruit
        ksize = self.blur_kernel if self.blur_kernel % 2 == 1 else self.blur_kernel + 1
        blurred = cv2.GaussianBlur(gray, (ksize, ksize), 0)
        
        # 2. Seuillage
        _, binary = cv2.threshold(blurred, self.threshold_value, 255, cv2.THRESH_BINARY_INV)
        
        # 3. Morphologie
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                          (self.morph_kernel, self.morph_kernel))
        morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, 
                                   iterations=self.morph_iterations)
        morphed = cv2.morphologyEx(morphed, cv2.MORPH_OPEN, kernel, 
                                  iterations=self.morph_iterations)
        
        # 4. Détection contours
        contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None, None, None, None, 0.0
        
        # 5. Filtrage
        best_contour = None
        best_score = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filtre aire
            if not (self.min_area <= area <= self.max_area):
                continue
            
            # Circularité
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * np.pi * area / (perimeter ** 2)
            
            if circularity < self.min_circularity:
                continue
            
            # Score combiné
            score = circularity * (area / self.max_area)
            
            if score > best_score:
                best_score = score
                best_contour = contour
        
        # 6. Ajustement ellipse + Confidence Score
        if best_contour is not None and len(best_contour) >= 5:
            try:
                ellipse = cv2.fitEllipse(best_contour)
                (center_x, center_y), (width, height), angle = ellipse

                diameter = (width + height) / 2
                diameter_mm = px_to_mm(diameter, self.ratio_mm_per_px)

                # ═══════════════════════════════════════════════════
                # CALCUL CONFIDENCE SCORE AMÉLIORÉ (0-100%)
                # ═══════════════════════════════════════════════════
                confidence = 0.0
                
                # ─── Composante 1 : Circularité (40%) ───
                perimeter = cv2.arcLength(best_contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * cv2.contourArea(best_contour) / (perimeter ** 2)
                    confidence += min(circularity, 1.0) * 40
                
                # ─── Composante 2 : Contraste iris/pupille (30%) ───
                try:
                    # Masque de la pupille
                    mask_pupil = np.zeros(gray.shape, dtype=np.uint8)
                    cv2.drawContours(mask_pupil, [best_contour], -1, 255, -1)
                    
                    # Intensité moyenne pupille
                    pupil_mean = cv2.mean(gray, mask=mask_pupil)[0]
                    
                    # Masque de l'iris (anneau autour de la pupille)
                    kernel = np.ones((15, 15), np.uint8)
                    mask_dilated = cv2.dilate(mask_pupil, kernel, iterations=2)
                    mask_iris = cv2.subtract(mask_dilated, mask_pupil)
                    iris_mean = cv2.mean(gray, mask=mask_iris)[0]
                    
                    # Score de contraste (plus le contraste est fort, mieux c'est)
                    if iris_mean > 0 and pupil_mean < iris_mean:
                        contrast_ratio = (iris_mean - pupil_mean) / iris_mean
                        confidence += min(contrast_ratio, 1.0) * 30
                    
                except Exception:
                    pass  # Si erreur, on ignore cette composante
                
                # ─── Composante 3 : Taille réaliste (20%) ───
                # Pupille humaine typique : 2-8mm → 40-160px à 0.05mm/px
                radius = diameter / 2
                if 30 < radius < 200:
                    confidence += 20
                elif 20 < radius < 250:
                    confidence += 10  # Acceptable mais limite
                
                # ─── Composante 4 : Uniformité interne (10%) ───
                try:
                    pupil_pixels = gray[mask_pupil == 255]
                    if len(pupil_pixels) > 10:  # Suffisamment de pixels
                        std_dev = np.std(pupil_pixels)
                        # Faible écart-type = bonne uniformité
                        uniformity = max(0, 1 - std_dev / 50)
                        confidence += uniformity * 10
                except Exception:
                    pass
                
                # ─── Score final (plafonné à 100%) ───
                confidence = min(confidence, 100.0)
                
                # ═══════════════════════════════════════════════════
                # RETOUR
                # ═══════════════════════════════════════════════════
                return center_x, center_y, diameter, diameter_mm, confidence

            except cv2.error as e:
                if self.debug_mode:
                    print(f"⚠️ Erreur fitEllipse : {e}")
                pass

        # Aucune détection valide
        return None, None, None, None, 0.0

    
    def calculate_confidence_score(self, contour, frame_gray):
        """
        Calcule le score de confiance de la détection (0-100%)
        
        Args:
            contour: Contour détecté de la pupille
            frame_gray: Image en niveaux de gris
            
        Returns:
            float: Score de confiance (0-100)
        """
        try:
            score = 0.0
            weights = []
            
            # ══════════════════════════════════════════════════════
            # CRITÈRE 1 : CIRCULARITÉ (40% du score)
            # ══════════════════════════════════════════════════════
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)
                # Score max si circularité = 1.0 (cercle parfait)
                circularity_score = min(circularity, 1.0) * 40
                score += circularity_score
                weights.append(("Circularité", circularity_score, 40))
            
            # ══════════════════════════════════════════════════════
            # CRITÈRE 2 : CONTRASTE IRIS/PUPILLE (30% du score)
            # ══════════════════════════════════════════════════════
            mask = np.zeros(frame_gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            
            # Intensité moyenne dans la pupille
            pupil_mean = cv2.mean(frame_gray, mask=mask)[0]
            
            # Intensité moyenne dans l'iris (anneau autour pupille)
            kernel = np.ones((15, 15), np.uint8)
            dilated_mask = cv2.dilate(mask, kernel, iterations=2)
            iris_mask = cv2.subtract(dilated_mask, mask)
            iris_mean = cv2.mean(frame_gray, mask=iris_mask)[0]
            
            if iris_mean > 0:
                contrast = abs(iris_mean - pupil_mean) / iris_mean
                contrast_score = min(contrast, 1.0) * 30
                score += contrast_score
                weights.append(("Contraste", contrast_score, 30))
            
            # ══════════════════════════════════════════════════════
            # CRITÈRE 3 : TAILLE RAISONNABLE (20% du score)
            # ══════════════════════════════════════════════════════
            # Pupille humaine : 2-8mm → environ 40-160 px à 0.05mm/px
            (x, y), radius = cv2.minEnclosingCircle(contour)
            
            if 30 < radius < 200:  # Plage réaliste en pixels
                size_score = 20
            elif 20 < radius < 250:
                size_score = 10  # Taille limite acceptable
            else:
                size_score = 0  # Taille aberrante
                
            score += size_score
            weights.append(("Taille", size_score, 20))
            
            # ══════════════════════════════════════════════════════
            # CRITÈRE 4 : UNIFORMITÉ INTERNE (10% du score)
            # ══════════════════════════════════════════════════════
            pupil_pixels = frame_gray[mask == 255]
            if len(pupil_pixels) > 0:
                std_dev = np.std(pupil_pixels)
                # Faible écart-type = pupille uniforme
                uniformity = max(0, 1 - std_dev / 50)  # Normalisation
                uniformity_score = uniformity * 10
                score += uniformity_score
                weights.append(("Uniformité", uniformity_score, 10))
            
            # ══════════════════════════════════════════════════════
            # SCORE FINAL
            # ══════════════════════════════════════════════════════
            final_score = min(score, 100.0)  # Plafonnement à 100%
            
            # Log détaillé (debug)
            if self.debug_mode:
                print(f"\n📊 Détail Confidence Score : {final_score:.1f}%")
                for name, value, max_val in weights:
                    print(f"   {name}: {value:.1f}/{max_val}")
            
            return final_score
            
        except Exception as e:
            print(f"⚠️ Erreur calcul confidence : {e}")
            return 0.0
    

    def start_recording(self):
        """Démarre l'enregistrement CSV"""
        if self.csv_file is not None:
            return  # Déjà en cours
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = self.data_folder / f"pupil_data_{timestamp}.csv"
        
        self.csv_file = open(csv_path, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['timestamp', 'frame', 'center_x', 'center_y', 
                                  'diameter_px', 'diameter_mm', 'confidence', 'fps'])
        
        print(f"🔴 Enregistrement démarré : {csv_path.name}")
    
    
    def stop_recording(self):
        """Arrête l'enregistrement CSV"""
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
            print("⏹️ Enregistrement arrêté")
    
    
    def run(self):
        """Boucle principale de détection"""
        
        print("\n" + "="*60)
        print("🎬 ACQUISITION DÉMARRÉE")
        print("="*60)
        print("Commandes :")
        print("  [ESPACE] Activer/désactiver enregistrement")
        print("  [1/2/3]  Changer mode affichage")
        print("  [Q/ESC]  Quitter")
        print("  Parameter Controller pour ajuster les paramètres")
        print("="*60 + "\n")
        
        frame_count = 0
        
        try:
            while True:
                # Timer FPS
                start_time = cv2.getTickCount()
                
                # Lecture caméra
                ret, frame = self.cap.read()
                if not ret:
                    print("⚠️ Erreur lecture caméra")
                    break
                
                frame_count += 1
                
                # Reload paramètres (toutes les 0.5s)
                now = datetime.now()
                if (now - self.last_params_check).total_seconds() > 0.5:
                    old_recording = self.recording
                    self.load_parameters()
                    self.last_params_check = now
                    
                    # Vérifier shutdown
                    if self.shutdown:
                        print("🛑 Arrêt demandé par Parameter Controller")
                        break
                    
                    # Gestion enregistrement
                    if self.recording and not old_recording:
                        self.start_recording()
                    elif not self.recording and old_recording:
                        self.stop_recording()
                
                # ROI
                h, w = frame.shape[:2]
                x1 = max(0, self.roi_x)
                y1 = max(0, self.roi_y)
                x2 = min(w, self.roi_x + self.roi_width)
                y2 = min(h, self.roi_y + self.roi_height)
                
                roi = frame[y1:y2, x1:x2]
                
                if roi.size == 0:
                    continue
                
                # Détection
                center_x, center_y, diameter, diameter_mm, confidence = self.detect_pupil(roi)
                
                # Sauvegarde CSV
                if self.recording and self.csv_writer and center_x is not None:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    abs_x = x1 + center_x
                    abs_y = y1 + center_y
                    
                    current_fps = self.fps_buffer[-1] if self.fps_buffer else 0
                    
                    self.csv_writer.writerow([
                        timestamp,
                        frame_count,
                        int(abs_x),
                        int(abs_y),
                        f"{diameter:.2f}",
                        f"{diameter_mm:.2f}" if diameter_mm else "N/A",
                        f"{confidence:.3f}",
                        f"{current_fps:.1f}"
                    ])
                
                # Affichage selon mode
                if self.view_mode == 1:
                    display = frame.copy()
                    cv2.rectangle(display, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    
                    if center_x is not None:
                        abs_x = int(x1 + center_x)
                        abs_y = int(y1 + center_y)
                        radius = int(diameter / 2)
                        cv2.circle(display, (abs_x, abs_y), radius, (0, 255, 0), 2)
                        cv2.circle(display, (abs_x, abs_y), 3, (0, 0, 255), -1)
                
                elif self.view_mode == 2:
                    display = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)
                    
                    if center_x is not None:
                        center = (int(center_x), int(center_y))
                        radius = int(diameter / 2)
                        cv2.circle(display, center, radius, (0, 255, 0), 2)
                        cv2.circle(display, center, 3, (0, 0, 255), -1)
                
                elif self.view_mode == 3:
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    ksize = self.blur_kernel if self.blur_kernel % 2 == 1 else self.blur_kernel + 1
                    blurred = cv2.GaussianBlur(gray, (ksize, ksize), 0)
                    _, binary = cv2.threshold(blurred, self.threshold_value, 255, cv2.THRESH_BINARY_INV)
                    display = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                
                # Texte overlay
                y_offset = 30
                
                if center_x is not None:
                    cv2.putText(display, f"Diam: {diameter:.1f}px", 
                               (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (0, 255, 0), 2)
                    y_offset += 25
                    
                    if diameter_mm is not None:
                        cv2.putText(display, f"Diam: {diameter_mm:.2f}mm", 
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 
                                   0.6, (0, 255, 0), 2)
                        y_offset += 25
                    else:
                        cv2.putText(display, "Diam: N/A (calibrer)", 
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 
                                   0.6, (255, 255, 0), 2)
                        y_offset += 25
                    
                    cv2.putText(display, f"Conf: {confidence:.2f}", 
                               (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (0, 255, 0), 2)
                    y_offset += 25
                else:
                    cv2.putText(display, "Aucune pupille", 
                               (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (0, 0, 255), 2)
                    y_offset += 25
                
                # FPS
                if self.fps_buffer:
                    avg_fps = sum(self.fps_buffer) / len(self.fps_buffer)
                    cv2.putText(display, f"FPS: {avg_fps:.1f}", 
                               (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (255, 255, 255), 2)
                    y_offset += 25
                
                # État enregistrement
                if self.recording:
                    cv2.circle(display, (display.shape[1]-30, 20), 10, (0, 0, 255), -1)
                    cv2.putText(display, "REC", 
                               (display.shape[1]-80, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (0, 0, 255), 2)
                
                # Mode vue
                mode_text = {1: "Full", 2: "ROI", 3: "Binary"}[self.view_mode]
                cv2.putText(display, f"Vue: {mode_text}", 
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.6, (255, 255, 255), 2)
                
                # Afficher
                cv2.imshow("Pupillometrie IR", display)
                
                # FPS calculation
                end_time = cv2.getTickCount()
                fps = cv2.getTickFrequency() / (end_time - start_time)
                self.fps_buffer.append(fps)
                
                # Gestion clavier
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q') or key == 27:
                    break
                
                elif key == ord(' '):
                    self.recording = not self.recording
                    
                    if self.recording:
                        self.start_recording()
                    else:
                        self.stop_recording()
                
                elif key == ord('1'):
                    self.view_mode = 1
                
                elif key == ord('2'):
                    self.view_mode = 2
                
                elif key == ord('3'):
                    self.view_mode = 3
        
        except KeyboardInterrupt:
            print("\n⚠️ Arrêt utilisateur")
        
        finally:
            # Stats
            print("\n" + "="*60)
            print("📊 STATISTIQUES FINALES")
            print(f"   Frames totales : {frame_count}")
            if self.fps_buffer:
                avg_fps = sum(self.fps_buffer) / len(self.fps_buffer)
                print(f"   FPS moyen      : {avg_fps:.1f}")
            print("="*60)
            
            # Nettoyage
            self.stop_recording()
            self.cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        detector = PupilDetectorIR(camera_id=0)
        detector.run()
    
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()
