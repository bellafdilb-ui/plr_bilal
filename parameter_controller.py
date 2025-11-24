"""
parameter_controller.py
Interface graphique pour ajuster les paramètres en temps réel
✅ Sliders + spin boxes synchronisés
✅ Preview des valeurs
✅ Sauvegarde profils
✅ Import/Export JSON
"""

import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QSlider, QSpinBox, QDoubleSpinBox, QPushButton,
    QComboBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

class ParameterController(QMainWindow):
    """Contrôleur de paramètres avec interface moderne"""
    
    def __init__(self):
        super().__init__()
        
        self.shared_file = Path("shared_params.json")
        self.profiles_dir = Path("config_profiles")
        self.profiles_dir.mkdir(exist_ok=True)
        
        # Paramètres par défaut (identiques à acquisition_camera_IR)
        self.params = {
            # CAMÉRA
            "fps": 30,
            "frame_width": 640,
            "frame_height": 480,
            "exposure": -6,
            "brightness": 128,
            "contrast": 128,
            
            # ROI
            "use_roi": True,
            "roi_scale": 0.5,
            
            # CANAL IR
            "ir_channel": "green",
            
            # REFLETS
            "remove_highlights": True,
            "highlight_threshold": 220,
            
            # DÉBRUITAGE
            "median_ksize": 5,
            
            # SEUILLAGE
            "adaptive_block_size": 35,
            "adaptive_c": 2,
            
            # MORPHOLOGIE
            "morph_kernel_size": 3,
            "morph_open_iter": 3,
            "morph_close_iter": 2,
            
            # VALIDATION
            "min_area": 100,
            "max_area": 5000,
            "min_circularity": 0.5,
            "max_aspect_ratio": 2.5
        }
        
        self.init_ui()
        self.load_default_profile()
        
        # Timer pour écriture automatique (toutes les 500ms)
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.save_to_shared_file)
        self.auto_save_timer.start(500)  # 500ms
        
    def init_ui(self):
        """Construction interface"""
        self.setWindowTitle("🎛️ Contrôle Paramètres Pupillométrie")
        self.setGeometry(100, 100, 800, 900)
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # ═════════════════════════════════════════════════════
        # SECTION 1 : CAMÉRA
        # ═════════════════════════════════════════════════════
        camera_group = self.create_group_box("📹 CAMÉRA")
        camera_layout = QVBoxLayout()
        
        self.fps_slider = self.create_slider_with_spinbox(
            "FPS", 5, 60, self.params["fps"], camera_layout
        )
        self.exposure_slider = self.create_slider_with_spinbox(
            "Exposition", -13, -1, self.params["exposure"], camera_layout
        )
        self.brightness_slider = self.create_slider_with_spinbox(
            "Luminosité", 0, 255, self.params["brightness"], camera_layout
        )
        self.contrast_slider = self.create_slider_with_spinbox(
            "Contraste", 0, 255, self.params["contrast"], camera_layout
        )
        
        camera_group.setLayout(camera_layout)
        main_layout.addWidget(camera_group)
        
        # ═════════════════════════════════════════════════════
        # SECTION 2 : ROI
        # ═════════════════════════════════════════════════════
        roi_group = self.create_group_box("🔍 ROI (Region of Interest)")
        roi_layout = QVBoxLayout()
        
        self.roi_scale_slider = self.create_slider_with_doublespinbox(
            "Échelle ROI", 0.1, 1.0, self.params["roi_scale"], 0.05, roi_layout
        )
        
        roi_group.setLayout(roi_layout)
        main_layout.addWidget(roi_group)
        
        # ═════════════════════════════════════════════════════
        # SECTION 3 : TRAITEMENT IMAGE
        # ═════════════════════════════════════════════════════
        processing_group = self.create_group_box("🎨 TRAITEMENT IMAGE")
        processing_layout = QVBoxLayout()
        
        # Canal IR
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("Canal IR :"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["green", "red", "blue", "mono"])
        self.channel_combo.setCurrentText(self.params["ir_channel"])
        self.channel_combo.currentTextChanged.connect(self.on_param_changed)
        channel_layout.addWidget(self.channel_combo)
        channel_layout.addStretch()
        processing_layout.addLayout(channel_layout)
        
        # Seuil reflets
        self.highlight_threshold_slider = self.create_slider_with_spinbox(
            "Seuil Reflets", 180, 255, self.params["highlight_threshold"], processing_layout
        )
        
        # Flou médian
        self.median_ksize_slider = self.create_slider_with_spinbox(
            "Flou Médian (taille noyau)", 1, 15, self.params["median_ksize"], processing_layout, step=2
        )
        
        # Seuillage adaptatif
        self.adaptive_block_slider = self.create_slider_with_spinbox(
            "Seuillage - Taille Bloc", 11, 99, self.params["adaptive_block_size"], processing_layout, step=2
        )
        self.adaptive_c_slider = self.create_slider_with_spinbox(
            "Seuillage - Constante C", -10, 10, self.params["adaptive_c"], processing_layout
        )
        
        processing_group.setLayout(processing_layout)
        main_layout.addWidget(processing_group)
        
        # ═════════════════════════════════════════════════════
        # SECTION 4 : MORPHOLOGIE
        # ═════════════════════════════════════════════════════
        morph_group = self.create_group_box("🔧 MORPHOLOGIE")
        morph_layout = QVBoxLayout()
        
        self.morph_kernel_slider = self.create_slider_with_spinbox(
            "Taille Noyau", 1, 11, self.params["morph_kernel_size"], morph_layout, step=2
        )
        self.morph_open_slider = self.create_slider_with_spinbox(
            "Itérations Ouverture", 0, 10, self.params["morph_open_iter"], morph_layout
        )
        self.morph_close_slider = self.create_slider_with_spinbox(
            "Itérations Fermeture", 0, 10, self.params["morph_close_iter"], morph_layout
        )
        
        morph_group.setLayout(morph_layout)
        main_layout.addWidget(morph_group)
        
        # ═════════════════════════════════════════════════════
        # SECTION 5 : VALIDATION
        # ═════════════════════════════════════════════════════
        validation_group = self.create_group_box("✅ VALIDATION GÉOMÉTRIQUE")
        validation_layout = QVBoxLayout()
        
        self.min_area_slider = self.create_slider_with_spinbox(
            "Aire Minimale (px²)", 50, 1000, self.params["min_area"], validation_layout
        )
        self.max_area_slider = self.create_slider_with_spinbox(
            "Aire Maximale (px²)", 1000, 10000, self.params["max_area"], validation_layout, step=100
        )
        self.min_circularity_slider = self.create_slider_with_doublespinbox(
            "Circularité Minimale", 0.1, 1.0, self.params["min_circularity"], 0.05, validation_layout
        )
        self.max_aspect_slider = self.create_slider_with_doublespinbox(
            "Aspect Ratio Maximum", 1.0, 5.0, self.params["max_aspect_ratio"], 0.1, validation_layout
        )
        
        validation_group.setLayout(validation_layout)
        main_layout.addWidget(validation_group)
        
        # ═════════════════════════════════════════════════════
        # BOUTONS ACTIONS
        # ═════════════════════════════════════════════════════
        button_layout = QHBoxLayout()
        
        btn_save_profile = QPushButton("💾 Sauvegarder Profil")
        btn_save_profile.clicked.connect(self.save_profile)
        button_layout.addWidget(btn_save_profile)
        
        btn_load_profile = QPushButton("📂 Charger Profil")
        btn_load_profile.clicked.connect(self.load_profile)
        button_layout.addWidget(btn_load_profile)
        
        btn_reset = QPushButton("🔄 Réinitialiser Défaut")
        btn_reset.clicked.connect(self.load_default_profile)
        button_layout.addWidget(btn_reset)
        
        main_layout.addLayout(button_layout)
        
        # Statut
        self.status_label = QLabel("✅ Paramètres synchronisés")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        main_layout.addWidget(self.status_label)
        
    def create_group_box(self, title):
        """Crée un groupe stylisé"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        return group
    
    def create_slider_with_spinbox(self, label, min_val, max_val, default, parent_layout, step=1):
        """Crée slider + spinbox synchronisés"""
        container = QHBoxLayout()
        
        # Label
        lbl = QLabel(f"{label} :")
        lbl.setMinimumWidth(200)
        container.addWidget(lbl)
        
        # Slider
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.setSingleStep(step)
        container.addWidget(slider)
        
        # SpinBox
        spinbox = QSpinBox()
        spinbox.setMinimum(min_val)
        spinbox.setMaximum(max_val)
        spinbox.setValue(default)
        spinbox.setSingleStep(step)
        container.addWidget(spinbox)
        
        # Synchronisation bidirectionnelle
        slider.valueChanged.connect(spinbox.setValue)
        spinbox.valueChanged.connect(slider.setValue)
        slider.valueChanged.connect(self.on_param_changed)
        
        parent_layout.addLayout(container)
        
        return (slider, spinbox)
    
    def create_slider_with_doublespinbox(self, label, min_val, max_val, default, step, parent_layout):
        """Crée slider + double spinbox pour valeurs décimales"""
        container = QHBoxLayout()
        
        lbl = QLabel(f"{label} :")
        lbl.setMinimumWidth(200)
        container.addWidget(lbl)
        
        # Slider (valeurs entières * 100 pour précision)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(int(min_val * 100))
        slider.setMaximum(int(max_val * 100))
        slider.setValue(int(default * 100))
        container.addWidget(slider)
        
        # DoubleSpinBox
        spinbox = QDoubleSpinBox()
        spinbox.setMinimum(min_val)
        spinbox.setMaximum(max_val)
        spinbox.setValue(default)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(2)
        container.addWidget(spinbox)
        
        # Synchronisation
        slider.valueChanged.connect(lambda v: spinbox.setValue(v / 100))
        spinbox.valueChanged.connect(lambda v: slider.setValue(int(v * 100)))
        slider.valueChanged.connect(self.on_param_changed)
        
        parent_layout.addLayout(container)
        
        return (slider, spinbox)
    
    def on_param_changed(self):
        """Mise à jour paramètres lors de changements"""
        # CAMÉRA
        self.params["fps"] = self.fps_slider[1].value()
        self.params["exposure"] = self.exposure_slider[1].value()
        self.params["brightness"] = self.brightness_slider[1].value()
        self.params["contrast"] = self.contrast_slider[1].value()
        
        # ROI
        self.params["roi_scale"] = self.roi_scale_slider[1].value()
        
        # TRAITEMENT
        self.params["ir_channel"] = self.channel_combo.currentText()
        self.params["highlight_threshold"] = self.highlight_threshold_slider[1].value()
        self.params["median_ksize"] = self.median_ksize_slider[1].value()
        self.params["adaptive_block_size"] = self.adaptive_block_slider[1].value()
        self.params["adaptive_c"] = self.adaptive_c_slider[1].value()
        
        # MORPHOLOGIE
        self.params["morph_kernel_size"] = self.morph_kernel_slider[1].value()
        self.params["morph_open_iter"] = self.morph_open_slider[1].value()
        self.params["morph_close_iter"] = self.morph_close_slider[1].value()
        
        # VALIDATION
        self.params["min_area"] = self.min_area_slider[1].value()
        self.params["max_area"] = self.max_area_slider[1].value()
        self.params["min_circularity"] = self.min_circularity_slider[1].value()
        self.params["max_aspect_ratio"] = self.max_aspect_slider[1].value()
        
        self.status_label.setText("🔄 Paramètres modifiés (auto-save dans 500ms)")
        self.status_label.setStyleSheet("color: orange;")
    
    def save_to_shared_file(self):
        """Sauvegarde automatique vers JSON partagé"""
        try:
            with open(self.shared_file, 'w') as f:
                json.dump(self.params, f, indent=2)
            
            self.status_label.setText("✅ Paramètres synchronisés")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        except Exception as e:
            self.status_label.setText(f"❌ Erreur : {e}")
            self.status_label.setStyleSheet("color: red;")
    
    def save_profile(self):
        """Sauvegarde profil personnalisé"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder Profil", str(self.profiles_dir), "JSON (*.json)"
        )
        
        if filename:
            with open(filename, 'w') as f:
                json.dump(self.params, f, indent=2)
            
            QMessageBox.information(self, "Succès", f"Profil sauvegardé : {Path(filename).name}")
    
    def load_profile(self):
        """Charge profil personnalisé"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Charger Profil", str(self.profiles_dir), "JSON (*.json)"
        )
        
        if filename:
            with open(filename, 'r') as f:
                loaded_params = json.load(f)
            
            self.params.update(loaded_params)
            self.update_ui_from_params()
            self.save_to_shared_file()
            
            QMessageBox.information(self, "Succès", f"Profil chargé : {Path(filename).name}")
    
    def load_default_profile(self):
        """Charge profil par défaut"""
        default_file = self.profiles_dir / "default.json"
        
        if default_file.exists():
            with open(default_file, 'r') as f:
                self.params = json.load(f)
            
            self.update_ui_from_params()
            self.save_to_shared_file()
        else:
            # Créer profil par défaut
            with open(default_file, 'w') as f:
                json.dump(self.params, f, indent=2)
    
    def update_ui_from_params(self):
        """Met à jour l'UI depuis les paramètres"""
        self.fps_slider[1].setValue(self.params["fps"])
        self.exposure_slider[1].setValue(self.params["exposure"])
        self.brightness_slider[1].setValue(self.params["brightness"])
        self.contrast_slider[1].setValue(self.params["contrast"])
        
        self.roi_scale_slider[1].setValue(self.params["roi_scale"])
        
        self.channel_combo.setCurrentText(self.params["ir_channel"])
        self.highlight_threshold_slider[1].setValue(self.params["highlight_threshold"])
        self.median_ksize_slider[1].setValue(self.params["median_ksize"])
        self.adaptive_block_slider[1].setValue(self.params["adaptive_block_size"])
        self.adaptive_c_slider[1].setValue(self.params["adaptive_c"])
        
        self.morph_kernel_slider[1].setValue(self.params["morph_kernel_size"])
        self.morph_open_slider[1].setValue(self.params["morph_open_iter"])
        self.morph_close_slider[1].setValue(self.params["morph_close_iter"])
        
        self.min_area_slider[1].setValue(self.params["min_area"])
        self.max_area_slider[1].setValue(self.params["max_area"])
        self.min_circularity_slider[1].setValue(self.params["min_circularity"])
        self.max_aspect_slider[1].setValue(self.params["max_aspect_ratio"])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = ParameterController()
    controller.show()
    sys.exit(app.exec())
