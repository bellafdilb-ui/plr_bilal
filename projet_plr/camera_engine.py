"""
camera_engine.py
================
Moteur de capture et détection pupillaire en temps réel.

Modes d'affichage:
- 'normal': Vue RGB complète avec overlays
- 'roi': Zone ROI agrandie
- 'binary': Image binaire (seuillage)
- 'mosaic': 4 vues simultanées (2x2)

Recording mode:
- OFF par défaut (pas d'enregistrement CSV)
- ON uniquement pendant les tests PLR
"""

import cv2
import numpy as np
import time
import csv
import os
from datetime import datetime
from typing import Optional, Tuple, Dict

# ===========================
# CLASSE PRINCIPALE
# ===========================

class CameraEngine:
    """Gestion caméra + détection pupille + affichage multi-vues"""
    def __init__(self, camera_index=0, output_dir=None):
        """
        Initialisation du moteur caméra.

        Args:
            camera_index: Index de la caméra (0 par défaut)
        """
        # Caméra
        self.cap = cv2.VideoCapture(camera_index)

        if not self.cap.isOpened():
            print(f"⚠️ Warning: Caméra {camera_index} non disponible")

        # ✅ CORRECTION : Initialisation DANS __init__ (pas après is_ready)
        # Initialisation des paramètres (même si caméra non ouverte)
        self.blur_kernel = 5
        self.threshold_value = 50
        self.min_area = 100
        self.max_area = 50000
        self.circularity_threshold = 0.7

        # Paramètres caméra (valeurs par défaut)
        self.exposure = -6
        self.brightness = 128
        self.contrast = 32
        self.set_camera_params(self.exposure, self.brightness, self.contrast)

        # ROI (Region of Interest) - valeurs par défaut
        self.roi_x = 200
        self.roi_y = 150
        self.roi_w = 240
        self.roi_h = 180

        # Paramètres détection (note: redondance avec blur_kernel/threshold ci-dessus)
        # Si tu veux éviter la redondance, supprime les lignes 52-54 ou 87-91
        self.threshold_value = 50
        self.blur_kernel = 5
        self.min_area = 300
        self.max_area = 50000
        self.min_circularity = 0.6

        # Calibration (mm par pixel) - À AJUSTER selon votre setup
        self.mm_per_pixel = 0.05  # Exemple: 1 pixel = 0.05 mm

        # Mode d'affichage
        self.display_mode = 'normal'  # 'normal', 'roi', 'binary', 'mosaic'

        # Overlays
        self.show_ellipse = True
        self.show_diameter = True
        self.show_fps = True
        self.show_quality = True

        # Enregistrement
        self.recording_mode = False
        self.csv_writer = None
        self.csv_file = None
        self.recording_start_time = None
        
        # ✅ AJOUT : Attributs manquants pour tests
        self.frame_count = 0
        self.roi_rect = None
        self.output_file = None

        # Frames de sortie (pour mosaïque)
        self.frame_normal = None
        self.frame_roi = None
        self.frame_binary = None
        self.frame_contours = None

        # FPS tracking
        self.fps = 0
        self.fps_counter = 0
        self.fps_start_time = time.time()

        # Enregistrement vidéo
        self.output_dir = output_dir or "recordings"  # Dossier de sortie
        os.makedirs(self.output_dir, exist_ok=True)   # Créer si n'existe pas
        self.is_recording = False
        self.video_writer = None
        self.current_video_path = None


        print("✅ CameraEngine initialisé")

    # ✅ MÉTHODE SÉPARÉE (en dehors de __init__)
    def is_ready(self):
        """Vérifie si la caméra est opérationnelle"""
        return self.cap is not None and self.cap.isOpened()
 
    # ===========================
    # CONFIGURATION
    # ===========================
    
    def set_camera_params(self, exposure: int, brightness: int, contrast: int):
        """Configure les paramètres de la caméra"""
        self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, brightness)
        self.cap.set(cv2.CAP_PROP_CONTRAST, contrast)
        
        self.exposure = exposure
        self.brightness = brightness
        self.contrast = contrast
    
    def set_roi(self, x: int, y: int, w: int, h: int):
        """Définit la région d'intérêt"""
        self.roi_x = x
        self.roi_y = y
        self.roi_w = w
        self.roi_h = h
    
    def set_threshold(self, value: int):
        """Ajuste le seuil de binarisation (0-255)"""
        self.threshold_value = max(0, min(255, value))
    
    def set_blur_kernel(self, value: int):
        """Ajuste le noyau de flou gaussien (impair uniquement)"""
        if value % 2 == 0:
            value += 1
        self.blur_kernel = max(1, value)
    
    def set_display_mode(self, mode: str):
        """Change le mode d'affichage ('normal', 'roi', 'binary', 'mosaic')"""
        if mode in ['normal', 'roi', 'binary', 'mosaic']:
            self.display_mode = mode
        else:
            print(f"⚠️ Mode inconnu: {mode}, utilisation de 'normal'")
            self.display_mode = 'normal'
    
    def set_overlays(self, ellipse: bool, diameter: bool, fps: bool, quality: bool):
        """Configure les overlays à afficher"""
        self.show_ellipse = ellipse
        self.show_diameter = diameter
        self.show_fps = fps
        self.show_quality = quality
    
    # ===========================
    # CONTRÔLE ENREGISTREMENT
    # ===========================
    
    def start_recording(self, output_file: str):
        """
        Active le mode enregistrement (création CSV).
        
        Args:
            output_file: Chemin du fichier CSV de sortie
        """
        try:
            self.csv_file = open(output_file, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            
            # En-tête CSV
            self.csv_writer.writerow([
                'timestamp_s',
                'frame_number',
                'diameter_px',
                'diameter_mm',
                'center_x',
                'center_y',
                'area',
                'circularity',
                'quality_score'
            ])
            
            self.recording_mode = True
            self.recording_start_time = time.time()
            print(f"🔴 Enregistrement démarré: {output_file}")
            
        except Exception as e:
            print(f"❌ Erreur démarrage enregistrement: {e}")
            self.recording_mode = False
    
    def stop_recording(self):
        """Arrête l'enregistrement et ferme le CSV"""
        if self.csv_file is not None:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
        
        self.recording_mode = False
        self.recording_start_time = None
        print("⏹️ Enregistrement arrêté")
    
    # ===========================
    # TRAITEMENT PRINCIPAL
    # ===========================
    
    def grab_and_detect(self) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Capture une frame, détecte la pupille et retourne la vue sélectionnée.
        
        Returns:
            tuple: (frame_affichage, pupil_data)
                - frame_affichage: Image à afficher selon le mode
                - pupil_data: Dict avec données pupille ou None si non détectée
        """
        # 1. Capture
        ret, frame = self.cap.read()
        if not ret:
            return np.zeros((480, 640, 3), dtype=np.uint8), None
        
        # 2. Extraction ROI
        roi = frame[self.roi_y:self.roi_y+self.roi_h, 
                    self.roi_x:self.roi_x+self.roi_w]
        
        if roi.size == 0:
            return frame, None
        
        # 3. Traitement d'image
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)
        _, binary = cv2.threshold(blurred, self.threshold_value, 255, cv2.THRESH_BINARY_INV)
        
        # 4. Détection contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 5. Sélection meilleur contour (pupille)
        pupil_data = self._find_best_pupil(contours)
        
        # 6. Génération des vues
        self.frame_normal = self._generate_normal_view(frame.copy(), pupil_data)
        self.frame_roi = self._generate_roi_view(roi.copy(), pupil_data)
        self.frame_binary = self._generate_binary_view(binary)
        self.frame_contours = self._generate_contours_view(roi.copy(), contours)
        
        # 7. Enregistrement (si mode actif)
        if self.recording_mode and pupil_data:
            self._record_data(pupil_data)
        
        # 8. Calcul FPS
        self._update_fps()
        
        # 9. Retour de la vue sélectionnée
        output_frame = self._get_display_frame()
        
        return output_frame, pupil_data
    
    def _detect_pupil_internal(self, frame):
        """
        Détecte la pupille sur une frame donnée.
        
        Args:
            frame: Image BGR (numpy array)
        
        Returns:
            dict: {'center': (x,y), 'diameter_px': float, 'diameter_mm': float} ou None
        """
        if frame is None:
            return None
        
        # Conversion en niveaux de gris
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Flou gaussien (réduction du bruit)
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)
        
        # Seuillage binaire
        _, binary = cv2.threshold(blurred, self.threshold_value, 255, cv2.THRESH_BINARY_INV)
        
        # Détection des contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 0:
            return None
        
        # Filtrage des contours valides
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filtres de taille
            if area < self.min_area or area > self.max_area:
                continue
            
            # Filtrage par circularité
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * np.pi * area / (perimeter ** 2)
            
            if circularity >= self.min_circularity:
                valid_contours.append((contour, circularity, area))
        
        if len(valid_contours) == 0:
            return None
        
        # Sélection du contour le plus circulaire
        best_contour = max(valid_contours, key=lambda x: x[1])[0]
        
        # Ajustement d'une ellipse
        if len(best_contour) < 5:  # fitEllipse nécessite au moins 5 points
            return None
        
        ellipse = cv2.fitEllipse(best_contour)
        center = (int(ellipse[0][0]), int(ellipse[0][1]))
        axes = ellipse[1]
        diameter_px = (axes[0] + axes[1]) / 2  # Moyenne des axes
        diameter_mm = diameter_px * self.mm_per_pixel
        
        return {
            'center': center,
            'diameter_px': diameter_px,
            'diameter_mm': diameter_mm,
            'ellipse': ellipse  # Pour affichage ultérieur
        }


    # ===========================
    # ENREGISTREMENT VIDÉO
    # ===========================

    def start_recording(self, prefix="recording"):
        """
        Démarre l'enregistrement vidéo.
        
        Args:
            prefix: Préfixe pour le nom de fichier (ex: "patient001")
        
        Returns:
            str: Nom du fichier (sans chemin complet) ou None si échec
        """
        if self.is_recording:
            print("⚠️ Enregistrement déjà en cours")
            return None
        
        # Génération du nom de fichier : YYYYMMDD_HHMMSS_prefix.mp4
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{prefix}.mp4"
        self.current_video_path = os.path.join(self.output_dir, filename)
        
        # Codec H264 (ou MJPEG si H264 non disponible)
        fourcc = cv2.VideoWriter_fourcc(*'H264')  # Ou 'mp4v', 'MJPG'
        
        # Résolution actuelle de la caméra
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0  # Fallback 30 FPS
        
        # Création du VideoWriter
        self.video_writer = cv2.VideoWriter(
            self.current_video_path,
            fourcc,
            fps,
            (width, height)
        )
        
        if not self.video_writer.isOpened():
            print(f"❌ Échec création VideoWriter: {self.current_video_path}")
            self.video_writer = None
            return None
        
        self.is_recording = True
        print(f"🔴 Enregistrement démarré: {filename}")
        return filename


    def write_frame(self, frame):
        """
        Écrit une frame dans la vidéo en cours.
        
        Args:
            frame: Image BGR (numpy array)
        
        Returns:
            bool: True si succès, False sinon
        """
        if not self.is_recording or self.video_writer is None:
            return False
        
        self.video_writer.write(frame)
        return True


    def stop_recording(self):
        """
        Arrête l'enregistrement vidéo.
        
        Returns:
            str: Chemin complet du fichier enregistré, ou None si aucun enregistrement
        """
        if not self.is_recording:
            return None
        
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        
        self.is_recording = False
        saved_path = self.current_video_path
        self.current_video_path = None
        
        print(f"⏹️ Enregistrement arrêté: {os.path.basename(saved_path)}")
        return saved_path


    # ===========================
    # GÉNÉRATION DES VUES
    # ===========================
    
    def _generate_normal_view(self, frame: np.ndarray, pupil: Optional[Dict]) -> np.ndarray:
        """Vue normale: RGB avec ROI et overlays"""
        # Dessiner le rectangle ROI
        cv2.rectangle(frame, 
                     (self.roi_x, self.roi_y), 
                     (self.roi_x + self.roi_w, self.roi_y + self.roi_h),
                     (0, 255, 0), 2)
        
        if pupil and self.show_ellipse:
            # Coordonnées dans le frame complet
            center = (int(pupil['center_x'] + self.roi_x), 
                     int(pupil['center_y'] + self.roi_y))
            axes = (int(pupil['ellipse'][1][0]/2), int(pupil['ellipse'][1][1]/2))
            angle = int(pupil['ellipse'][2])
            
            # Dessiner l'ellipse
            cv2.ellipse(frame, center, axes, angle, 0, 360, (0, 0, 255), 2)
            
            # Dessiner le centre
            cv2.circle(frame, center, 3, (255, 0, 0), -1)
        
        # Overlays texte
        y_offset = 30
        if self.show_diameter and pupil:
            text = f"Diameter: {pupil['diameter_mm']:.2f} mm"
            cv2.putText(frame, text, (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            y_offset += 25
        
        if self.show_fps:
            text = f"FPS: {self.fps:.1f}"
            cv2.putText(frame, text, (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            y_offset += 25
        
        if self.show_quality and pupil:
            text = f"Quality: {pupil['quality_score']:.0f}%"
            color = (0, 255, 0) if pupil['quality_score'] > 80 else (0, 165, 255)
            cv2.putText(frame, text, (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return frame
    
    def _generate_roi_view(self, roi: np.ndarray, pupil: Optional[Dict]) -> np.ndarray:
        """Vue ROI: Zone détection agrandie"""
        if pupil and self.show_ellipse:
            center = (int(pupil['center_x']), int(pupil['center_y']))
            axes = (int(pupil['ellipse'][1][0]/2), int(pupil['ellipse'][1][1]/2))
            angle = int(pupil['ellipse'][2])
            
            cv2.ellipse(roi, center, axes, angle, 0, 360, (0, 0, 255), 2)
            cv2.circle(roi, center, 3, (255, 0, 0), -1)
        
        if pupil and self.show_diameter:
            text = f"{pupil['diameter_mm']:.2f} mm"
            cv2.putText(roi, text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        return roi
    
    def _generate_binary_view(self, binary: np.ndarray) -> np.ndarray:
        """Vue binaire: Seuillage noir/blanc"""
        # Ajouter infos texte (convertir en BGR pour texte couleur)
        binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        
        text = f"Threshold: {self.threshold_value}"
        cv2.putText(binary_bgr, text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return binary_bgr
    
    def _generate_contours_view(self, roi: np.ndarray, contours: list) -> np.ndarray:
        """Vue contours: Debug détection"""
        # Dessiner tous les contours
        cv2.drawContours(roi, contours, -1, (0, 255, 0), 1)
        
        # Info nombre de contours
        text = f"Contours: {len(contours)}"
        cv2.putText(roi, text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        return roi
    
    def _create_mosaic(self) -> np.ndarray:
        """Crée la vue mosaïque 2x2"""
        h, w = 240, 320
        
        # Redimensionner toutes les vues
        top_left = cv2.resize(self.frame_normal, (w, h))
        top_right = cv2.resize(self.frame_roi, (w, h))
        bottom_left = cv2.resize(self.frame_binary, (w, h))
        bottom_right = cv2.resize(self.frame_contours, (w, h))
        
        # Labels
        cv2.putText(top_left, "Normal", (5, 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(top_right, "ROI", (5, 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(bottom_left, "Binary", (5, 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(bottom_right, "Contours", (5, 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Assembler
        top_row = np.hstack([top_left, top_right])
        bottom_row = np.hstack([bottom_left, bottom_right])
        mosaic = np.vstack([top_row, bottom_row])
        
        # Info globale
        text = f"FPS: {self.fps:.1f} | Threshold: {self.threshold_value}"
        cv2.putText(mosaic, text, (10, mosaic.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
        return mosaic
    
    def _get_display_frame(self) -> np.ndarray:
        """Retourne la frame selon le mode d'affichage"""
        if self.display_mode == 'normal':
            return self.frame_normal
        
        elif self.display_mode == 'roi':
            # Agrandir le ROI à 640x480
            return cv2.resize(self.frame_roi, (640, 480))
        
        elif self.display_mode == 'binary':
            # Agrandir la vue binaire
            return cv2.resize(self.frame_binary, (640, 480))
        
        elif self.display_mode == 'mosaic':
            return self._create_mosaic()
        
        else:
            return self.frame_normal
    
    # ===========================
    # DÉTECTION PUPILLE
    # ===========================
    
    def _find_best_pupil(self, contours: list) -> Optional[Dict]:
        """
        Trouve le meilleur contour candidat pour la pupille.
        
        Critères:
        - Aire entre min_area et max_area
        - Circularité > min_circularity
        - Peut être fitté par une ellipse
        
        Returns:
            Dict avec données pupille ou None
        """
        best_pupil = None
        best_score = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filtrage aire
            if area < self.min_area or area > self.max_area:
                continue
            
            # Vérification nombre de points (besoin de >= 5 pour ellipse)
            if len(contour) < 5:
                continue
            
            # Fit ellipse
            try:
                ellipse = cv2.fitEllipse(contour)
            except:
                continue
            
            # Calcul circularité
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            
            # Filtrage circularité
            if circularity < self.min_circularity:
                continue
            
            # Score de qualité (aire + circularité)
            score = area * circularity
            
            if score > best_score:
                best_score = score
                
                # Extraction données
                center_x, center_y = ellipse[0]
                major_axis, minor_axis = ellipse[1]
                diameter_px = (major_axis + minor_axis) / 2
                diameter_mm = diameter_px * self.mm_per_pixel
                
                # Score qualité (0-100)
                quality_score = min(100, circularity * 100)
                
                best_pupil = {
                    'center_x': center_x,
                    'center_y': center_y,
                    'diameter_px': diameter_px,
                    'diameter_mm': diameter_mm,
                    'area': area,
                    'circularity': circularity,
                    'ellipse': ellipse,
                    'quality_score': quality_score,
                    'contour': contour
                }
        
        return best_pupil
    
    # ===========================
    # ENREGISTREMENT DONNÉES
    # ===========================
    
    def _record_data(self, pupil: Dict):
        """Enregistre une ligne dans le CSV (si recording_mode actif)"""
        if not self.csv_writer:
            return
        
        timestamp = time.time() - self.recording_start_time
        
        self.csv_writer.writerow([
            f"{timestamp:.3f}",
            self.fps_counter,
            f"{pupil['diameter_px']:.2f}",
            f"{pupil['diameter_mm']:.3f}",
            f"{pupil['center_x']:.1f}",
            f"{pupil['center_y']:.1f}",
            f"{pupil['area']:.0f}",
            f"{pupil['circularity']:.3f}",
            f"{pupil['quality_score']:.1f}"
        ])
    
    # ===========================
    # UTILITAIRES
    # ===========================
    
    def _update_fps(self):
        """Calcule le FPS moyen"""
        self.fps_counter += 1
        elapsed = time.time() - self.fps_start_time
        
        if elapsed > 1.0:  # Mise à jour chaque seconde
            self.fps = self.fps_counter / elapsed
            self.fps_counter = 0
            self.fps_start_time = time.time()
    
    def release(self):
        """Libère les ressources"""
        self.stop_recording()
        if self.cap:
            self.cap.release()
        print("✅ CameraEngine libéré")


# ===========================
# TEST STANDALONE
# ===========================

if __name__ == "__main__":
    print("=== TEST CAMERA ENGINE ===\n")
    
    # Initialisation
    camera = CameraEngine(camera_index=0)
    
    print("🎮 Contrôles:")
    print("  [1-4] : Changer mode affichage (Normal/ROI/Binaire/Mosaïque)")
    print("  [+/-] : Ajuster seuil")
    print("  [R]   : Démarrer/Arrêter enregistrement")
    print("  [Q]   : Quitter\n")
    
    recording_active = False
    
    while True:
        # Capture + détection
        frame, pupil = camera.grab_and_detect()
        
        # Affichage
        cv2.imshow("Camera Engine Test", frame)
        
        # Gestion clavier
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        
        elif key == ord('1'):
            camera.set_display_mode('normal')
            print("→ Mode: Normal")
        
        elif key == ord('2'):
            camera.set_display_mode('roi')
            print("→ Mode: ROI")
        
        elif key == ord('3'):
            camera.set_display_mode('binary')
            print("→ Mode: Binaire")
        
        elif key == ord('4'):
            camera.set_display_mode('mosaic')
            print("→ Mode: Mosaïque")
        
        elif key == ord('+') or key == ord('='):
            new_threshold = camera.threshold_value + 5
            camera.set_threshold(new_threshold)
            print(f"→ Seuil: {camera.threshold_value}")
        
        elif key == ord('-') or key == ord('_'):
            new_threshold = camera.threshold_value - 5
            camera.set_threshold(new_threshold)
            print(f"→ Seuil: {camera.threshold_value}")
        
        elif key == ord('r'):
            if not recording_active:
                output_file = f"test_recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                camera.start_recording(output_file)
                recording_active = True
            else:
                camera.stop_recording()
                recording_active = False
    
    # Cleanup
    camera.release()
    cv2.destroyAllWindows()
    print("\n✅ Test terminé")
