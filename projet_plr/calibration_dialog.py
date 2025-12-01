"""
calibration_dialog.py
=====================
Module de calibration pixel -> millimètre.

Permet de calculer le facteur d'échelle en utilisant un objet de référence
de taille connue placé à la distance focale fixe de l'appareil.
"""

import cv2
import numpy as np
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QDoubleSpinBox, QPushButton, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QPixmap

# On réutilise le ConfigManager existant pour sauvegarder le résultat
from settings_dialog import ConfigManager

logger = logging.getLogger(__name__)

class CalibrationDialog(QDialog):
    """
    Fenêtre de calibration.
    Affiche le flux vidéo et permet de mesurer un objet de référence.
    """
    
    # Signal émis quand la calibration est validée (nouveau ratio)
    calibration_saved = Signal(float)

    def __init__(self, camera_engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration de la Mesure")
        self.setMinimumSize(800, 600)
        
        self.camera = camera_engine
        self.config_manager = ConfigManager()
        self.processed_frame = None
        self.current_px_diameter = 0.0
        
        self.setup_ui()
        self.apply_stylesheet()
        
        # Timer pour rafraîchir l'interface (30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. Zone Vidéo
        self.video_label = QLabel("En attente de la caméra...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("background-color: #000; border: 2px solid #555;")
        layout.addWidget(self.video_label, stretch=3)
        
        # 2. Zone Contrôles
        controls_group = QGroupBox("Paramètres de l'Objet de Référence")
        controls_layout = QHBoxLayout()
        
        # Entrée diamètre réel
        lbl_real = QLabel("Diamètre RÉEL de la cible (mm) :")
        self.spin_real_size = QDoubleSpinBox()
        self.spin_real_size.setRange(1.0, 50.0)
        self.spin_real_size.setValue(10.0) # Valeur par défaut standard
        self.spin_real_size.setSuffix(" mm")
        self.spin_real_size.setDecimals(1)
        
        # Affichage diamètre mesuré
        lbl_measured = QLabel("Diamètre DÉTECTÉ (px) :")
        self.lbl_px_size = QLabel("0.0 px")
        self.lbl_px_size.setStyleSheet("font-weight: bold; color: #007bff; font-size: 14px;")
        
        # Bouton Calibrer
        self.btn_calibrate = QPushButton("🎯 CALIBRER MAINTENANT")
        self.btn_calibrate.clicked.connect(self.perform_calibration)
        self.btn_calibrate.setFixedHeight(40)
        
        controls_layout.addWidget(lbl_real)
        controls_layout.addWidget(self.spin_real_size)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(lbl_measured)
        controls_layout.addWidget(self.lbl_px_size)
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_calibrate)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # 3. Info actuelle
        current_ratio = self.camera.mm_per_pixel if self.camera else 0.05
        self.lbl_current_info = QLabel(
            f"Ratio actuel : 1 px = <b>{current_ratio:.5f} mm</b>"
        )
        self.lbl_current_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_current_info)

    def apply_stylesheet(self):
        """Style clair cohérent avec le reste."""
        self.setStyleSheet("""
            QDialog { background-color: #f0f2f5; color: #000; font-size: 10pt; }
            QGroupBox { background-color: #fff; border: 1px solid #ccc; border-radius: 5px; margin-top: 10px; padding-top: 15px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #333; }
            QLabel { color: #000; }
            QDoubleSpinBox { padding: 5px; border: 1px solid #ccc; border-radius: 3px; background: #fff; }
            QPushButton { background-color: #28a745; color: white; border: none; border-radius: 4px; font-weight: bold; font-size: 11pt; }
            QPushButton:hover { background-color: #218838; }
            QPushButton:pressed { background-color: #1e7e34; }
        """)

    def update_frame(self):
        """Récupère l'image et détecte la cible en temps réel."""
        if not self.camera or not self.camera.cap.isOpened():
            return

        # On utilise grab_and_detect pour voir exactement ce que voit l'algo
        # Note: Cela ne perturbe pas l'app principale car calibration est modale
        frame, pupil_data = self.camera.grab_and_detect()
        
        if pupil_data:
            self.current_px_diameter = pupil_data['diameter_px']
            self.lbl_px_size.setText(f"{self.current_px_diameter:.1f} px")
            
            # Dessin de validation (Cercle vert sur la cible)
            cv2.ellipse(frame, pupil_data['ellipse'], (0, 255, 0), 2)
            center = (int(pupil_data['center_x']), int(pupil_data['center_y']))
            cv2.drawMarker(frame, center, (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
        else:
            self.current_px_diameter = 0.0
            self.lbl_px_size.setText("---")

        # Conversion pour affichage Qt
        self._display_image(frame)

    def _display_image(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(img)
            self.video_label.setPixmap(pix.scaled(
                self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        except Exception:
            pass

    def perform_calibration(self):
            """Calcule et sauvegarde le nouveau ratio."""
            if self.current_px_diameter <= 0:
                QMessageBox.warning(self, "Erreur", "Aucune cible détectée.\nVeuillez placer la mire devant la caméra.")
                return

            real_mm = self.spin_real_size.value()
            measured_px = self.current_px_diameter
            
            # CALCUL MAGIQUE
            new_ratio = real_mm / measured_px
            
            # Confirmation
            reply = QMessageBox.question(
                self, "Confirmer Calibration",
                f"Mesure : {measured_px:.1f} pixels pour {real_mm} mm.\n\n"
                f"Nouveau ratio : 1 px = {new_ratio:.6f} mm\n\n"
                "Voulez-vous sauvegarder cette calibration ?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 1. Sauvegarde dans fichier config
                # --- CORRECTION : Suppression des lignes fautives .get() ---
                # On utilise directement .set() qui gère tout correctement
                self.config_manager.set("camera", "mm_per_pixel", new_ratio) 
                self.config_manager.save() # Écriture disque
                
                # 2. Application immédiate à la caméra active
                self.camera.mm_per_pixel = new_ratio
                
                # 3. Émission signal et fermeture
                self.calibration_saved.emit(new_ratio)
                self.lbl_current_info.setText(f"Ratio actuel : 1 px = <b>{new_ratio:.6f} mm</b>")
                QMessageBox.information(self, "Succès", "Calibration enregistrée avec succès !")
                self.accept()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)