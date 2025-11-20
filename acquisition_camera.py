# acquisition_camera.py (version anti-reflets)
import cv2
import numpy as np
import argparse
import json
from pathlib import Path
from enum import Enum

class PupilShape(Enum):
    """Types de pupille détectables."""
    CIRCULAR = 1
    ELLIPTICAL = 2
    HORIZONTAL = 3
    ANY = 4

class PupilTracker:
    """Détecteur de pupille avec suppression des reflets."""

    def __init__(self, camera_index=0, display=True, save_frames=False, output_dir="output_frames"):
        self.camera_index = camera_index
        self.display = display
        self.save_frames = save_frames
        self.output_dir = Path(output_dir) if save_frames else None
        self.cap = None
        self.is_running = False
        self.frame_count = 0

        self.pupil_shape = PupilShape.CIRCULAR

        # Paramètres optimisés pour ton cas
        self.params = {
            # ━━━ SUPPRESSION DES REFLETS ━━━
            'remove_reflections': True,           # ⭐ Activer l'inpainting
            'reflection_threshold': 220,          # Seuil pour détecter les reflets (blanc pur)
            'inpaint_radius': 5,                  # Rayon de reconstruction autour des reflets
            
            # ━━━ DÉTECTION PUPILLE (NOIR PUR) ━━━
            'hsv_value_max': 50,                  # ⭐ Plus strict (30-50 pour noir pur)
            'hsv_saturation_max': 100,            # ⭐ Réduit (évite l'iris marron)
            'use_lab_space': True,                # ⭐ Utilise L*a*b* au lieu de HSV
            'lab_l_max': 70,                      # Luminance max (Lab)
            
            # ━━━ CLAHE (CONTRASTE LOCAL) ━━━
            'use_clahe': True,                    # ⭐ Activé par défaut
            'clahe_clip_limit': 3.0,              # Limite de contraste
            'clahe_tile_size': 8,                 # Taille des tuiles
            
            # ━━━ ROI (RÉGION D'INTÉRÊT) ━━━
            'use_roi': True,                      # ⭐ Cherche uniquement au centre
            'roi_scale': 0.6,                     # Proportion de l'image (0.6 = 60% central)
            
            # ━━━ MORPHOLOGIE ━━━
            'morph_open_size': 3,
            'morph_close_size': 5,
            'use_gradient': False,                # Détection par gradient (optionnel)
            
            # ━━━ FILTRAGE GÉOMÉTRIQUE ━━━
            'min_area': 300,
            'max_area': 5000,
            'min_circularity': 0.7,               # ⭐ Plus strict (pupille = très ronde)
            'min_solidity': 0.8,                  # ⭐ Plus strict (forme pleine)
            'max_aspect_ratio': 1.5,              # ⭐ Plus strict (quasi-circulaire)
        }

        self.config_file = Path("pupil_tracker_config.json")
        self.load_params()

        if self.save_frames and self.output_dir:
            self.output_dir.mkdir(exist_ok=True, parents=True)

    def load_params(self):
        """Charge les paramètres depuis le fichier JSON."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_params = json.load(f)
                    self.params.update(saved_params)
                    if 'pupil_shape' in saved_params:
                        self.pupil_shape = PupilShape(saved_params['pupil_shape'])
                    print(f"✅ Paramètres chargés depuis {self.config_file}")
            except Exception as e:
                print(f"⚠️ Erreur de chargement des paramètres: {e}")

    def save_params(self):
        """Sauvegarde les paramètres dans un fichier JSON."""
        try:
            params_to_save = self.params.copy()
            params_to_save['pupil_shape'] = self.pupil_shape.value
            with open(self.config_file, 'w') as f:
                json.dump(params_to_save, f, indent=4)
                print(f"💾 Paramètres sauvegardés")
        except Exception as e:
            print(f"⚠️ Erreur de sauvegarde: {e}")

    def create_control_window(self):
        """Crée une fenêtre avec des trackbars."""
        window_name = "Reglages Pupille"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 500, 700)

        def nothing(x):
            pass

        # Suppression reflets
        cv2.createTrackbar("Supprimer Reflets", window_name, int(self.params['remove_reflections']), 1, nothing)
        cv2.createTrackbar("Seuil Reflet", window_name, self.params['reflection_threshold'], 255, nothing)
        cv2.createTrackbar("Rayon Inpaint", window_name, self.params['inpaint_radius'], 20, nothing)
        
        # Détection couleur
        cv2.createTrackbar("Utiliser Lab", window_name, int(self.params['use_lab_space']), 1, nothing)
        cv2.createTrackbar("HSV Noir Max", window_name, self.params['hsv_value_max'], 100, nothing)
        cv2.createTrackbar("HSV Sat Max", window_name, self.params['hsv_saturation_max'], 255, nothing)
        cv2.createTrackbar("Lab L Max", window_name, self.params['lab_l_max'], 150, nothing)
        
        # CLAHE
        cv2.createTrackbar("CLAHE (0=OFF)", window_name, int(self.params['use_clahe']), 1, nothing)
        cv2.createTrackbar("CLAHE Clip x10", window_name, int(self.params['clahe_clip_limit'] * 10), 100, nothing)
        
        # ROI
        cv2.createTrackbar("ROI (0=OFF)", window_name, int(self.params['use_roi']), 1, nothing)
        cv2.createTrackbar("ROI Scale x100", window_name, int(self.params['roi_scale'] * 100), 100, nothing)
        
        # Morphologie
        cv2.createTrackbar("Morph Open", window_name, self.params['morph_open_size'], 15, nothing)
        cv2.createTrackbar("Morph Close", window_name, self.params['morph_close_size'], 15, nothing)
        
        # Filtrage
        cv2.createTrackbar("Aire Min", window_name, self.params['min_area'] // 10, 1000, nothing)
        cv2.createTrackbar("Aire Max", window_name, self.params['max_area'] // 10, 2000, nothing)
        cv2.createTrackbar("Circularite x100", window_name, int(self.params['min_circularity'] * 100), 100, nothing)
        cv2.createTrackbar("Solidite x100", window_name, int(self.params['min_solidity'] * 100), 100, nothing)
        cv2.createTrackbar("Aspect Ratio x10", window_name, int(self.params['max_aspect_ratio'] * 10), 50, nothing)

        return window_name

    def update_params_from_trackbars(self, window_name):
        """Met à jour les paramètres depuis les trackbars."""
        # Suppression reflets
        self.params['remove_reflections'] = bool(cv2.getTrackbarPos("Supprimer Reflets", window_name))
        self.params['reflection_threshold'] = cv2.getTrackbarPos("Seuil Reflet", window_name)
        self.params['inpaint_radius'] = max(1, cv2.getTrackbarPos("Rayon Inpaint", window_name))
        
        # Détection couleur
        self.params['use_lab_space'] = bool(cv2.getTrackbarPos("Utiliser Lab", window_name))
        self.params['hsv_value_max'] = cv2.getTrackbarPos("HSV Noir Max", window_name)
        self.params['hsv_saturation_max'] = cv2.getTrackbarPos("HSV Sat Max", window_name)
        self.params['lab_l_max'] = cv2.getTrackbarPos("Lab L Max", window_name)
        
        # CLAHE
        self.params['use_clahe'] = bool(cv2.getTrackbarPos("CLAHE (0=OFF)", window_name))
        self.params['clahe_clip_limit'] = cv2.getTrackbarPos("CLAHE Clip x10", window_name) / 10.0
        
        # ROI
        self.params['use_roi'] = bool(cv2.getTrackbarPos("ROI (0=OFF)", window_name))
        self.params['roi_scale'] = cv2.getTrackbarPos("ROI Scale x100", window_name) / 100.0
        
        # Morphologie
        morph_open = cv2.getTrackbarPos("Morph Open", window_name)
        morph_open = morph_open if morph_open % 2 == 1 else morph_open + 1
        self.params['morph_open_size'] = max(1, morph_open)
        
        morph_close = cv2.getTrackbarPos("Morph Close", window_name)
        morph_close = morph_close if morph_close % 2 == 1 else morph_close + 1
        self.params['morph_close_size'] = max(1, morph_close)
        
        # Filtrage
        self.params['min_area'] = cv2.getTrackbarPos("Aire Min", window_name) * 10
        self.params['max_area'] = cv2.getTrackbarPos("Aire Max", window_name) * 10
        self.params['min_circularity'] = cv2.getTrackbarPos("Circularite x100", window_name) / 100.0
        self.params['min_solidity'] = cv2.getTrackbarPos("Solidite x100", window_name) / 100.0
        self.params['max_aspect_ratio'] = cv2.getTrackbarPos("Aspect Ratio x10", window_name) / 10.0

    def remove_reflections(self, frame):
        """
        ⭐ ÉTAPE 1 : Suppression des reflets par inpainting.
        
        Principe :
        1. Détecter les zones blanches intenses (reflets)
        2. Créer un masque de ces zones
        3. Reconstruire ces zones par inpainting (interpolation des pixels voisins)
        """
        if not self.params['remove_reflections']:
            return frame, None
        
        # Convertir en niveaux de gris
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Détecter les reflets (pixels très blancs)
        _, reflection_mask = cv2.threshold(gray, self.params['reflection_threshold'], 255, cv2.THRESH_BINARY)
        
        # Dilater légèrement le masque (pour inclure les bords du reflet)
        kernel = np.ones((3, 3), np.uint8)
        reflection_mask = cv2.dilate(reflection_mask, kernel, iterations=1)
        
        # Inpainting : reconstruction des zones masquées
        # Méthode : cv2.INPAINT_TELEA (rapide) ou cv2.INPAINT_NS (plus lent mais meilleur)
        frame_no_reflections = cv2.inpaint(frame, reflection_mask, self.params['inpaint_radius'], cv2.INPAINT_TELEA)
        
        return frame_no_reflections, reflection_mask

    def get_roi(self, frame):
        """
        ⭐ Calcule la ROI (région centrale de l'image).
        
        Principe : La pupille est toujours au centre de l'image (si caméra bien positionnée).
        On ignore les bords (cils, paupières, fond).
        """
        if not self.params['use_roi']:
            return frame, (0, 0, frame.shape[1], frame.shape[0])
        
        h, w = frame.shape[:2]
        scale = self.params['roi_scale']
        
        # Calculer les coordonnées du rectangle central
        roi_w = int(w * scale)
        roi_h = int(h * scale)
        x = (w - roi_w) // 2
        y = (h - roi_h) // 2
        
        roi = frame[y:y+roi_h, x:x+roi_w]
        return roi, (x, y, roi_w, roi_h)

    def preprocess_frame(self, frame):
        """
        ⭐ ÉTAPE 2 : Prétraitement adaptatif.
        
        Returns:
            mask: Masque binaire de la pupille
            debug_images: Dictionnaire d'images de debug
        """
        debug_images = {}
        
        # 1. Suppression des reflets
        frame_clean, reflection_mask = self.remove_reflections(frame)
        debug_images['reflections'] = reflection_mask
        debug_images['no_reflections'] = frame_clean
        
        # 2. Extraction de la ROI
        roi, (roi_x, roi_y, roi_w, roi_h) = self.get_roi(frame_clean)
        debug_images['roi_coords'] = (roi_x, roi_y, roi_w, roi_h)
        
        # 3. CLAHE (égalisation de contraste localisée)
        if self.params['use_clahe']:
            # Convertir en Lab (L = luminance, a/b = chrominance)
            lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Appliquer CLAHE uniquement sur le canal L
            clahe = cv2.createCLAHE(
                clipLimit=self.params['clahe_clip_limit'],
                tileGridSize=(self.params['clahe_tile_size'], self.params['clahe_tile_size'])
            )
            l = clahe.apply(l)
            
            # Recombiner
            roi = cv2.merge([l, a, b])
            roi = cv2.cvtColor(roi, cv2.COLOR_LAB2BGR)
            debug_images['clahe'] = roi
        
        # 4. Détection par couleur (Lab ou HSV)
        if self.params['use_lab_space']:
            # ⭐ MÉTHODE Lab (RECOMMANDÉE) ⭐
            # Lab sépare mieux la luminance (L) de la couleur (a, b)
            lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Détecter les pixels sombres (L faible)
            _, mask = cv2.threshold(l, self.params['lab_l_max'], 255, cv2.THRESH_BINARY_INV)
            debug_images['lab_l'] = l
        else:
            # Méthode HSV (alternative)
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower_black = np.array([0, 0, 0])
            upper_black = np.array([179, self.params['hsv_saturation_max'], self.params['hsv_value_max']])
            mask = cv2.inRange(hsv, lower_black, upper_black)
            debug_images['hsv'] = hsv
        
        # 5. Morphologie (nettoyage)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                                (self.params['morph_open_size'], self.params['morph_open_size']))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
        
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                                 (self.params['morph_close_size'], self.params['morph_close_size']))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
        
        debug_images['mask'] = mask
        
        return mask, debug_images

    def calculate_shape_metrics(self, contour):
        """Calcule les métriques de forme d'un contour."""
        area = cv2.contourArea(contour)
        if area < 5:
            return None
        
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0
        
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        
        if len(contour) >= 5:
            ellipse = cv2.fitEllipse(contour)
            (center, axes, angle) = ellipse
            major_axis = max(axes)
            minor_axis = min(axes)
            aspect_ratio = major_axis / minor_axis if minor_axis > 0 else 0
        else:
            ellipse = None
            aspect_ratio = 0
        
        # ⭐ NOUVEAU : Position relative (pour favoriser le centre)
        M = cv2.moments(contour)
        if M['m00'] != 0:
            cx = int(M['m10'] / M['m00'])
            cy = int(M['m01'] / M['m00'])
        else:
            cx, cy = 0, 0
        
        return {
            'area': area,
            'solidity': solidity,
            'circularity': circularity,
            'aspect_ratio': aspect_ratio,
            'ellipse': ellipse,
            'center': (cx, cy)
        }

    def detect_pupil(self, mask, original_frame, debug_images):
        """
        ⭐ ÉTAPE 3 : Détection avec validation géométrique stricte.
        """
        # Trouver tous les contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) == 0:
            return None

        # Récupérer les coordonnées de la ROI
        roi_coords = debug_images.get('roi_coords', (0, 0, original_frame.shape[1], original_frame.shape[0]))
        roi_x, roi_y, roi_w, roi_h = roi_coords
        
        # Centre de la ROI (position idéale de la pupille)
        roi_center_x = roi_w // 2
        roi_center_y = roi_h // 2

        best_pupil = None
        best_score = 0

        for contour in contours:
            metrics = self.calculate_shape_metrics(contour)
            if metrics is None:
                continue
            
            # ━━━ FILTRAGE STRICT ━━━
            
            # Filtre 1 : Aire
            if metrics['area'] < self.params['min_area'] or metrics['area'] > self.params['max_area']:
                continue
            
            # Filtre 2 : Solidité (forme pleine)
            if metrics['solidity'] < self.params['min_solidity']:
                continue
            
            # Filtre 3 : Circularité (presque un cercle)
            if metrics['circularity'] < self.params['min_circularity']:
                continue
            
            # Filtre 4 : Aspect ratio (presque 1:1)
            if metrics['aspect_ratio'] > self.params['max_aspect_ratio']:
                continue
            
            # ⭐ Filtre 5 : Distance au centre (favorise les contours centraux)
            cx, cy = metrics['center']
            distance_to_center = np.sqrt((cx - roi_center_x)**2 + (cy - roi_center_y)**2)
            max_distance = np.sqrt(roi_w**2 + roi_h**2) / 2  # Diagonale / 2
            centrality = 1 - (distance_to_center / max_distance)  # 1 = au centre, 0 = au bord
            
            # ━━━ SCORE COMBINÉ ━━━
            score = (
                metrics['circularity'] * 0.30 +
                metrics['solidity'] * 0.25 +
                (1 / metrics['aspect_ratio']) * 0.20 +
                centrality * 0.25  # ⭐ 25% du score basé sur la centralité
            )
            
            if score > best_score:
                best_score = score
                best_pupil = {
                    'contour': contour,
                    'ellipse': metrics['ellipse'],
                    'area': metrics['area'],
                    'solidity': metrics['solidity'],
                    'circularity': metrics['circularity'],
                    'aspect_ratio': metrics['aspect_ratio'],
                    'center': metrics['center'],
                    'centrality': centrality,
                    'score': score,
                    'roi_offset': (roi_x, roi_y)  # Pour repositionner dans l'image complète
                }

        return best_pupil

    def start(self):
        """Démarre la caméra."""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Impossible d'ouvrir la caméra (index={self.camera_index})")
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            self.is_running = True
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"🎥 Caméra démarrée (résolution: {width}x{height})")
            print(f"🔍 Type de pupille: {self.pupil_shape.name}")

        except Exception as e:
            print(f"❌ Erreur lors du démarrage de la caméra: {e}")
            self.is_running = False

    def stop(self):
        """Arrête la caméra et ferme les fenêtres."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.is_running = False
        cv2.destroyAllWindows()
        print("🛑 Caméra arrêtée.")

    def run(self):
        """Boucle principale d'acquisition et de traitement."""
        if not self.is_running:
            self.start()

        if not self.is_running:
            return

        control_window = self.create_control_window()

        print("\n🎮 Contrôles:")
        print("  - 's' : Sauvegarder les paramètres")
        print("  - 'r' : Réinitialiser aux valeurs par défaut")
        print("  - 'q' : Quitter\n")

        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                print("⚠️ Impossible de lire la frame")
                break

            self.update_params_from_trackbars(control_window)

            # Prétraitement
            mask, debug_images = self.preprocess_frame(frame)

            # Détection
            pupil = self.detect_pupil(mask, frame, debug_images)

            # Affichage
            display_frame = frame.copy()
            
            # Dessiner la ROI
            if self.params['use_roi']:
                roi_x, roi_y, roi_w, roi_h = debug_images['roi_coords']
                cv2.rectangle(display_frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (255, 255, 0), 2)
            
            # Dessiner la pupille détectée
            if pupil and pupil['ellipse'] is not None:
                # Repositionner l'ellipse dans le repère de l'image complète
                roi_x, roi_y = pupil['roi_offset']
                ellipse = pupil['ellipse']
                center, axes, angle = ellipse
                center_full = (int(center[0] + roi_x), int(center[1] + roi_y))
                ellipse_full = (center_full, axes, angle)
                
                # Dessiner l'ellipse
                cv2.ellipse(display_frame, ellipse_full, (0, 0, 255), 2)
                
                # Dessiner le contour
                contour_full = pupil['contour'] + np.array([roi_x, roi_y])
                cv2.drawContours(display_frame, [contour_full], -1, (0, 255, 0), 1)
                
                # Centre
                cv2.circle(display_frame, center_full, 3, (0, 255, 0), -1)

                # Afficher les métriques
                x, y = center_full
                text1 = f"A:{int(pupil['area'])} C:{pupil['circularity']:.2f}"
                text2 = f"S:{pupil['solidity']:.2f} Cnt:{pupil['centrality']:.2f}"
                cv2.putText(display_frame, text1, (x - 80, y - 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                cv2.putText(display_frame, text2, (x - 80, y - 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

            if self.display:
                cv2.imshow("1. Flux Original", frame)
                
                if debug_images.get('no_reflections') is not None:
                    cv2.imshow("2. Sans Reflets", debug_images['no_reflections'])
                
                if debug_images.get('reflections') is not None:
                    cv2.imshow("3. Masque Reflets", debug_images['reflections'])
                
                if debug_images.get('clahe') is not None:
                    cv2.imshow("4. CLAHE", debug_images['clahe'])
                
                if debug_images.get('lab_l') is not None:
                    cv2.imshow("5. Lab L (luminance)", debug_images['lab_l'])
                
                # Agrandir le masque à la taille de la frame complète
                mask_full = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.uint8)
                roi_x, roi_y, roi_w, roi_h = debug_images['roi_coords']
                mask_full[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w] = mask
                cv2.imshow("6. Masque Final", mask_full)
                
                cv2.imshow("7. Detection Finale", display_frame)

            # Sauvegarde
            if self.save_frames and pupil:
                filename = self.output_dir / f"frame_{self.frame_count:06d}.jpg"
                cv2.imwrite(str(filename), display_frame)
                self.frame_count += 1

            # Gestion des touches
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                self.save_params()
            elif key == ord('r'):
                self.params = {
                    'remove_reflections': True,
                    'reflection_threshold': 220,
                    'inpaint_radius': 5,
                    'hsv_value_max': 50,
                    'hsv_saturation_max': 100,
                    'use_lab_space': True,
                    'lab_l_max': 70,
                    'use_clahe': True,
                    'clahe_clip_limit': 3.0,
                    'clahe_tile_size': 8,
                    'use_roi': True,
                    'roi_scale': 0.6,
                    'morph_open_size': 3,
                    'morph_close_size': 5,
                    'use_gradient': False,
                    'min_area': 300,
                    'max_area': 5000,
                    'min_circularity': 0.7,
                    'min_solidity': 0.8,
                    'max_aspect_ratio': 1.5,
                }
                print("🔄 Paramètres réinitialisés")

        self.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Détection de pupille avec suppression des reflets")
    parser.add_argument("--camera", type=int, default=0, help="Index de la caméra")
    parser.add_argument("--save", action="store_true", help="Sauvegarder les frames")
    parser.add_argument("--output", type=str, default="output_frames", help="Dossier de sortie")
    args = parser.parse_args()

    tracker = PupilTracker(
        camera_index=args.camera,
        save_frames=args.save,
        output_dir=args.output
    )
    
    tracker.run()
