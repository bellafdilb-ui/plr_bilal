"""
calibration.py
OUTIL DE CALIBRATION - Conversion pixels → millimètres
Version 4.2 - Compatible avec acquisition_camera_IR.py
"""

import cv2
import numpy as np
import json
from pathlib import Path
from datetime import datetime


class CalibrationTool:
    """Outil de calibration caméra pour pupillométrie"""

    def __init__(self, camera_id=0):
        """Initialisation de l'outil de calibration"""

        print("🔬 Initialisation CalibrationTool v4.2")

        # ═══════════════════════════════════════════════════════════
        # CHEMINS
        # ═══════════════════════════════════════════════════════════
        self.project_root = Path(__file__).parent
        self.calib_file = self.project_root / "calibration_data.json"
        self.shared_params = self.project_root / "shared_params.json"

        # ═══════════════════════════════════════════════════════════
        # CAMÉRA
        # ═══════════════════════════════════════════════════════════
        self.camera_id = camera_id
        self.cap = None

        # ═══════════════════════════════════════════════════════════
        # ÉTAT CALIBRATION
        # ═══════════════════════════════════════════════════════════
        self.points = []  # Points cliqués (max 2)
        self.reference_mm = 85.6  # Largeur carte bancaire par défaut
        self.ratio_mm_per_px = None

        # ═══════════════════════════════════════════════════════════
        # CHARGER CALIBRATIONS EXISTANTES
        # ═══════════════════════════════════════════════════════════
        self.load_calibrations()

    # ═══════════════════════════════════════════════════════════════
    # GESTION FICHIERS JSON
    # ═══════════════════════════════════════════════════════════════

    def load_calibrations(self):
        """Charge les calibrations existantes depuis le fichier JSON"""
        try:
            if self.calib_file.exists():
                with open(self.calib_file, 'r') as f:
                    self.calib_data = json.load(f)
                
                # Vérifier la structure
                if "calibrations" not in self.calib_data:
                    self.calib_data["calibrations"] = []
                if "active_calibration" not in self.calib_data:
                    self.calib_data["active_calibration"] = None
                if "ratio_mm_per_px" not in self.calib_data:
                    self.calib_data["ratio_mm_per_px"] = None
                    
                print(f"📂 {len(self.calib_data['calibrations'])} calibration(s) chargée(s)")
            else:
                # Structure par défaut
                self.calib_data = {
                    "calibrations": [],
                    "active_calibration": None,
                    "ratio_mm_per_px": None
                }
                print("📂 Aucune calibration existante, fichier initialisé")
                
        except Exception as e:
            print(f"⚠️ Erreur chargement calibrations : {e}")
            self.calib_data = {
                "calibrations": [],
                "active_calibration": None,
                "ratio_mm_per_px": None
            }

    def save_calibration(self, ratio, reference_mm, distance_px):
        """
        Sauvegarde une nouvelle calibration
        
        Args:
            ratio (float): Ratio mm/px calculé
            reference_mm (float): Distance réelle en mm
            distance_px (float): Distance mesurée en pixels
        """
        try:
            # Créer l'objet calibration
            calibration = {
                "timestamp": datetime.now().isoformat(),
                "ratio_mm_per_px": round(ratio, 4),
                "reference_mm": round(reference_mm, 2),
                "distance_px": round(distance_px, 2),
                "camera_id": self.camera_id
            }

            # Ajouter à l'historique
            self.calib_data["calibrations"].append(calibration)
            self.calib_data["active_calibration"] = len(self.calib_data["calibrations"]) - 1
            
            # ✅ IMPORTANT : Mettre le ratio à la racine pour acquisition_camera_IR.py
            self.calib_data["ratio_mm_per_px"] = round(ratio, 4)

            # Sauvegarder le fichier
            with open(self.calib_file, 'w') as f:
                json.dump(self.calib_data, f, indent=2)

            print(f"\n✅ Calibration sauvegardée : {ratio:.4f} mm/px")
            print(f"   📁 Fichier : {self.calib_file}")
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde calibration : {e}")

    def apply_to_shared_params(self, ratio):
        """
        Applique la calibration aux paramètres partagés
        
        Args:
            ratio (float): Ratio mm/px à appliquer
        """
        try:
            if self.shared_params.exists():
                with open(self.shared_params, 'r') as f:
                    params = json.load(f)

                # Mettre à jour le ratio
                params["params"]["ratio_mm_per_px"] = round(ratio, 4)
                params["timestamp"] = datetime.now().isoformat()

                # Sauvegarder
                with open(self.shared_params, 'w') as f:
                    json.dump(params, f, indent=2)

                print(f"✅ Ratio appliqué aux paramètres partagés : {ratio:.4f} mm/px")
            else:
                print("⚠️ Fichier shared_params.json introuvable")
                
        except Exception as e:
            print(f"❌ Erreur application aux paramètres : {e}")

    # ═══════════════════════════════════════════════════════════════
    # CALIBRATION MANUELLE (2 POINTS)
    # ═══════════════════════════════════════════════════════════════

    def mouse_callback(self, event, x, y, flags, param):
        """
        Callback souris pour sélection de points
        
        Args:
            event: Type d'événement souris
            x, y: Coordonnées du clic
        """
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.points) < 2:
                self.points.append((x, y))
                print(f"✓ Point {len(self.points)}/2 : ({x}, {y})")

                if len(self.points) == 2:
                    # Calculer distance entre les 2 points
                    p1, p2 = self.points
                    distance_px = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

                    # Calculer le ratio
                    self.ratio_mm_per_px = self.reference_mm / distance_px

                    print("\n" + "="*60)
                    print("📐 CALIBRATION CALCULÉE")
                    print("="*60)
                    print(f"   Distance pixels : {distance_px:.2f} px")
                    print(f"   Distance réelle : {self.reference_mm:.2f} mm")
                    print(f"   Ratio           : {self.ratio_mm_per_px:.4f} mm/px")
                    print("="*60)
                    print("\n👉 Appuyez sur 'S' pour sauvegarder ou 'R' pour recommencer\n")

    def run_manual_calibration(self):
        """Mode calibration manuelle (2 points)"""

        print("\n" + "="*60)
        print("🎯 MODE CALIBRATION MANUELLE")
        print("="*60)
        print("1. Placez un objet de taille connue devant la caméra")
        print("   (carte bancaire = 85.6mm recommandé)")
        print("2. Cliquez sur les 2 extrémités de l'objet")
        print("3. Appuyez sur 'S' pour sauvegarder")
        print("4. 'R' pour recommencer, 'Q' pour quitter")
        print("="*60 + "\n")

        # Demander la distance de référence
        ref_input = input(f"Distance de référence en mm [{self.reference_mm}] : ").strip()
        if ref_input:
            try:
                self.reference_mm = float(ref_input)
            except ValueError:
                print("⚠️ Valeur invalide, utilisation de la valeur par défaut")

        # Ouvrir la caméra
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            print(f"❌ Impossible d'ouvrir la caméra {self.camera_id}")
            return

        # Configurer la résolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Créer la fenêtre et configurer le callback
        cv2.namedWindow("Calibration")
        cv2.setMouseCallback("Calibration", self.mouse_callback)

        print("📹 Caméra ouverte, cliquez sur l'image...\n")

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("❌ Erreur lecture caméra")
                    break

                # Copie pour l'affichage
                display = frame.copy()

                # Dessiner les points déjà cliqués
                for i, point in enumerate(self.points):
                    cv2.circle(display, point, 8, (0, 255, 0), -1)
                    cv2.putText(display, f"P{i+1}", 
                               (point[0]+15, point[1]+15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                # Si 2 points, dessiner la ligne
                if len(self.points) == 2:
                    cv2.line(display, self.points[0], self.points[1], 
                            (0, 255, 255), 2)
                    
                    # Afficher la distance au milieu
                    mid_x = (self.points[0][0] + self.points[1][0]) // 2
                    mid_y = (self.points[0][1] + self.points[1][1]) // 2
                    
                    distance_px = np.sqrt(
                        (self.points[1][0]-self.points[0][0])**2 + 
                        (self.points[1][1]-self.points[0][1])**2
                    )
                    
                    cv2.putText(display, f"{distance_px:.1f} px", 
                               (mid_x, mid_y-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                # Afficher les infos
                y_offset = 30
                cv2.putText(display, f"Reference: {self.reference_mm:.1f} mm", 
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                y_offset += 30
                cv2.putText(display, f"Points: {len(self.points)}/2", 
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                if self.ratio_mm_per_px:
                    y_offset += 30
                    cv2.putText(display, f"Ratio: {self.ratio_mm_per_px:.4f} mm/px", 
                               (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    y_offset += 30
                    cv2.putText(display, "S=Save | R=Reset | Q=Quit", 
                               (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                cv2.imshow("Calibration", display)

                # Gestion clavier
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q') or key == 27:  # Q ou ESC
                    print("👋 Fermeture calibration")
                    break

                elif key == ord('r'):  # Reset
                    self.points = []
                    self.ratio_mm_per_px = None
                    print("🔄 Réinitialisation, cliquez 2 nouveaux points")

                elif key == ord('s') and self.ratio_mm_per_px:  # Save
                    # Calculer la distance pour la sauvegarde
                    p1, p2 = self.points
                    distance_px = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

                    # Sauvegarder
                    self.save_calibration(
                        self.ratio_mm_per_px,
                        self.reference_mm,
                        distance_px
                    )
                    
                    # Appliquer aux paramètres partagés
                    self.apply_to_shared_params(self.ratio_mm_per_px)
                    
                    print("✅ Calibration appliquée ! Vous pouvez quitter (Q)")

        finally:
            self.cap.release()
            cv2.destroyAllWindows()

    # ═══════════════════════════════════════════════════════════════
    # GESTION DES CALIBRATIONS
    # ═══════════════════════════════════════════════════════════════

    def show_calibrations(self):
        """Affiche toutes les calibrations existantes"""

        if not self.calib_data["calibrations"]:
            print("\n❌ Aucune calibration trouvée\n")
            return

        print("\n" + "="*60)
        print("📋 CALIBRATIONS EXISTANTES")
        print("="*60)

        for i, calib in enumerate(self.calib_data["calibrations"]):
            active = " [ACTIVE]" if i == self.calib_data["active_calibration"] else ""
            
            # Formatage de la date
            try:
                timestamp = datetime.fromisoformat(calib['timestamp'])
                date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            except:
                date_str = calib['timestamp']
            
            print(f"\n{i+1}. {date_str}{active}")
            print(f"   Ratio      : {calib['ratio_mm_per_px']:.4f} mm/px")
            print(f"   Référence  : {calib['reference_mm']:.2f} mm")
            print(f"   Distance   : {calib['distance_px']:.2f} px")
            print(f"   Caméra     : {calib.get('camera_id', 'N/A')}")

        print("="*60 + "\n")

    def select_calibration(self, index):
        """
        Active une calibration spécifique
        
        Args:
            index (int): Index de la calibration (0-based)
        """
        if 0 <= index < len(self.calib_data["calibrations"]):
            # Mettre à jour l'index actif
            self.calib_data["active_calibration"] = index
            
            # Récupérer le ratio
            ratio = self.calib_data["calibrations"][index]["ratio_mm_per_px"]
            
            # ✅ Mettre le ratio à la racine
            self.calib_data["ratio_mm_per_px"] = ratio

            # Sauvegarder
            with open(self.calib_file, 'w') as f:
                json.dump(self.calib_data, f, indent=2)

            # Appliquer aux paramètres partagés
            self.apply_to_shared_params(ratio)

            print(f"\n✅ Calibration {index+1} activée : {ratio:.4f} mm/px\n")
        else:
            print(f"\n❌ Index invalide (doit être entre 1 et {len(self.calib_data['calibrations'])})\n")

    def delete_calibration(self, index):
        """
        Supprime une calibration
        
        Args:
            index (int): Index de la calibration (0-based)
        """
        if 0 <= index < len(self.calib_data["calibrations"]):
            removed = self.calib_data["calibrations"].pop(index)
            
            # Ajuster l'index actif
            if self.calib_data["active_calibration"] == index:
                # Si on supprime la calibration active
                if self.calib_data["calibrations"]:
                    self.calib_data["active_calibration"] = 0
                    new_ratio = self.calib_data["calibrations"][0]["ratio_mm_per_px"]
                    self.calib_data["ratio_mm_per_px"] = new_ratio
                else:
                    self.calib_data["active_calibration"] = None
                    self.calib_data["ratio_mm_per_px"] = None
                    
            elif self.calib_data["active_calibration"] and self.calib_data["active_calibration"] > index:
                self.calib_data["active_calibration"] -= 1

            # Sauvegarder
            with open(self.calib_file, 'w') as f:
                json.dump(self.calib_data, f, indent=2)

            print(f"\n✅ Calibration {index+1} supprimée\n")
        else:
            print(f"\n❌ Index invalide\n")

    # ═══════════════════════════════════════════════════════════════
    # MENU PRINCIPAL
    # ═══════════════════════════════════════════════════════════════

    def run_menu(self):
        """Menu principal de l'outil"""

        while True:
            print("\n" + "="*60)
            print("🔬 OUTIL DE CALIBRATION PUPILLOMÉTRIE v4.2")
            print("="*60)
            print("1. Nouvelle calibration manuelle (2 points)")
            print("2. Afficher calibrations existantes")
            print("3. Sélectionner une calibration")
            print("4. Supprimer une calibration")
            print("5. Quitter")
            print("="*60)

            choice = input("\nChoix : ").strip()

            if choice == '1':
                self.run_manual_calibration()

            elif choice == '2':
                self.show_calibrations()

            elif choice == '3':
                self.show_calibrations()
                if self.calib_data["calibrations"]:
                    idx_input = input("\nIndex de calibration à activer : ").strip()
                    try:
                        idx = int(idx_input) - 1  # Convertir 1-based en 0-based
                        self.select_calibration(idx)
                    except ValueError:
                        print("\n❌ Veuillez entrer un nombre valide\n")

            elif choice == '4':
                self.show_calibrations()
                if self.calib_data["calibrations"]:
                    idx_input = input("\nIndex de calibration à supprimer : ").strip()
                    try:
                        idx = int(idx_input) - 1
                        confirm = input(f"⚠️ Confirmer suppression calibration {idx+1} ? (o/N) : ").strip().lower()
                        if confirm == 'o':
                            self.delete_calibration(idx)
                    except ValueError:
                        print("\n❌ Veuillez entrer un nombre valide\n")

            elif choice == '5' or choice.lower() == 'q':
                print("\n👋 Au revoir !\n")
                break

            else:
                print("\n❌ Choix invalide\n")


# ═══════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Démarrage CalibrationTool")
    print("="*60 + "\n")
    
    tool = CalibrationTool(camera_id=0)
    tool.run_menu()
