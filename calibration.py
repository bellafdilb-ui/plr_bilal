"""
calibration.py
OUTIL DE CALIBRATION - Conversion pixels → millimètres
"""

import cv2
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox


class CalibrationTool:
    """Outil de calibration caméra"""
    
    def __init__(self, camera_id=0):
        """Initialisation"""
        
        # Chemins
        self.project_root = Path(__file__).parent
        self.calib_file = self.project_root / "calibration_data.json"
        self.shared_params = self.project_root / "shared_params.json"
        
        # Caméra
        self.camera_id = camera_id
        self.cap = None
        
        # État calibration
        self.points = []  # Points cliqués
        self.reference_mm = 85.6  # Largeur carte bancaire par défaut
        self.ratio_mm_per_px = None
        
        # Charger calibrations existantes
        self.load_calibrations()
    
    
    def load_calibrations(self):
        """Charge les calibrations existantes"""
        if self.calib_file.exists():
            with open(self.calib_file, 'r') as f:
                self.calib_data = json.load(f)
        else:
            self.calib_data = {
                "calibrations": [],
                "active_calibration": None
            }
    
    
    def save_calibration(self, ratio, reference_mm, distance_px):
        """Sauvegarde une nouvelle calibration"""
        
        calibration = {
            "timestamp": datetime.now().isoformat(),
            "ratio_mm_per_px": ratio,
            "reference_mm": reference_mm,
            "distance_px": distance_px,
            "camera_id": self.camera_id
        }
        
        self.calib_data["calibrations"].append(calibration)
        self.calib_data["active_calibration"] = len(self.calib_data["calibrations"]) - 1
        
        with open(self.calib_file, 'w') as f:
            json.dump(self.calib_data, f, indent=2)
        
        print(f"✅ Calibration sauvegardée : {ratio:.4f} mm/px")
    
    
    def apply_to_shared_params(self, ratio):
        """Applique la calibration aux paramètres partagés"""
        
        if self.shared_params.exists():
            with open(self.shared_params, 'r') as f:
                params = json.load(f)
            
            params["params"]["ratio_mm_per_px"] = ratio
            params["timestamp"] = datetime.now().isoformat()
            
            with open(self.shared_params, 'w') as f:
                json.dump(params, f, indent=2)
            
            print(f"✅ Ratio appliqué aux paramètres partagés")
    
    
    def mouse_callback(self, event, x, y, flags, param):
        """Callback souris pour sélection de points"""
        
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.points) < 2:
                self.points.append((x, y))
                print(f"Point {len(self.points)}/2 : ({x}, {y})")
                
                if len(self.points) == 2:
                    # Calculer distance
                    p1, p2 = self.points
                    distance_px = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    
                    self.ratio_mm_per_px = self.reference_mm / distance_px
                    
                    print("\n" + "="*60)
                    print("📐 CALIBRATION CALCULÉE")
                    print(f"   Distance pixels : {distance_px:.2f} px")
                    print(f"   Distance réelle : {self.reference_mm:.2f} mm")
                    print(f"   Ratio           : {self.ratio_mm_per_px:.4f} mm/px")
                    print("="*60)
                    print("\n👉 Appuyez sur 'S' pour sauvegarder ou 'R' pour recommencer")
    
    
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
        
        # Demander la taille de référence
        ref_input = input(f"Taille de l'objet en mm [{self.reference_mm}] : ").strip()
        if ref_input:
            try:
                self.reference_mm = float(ref_input)
            except ValueError:
                print("⚠️ Valeur invalide, utilisation de 85.6mm")
        
        # Ouvrir caméra
        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        if not self.cap.isOpened():
            print("❌ Impossible d'ouvrir la caméra")
            return
        
        cv2.namedWindow("Calibration")
        cv2.setMouseCallback("Calibration", self.mouse_callback)
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                display = frame.copy()
                
                # Dessiner les points
                for i, pt in enumerate(self.points):
                    cv2.circle(display, pt, 5, (0, 255, 0), -1)
                    cv2.putText(display, f"P{i+1}", (pt[0]+10, pt[1]-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Ligne si 2 points
                if len(self.points) == 2:
                    cv2.line(display, self.points[0], self.points[1], (0, 255, 0), 2)
                    
                    # Distance
                    p1, p2 = self.points
                    mid_x = (p1[0] + p2[0]) // 2
                    mid_y = (p1[1] + p2[1]) // 2
                    dist_px = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    
                    text = f"{dist_px:.1f}px = {self.reference_mm:.1f}mm"
                    cv2.putText(display, text, (mid_x-80, mid_y-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Instructions
                y_offset = 30
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
                
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q') or key == 27:
                    break
                
                elif key == ord('r'):
                    self.points = []
                    self.ratio_mm_per_px = None
                    print("🔄 Réinitialisation")
                
                elif key == ord('s') and self.ratio_mm_per_px:
                    # Sauvegarder
                    p1, p2 = self.points
                    distance_px = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    
                    self.save_calibration(
                        self.ratio_mm_per_px,
                        self.reference_mm,
                        distance_px
                    )
                    self.apply_to_shared_params(self.ratio_mm_per_px)
                    print("✅ Calibration appliquée ! Vous pouvez quitter.")
        
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
    
    
    def show_calibrations(self):
        """Affiche les calibrations existantes"""
        
        if not self.calib_data["calibrations"]:
            print("❌ Aucune calibration trouvée")
            return
        
        print("\n" + "="*60)
        print("📋 CALIBRATIONS EXISTANTES")
        print("="*60)
        
        for i, calib in enumerate(self.calib_data["calibrations"]):
            active = " [ACTIVE]" if i == self.calib_data["active_calibration"] else ""
            print(f"\n{i+1}. {calib['timestamp']}{active}")
            print(f"   Ratio      : {calib['ratio_mm_per_px']:.4f} mm/px")
            print(f"   Référence  : {calib['reference_mm']:.2f} mm")
            print(f"   Distance   : {calib['distance_px']:.2f} px")
        
        print("="*60)
    
    
    def select_calibration(self, index):
        """Active une calibration spécifique"""
        
        if 0 <= index < len(self.calib_data["calibrations"]):
            self.calib_data["active_calibration"] = index
            
            with open(self.calib_file, 'w') as f:
                json.dump(self.calib_data, f, indent=2)
            
            ratio = self.calib_data["calibrations"][index]["ratio_mm_per_px"]
            self.apply_to_shared_params(ratio)
            
            print(f"✅ Calibration {index+1} activée")
        else:
            print("❌ Index invalide")
    
    
    def run_menu(self):
        """Menu principal"""
        
        while True:
            print("\n" + "="*60)
            print("🔬 OUTIL DE CALIBRATION PUPILLOMÉTRIE")
            print("="*60)
            print("1. Nouvelle calibration manuelle")
            print("2. Afficher calibrations existantes")
            print("3. Sélectionner une calibration")
            print("4. Quitter")
            print("="*60)
            
            choice = input("Choix : ").strip()
            
            if choice == '1':
                self.run_manual_calibration()
            
            elif choice == '2':
                self.show_calibrations()
            
            elif choice == '3':
                self.show_calibrations()
                idx_input = input("\nIndex de calibration à activer : ").strip()
                try:
                    idx = int(idx_input) - 1
                    self.select_calibration(idx)
                except ValueError:
                    print("❌ Index invalide")
            
            elif choice == '4':
                break


if __name__ == "__main__":
    tool = CalibrationTool(camera_id=0)
    tool.run_menu()
