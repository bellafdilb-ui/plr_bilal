"""
Fenêtre de paramètres pour PLR Analyzer
Version: 1.0.0
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QPushButton, QGroupBox, QLineEdit, QFileDialog, QSlider, QMessageBox
)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


# =====================================================
# GESTIONNAIRE DE CONFIGURATION
# =====================================================
class ConfigManager:
    """Gestion du chargement/sauvegarde de la configuration"""
    
    def __init__(self, config_path: str = "config/default_config.json"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._ensure_config_exists()
        self.load()
    
    def _ensure_config_exists(self):
        """Crée le fichier de config par défaut s'il n'existe pas"""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default_config = {
                "camera": {
                    "index": 0,
                    "width": 640,
                    "height": 480,
                    "fps": 30,
                    "exposure": -6,
                    "gain": 0,
                    "auto_exposure": True
                },
                "detection": {
                    "canny_threshold1": 50,
                    "canny_threshold2": 150,
                    "min_radius": 20,
                    "max_radius": 100,
                    "dp": 1.2,
                    "min_dist": 50,
                    "param1": 50,
                    "param2": 30,
                    "morphology_kernel_size": 5,
                    "gaussian_blur": 5
                },
                "recording": {
                    "save_path": "recordings",
                    "image_format": "png",
                    "auto_save": True,
                    "max_duration": 300
                },
                "advanced": {
                    "log_level": "INFO",
                    "enable_performance_monitor": False,
                    "show_debug_overlay": False,
                    "thread_priority": "normal"
                }
            }
            self.save(default_config)
    
    def load(self) -> Dict[str, Any]:
        """Charge la configuration depuis le fichier JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"Configuration chargée depuis {self.config_path}")
            return self.config
        except Exception as e:
            logger.error(f"Erreur chargement config: {e}")
            return {}
    
    def save(self, config: Dict[str, Any] = None):
        """Sauvegarde la configuration dans le fichier JSON"""
        if config:
            self.config = config
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info(f"Configuration sauvegardée dans {self.config_path}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde config: {e}")
    
    def get(self, section: str, key: str, default=None):
        """Récupère une valeur de configuration"""
        return self.config.get(section, {}).get(key, default)
    
    def set(self, section: str, key: str, value):
        """Définit une valeur de configuration"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value


# =====================================================
# DIALOG PRINCIPAL DES PARAMÈTRES
# =====================================================
class SettingsDialog(QDialog):
    """Fenêtre de paramètres avec onglets"""
    
    settings_changed = Signal(dict)  # Signal émis quand les paramètres changent

    
    def __init__(self, parent=None, config_manager: ConfigManager = None):
        super().__init__(parent)
        self.config_manager = config_manager or ConfigManager()
        self.setWindowTitle("Paramètres - PLR Analyzer")
        self.setMinimumSize(700, 600)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Onglets
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_camera_tab(), "📹 Caméra")
        self.tabs.addTab(self._create_detection_tab(), "🎯 Détection")
        self.tabs.addTab(self._create_recording_tab(), "💾 Enregistrement")
        self.tabs.addTab(self._create_advanced_tab(), "⚙️ Avancé")
        
        layout.addWidget(self.tabs)
        
        # Boutons de validation
        buttons_layout = QHBoxLayout()
        
        self.btn_restore_defaults = QPushButton("🔄 Valeurs par défaut")
        self.btn_restore_defaults.clicked.connect(self.restore_defaults)
        
        self.btn_cancel = QPushButton("❌ Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_apply = QPushButton("✅ Appliquer")
        self.btn_apply.clicked.connect(self.apply_settings)
        
        self.btn_ok = QPushButton("💾 OK")
        self.btn_ok.clicked.connect(self.save_and_close)
        self.btn_ok.setDefault(True)
        
        buttons_layout.addWidget(self.btn_restore_defaults)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_apply)
        buttons_layout.addWidget(self.btn_ok)
        
        layout.addLayout(buttons_layout)
    
    # =================================================
    # ONGLET CAMÉRA
    # =================================================
    def _create_camera_tab(self) -> QWidget:
        """Crée l'onglet des paramètres caméra"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Groupe: Sélection caméra
        group_selection = QGroupBox("Sélection de la caméra")
        form_selection = QFormLayout()
        
        self.spin_camera_index = QSpinBox()
        self.spin_camera_index.setRange(0, 10)
        self.spin_camera_index.setToolTip("Index de la caméra (0 = caméra par défaut)")
        form_selection.addRow("Index de la caméra:", self.spin_camera_index)
        
        group_selection.setLayout(form_selection)
        layout.addWidget(group_selection)
        
        # Groupe: Résolution
        group_resolution = QGroupBox("Résolution et FPS")
        form_resolution = QFormLayout()
        
        self.spin_width = QSpinBox()
        self.spin_width.setRange(320, 1920)
        self.spin_width.setSingleStep(160)
        self.spin_width.setSuffix(" px")
        form_resolution.addRow("Largeur:", self.spin_width)
        
        self.spin_height = QSpinBox()
        self.spin_height.setRange(240, 1080)
        self.spin_height.setSingleStep(120)
        self.spin_height.setSuffix(" px")
        form_resolution.addRow("Hauteur:", self.spin_height)
        
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 120)
        self.spin_fps.setSuffix(" FPS")
        form_resolution.addRow("Images/seconde:", self.spin_fps)
        
        group_resolution.setLayout(form_resolution)
        layout.addWidget(group_resolution)
        
        # Groupe: Exposition et gain
        group_exposure = QGroupBox("Exposition et Gain")
        form_exposure = QFormLayout()
        
        self.check_auto_exposure = QCheckBox("Exposition automatique")
        form_exposure.addRow(self.check_auto_exposure)
        
        self.spin_exposure = QSpinBox()
        self.spin_exposure.setRange(-13, 0)
        self.spin_exposure.setToolTip("Temps d'exposition (valeurs négatives = plus rapide)")
        form_exposure.addRow("Exposition:", self.spin_exposure)
        
        self.spin_gain = QSpinBox()
        self.spin_gain.setRange(0, 100)
        self.spin_gain.setToolTip("Gain ISO de la caméra")
        form_exposure.addRow("Gain:", self.spin_gain)
        
        # Désactiver exposition/gain si auto
        self.check_auto_exposure.toggled.connect(
            lambda checked: [
                self.spin_exposure.setEnabled(not checked),
                self.spin_gain.setEnabled(not checked)
            ]
        )
        
        group_exposure.setLayout(form_exposure)
        layout.addWidget(group_exposure)
        
        layout.addStretch()
        return widget
    
    # =================================================
    # ONGLET DÉTECTION
    # =================================================
    def _create_detection_tab(self) -> QWidget:
        """Crée l'onglet des paramètres de détection"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Groupe: Détection des contours (Canny)
        group_canny = QGroupBox("Détection de contours (Canny)")
        form_canny = QFormLayout()
        
        self.spin_canny_low = QSpinBox()
        self.spin_canny_low.setRange(1, 255)
        self.spin_canny_low.setToolTip("Seuil bas pour la détection de contours")
        form_canny.addRow("Seuil bas:", self.spin_canny_low)
        
        self.spin_canny_high = QSpinBox()
        self.spin_canny_high.setRange(1, 255)
        self.spin_canny_high.setToolTip("Seuil haut pour la détection de contours")
        form_canny.addRow("Seuil haut:", self.spin_canny_high)
        
        group_canny.setLayout(form_canny)
        layout.addWidget(group_canny)
        
        # Groupe: Détection des cercles (Hough)
        group_hough = QGroupBox("Détection de la pupille (Hough Transform)")
        form_hough = QFormLayout()
        
        self.spin_min_radius = QSpinBox()
        self.spin_min_radius.setRange(5, 200)
        self.spin_min_radius.setSuffix(" px")
        form_hough.addRow("Rayon minimum:", self.spin_min_radius)
        
        self.spin_max_radius = QSpinBox()
        self.spin_max_radius.setRange(10, 300)
        self.spin_max_radius.setSuffix(" px")
        form_hough.addRow("Rayon maximum:", self.spin_max_radius)
        
        self.spin_dp = QDoubleSpinBox()
        self.spin_dp.setRange(1.0, 3.0)
        self.spin_dp.setSingleStep(0.1)
        self.spin_dp.setDecimals(1)
        self.spin_dp.setToolTip("Résolution de l'accumulateur (1 = résolution image)")
        form_hough.addRow("Résolution (dp):", self.spin_dp)
        
        self.spin_min_dist = QSpinBox()
        self.spin_min_dist.setRange(10, 200)
        self.spin_min_dist.setSuffix(" px")
        self.spin_min_dist.setToolTip("Distance minimale entre centres de cercles")
        form_hough.addRow("Distance min:", self.spin_min_dist)
        
        self.spin_param1 = QSpinBox()
        self.spin_param1.setRange(10, 300)
        self.spin_param1.setToolTip("Seuil haut pour Canny interne")
        form_hough.addRow("Param1:", self.spin_param1)
        
        self.spin_param2 = QSpinBox()
        self.spin_param2.setRange(10, 200)
        self.spin_param2.setToolTip("Seuil d'accumulation pour centres de cercles")
        form_hough.addRow("Param2:", self.spin_param2)
        
        group_hough.setLayout(form_hough)
        layout.addWidget(group_hough)
        
        # Groupe: Prétraitement
        group_preproc = QGroupBox("Prétraitement de l'image")
        form_preproc = QFormLayout()
        
        self.spin_gaussian = QSpinBox()
        self.spin_gaussian.setRange(1, 15)
        self.spin_gaussian.setSingleStep(2)
        self.spin_gaussian.setSuffix(" px")
        self.spin_gaussian.setToolTip("Taille du noyau de flou gaussien (impair)")
        form_preproc.addRow("Flou gaussien:", self.spin_gaussian)
        
        self.spin_morphology = QSpinBox()
        self.spin_morphology.setRange(1, 15)
        self.spin_morphology.setSingleStep(2)
        self.spin_morphology.setSuffix(" px")
        self.spin_morphology.setToolTip("Taille du noyau morphologique (impair)")
        form_preproc.addRow("Noyau morpho:", self.spin_morphology)
        
        group_preproc.setLayout(form_preproc)
        layout.addWidget(group_preproc)
        
        layout.addStretch()
        return widget
    
    # =================================================
    # ONGLET ENREGISTREMENT
    # =================================================
    def _create_recording_tab(self) -> QWidget:
        """Crée l'onglet des paramètres d'enregistrement"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Groupe: Dossier de sauvegarde
        group_path = QGroupBox("Dossier de sauvegarde")
        layout_path = QVBoxLayout()
        
        path_layout = QHBoxLayout()
        self.edit_save_path = QLineEdit()
        self.edit_save_path.setPlaceholderText("Chemin du dossier...")
        
        self.btn_browse = QPushButton("📁 Parcourir")
        self.btn_browse.clicked.connect(self.browse_save_path)
        
        path_layout.addWidget(self.edit_save_path)
        path_layout.addWidget(self.btn_browse)
        layout_path.addLayout(path_layout)
        
        group_path.setLayout(layout_path)
        layout.addWidget(group_path)
        
        # Groupe: Format et options
        group_format = QGroupBox("Format et options")
        form_format = QFormLayout()
        
        self.combo_image_format = QComboBox()
        self.combo_image_format.addItems(["png", "jpg", "bmp", "tiff"])
        self.combo_image_format.setToolTip("Format d'enregistrement des images")
        form_format.addRow("Format d'image:", self.combo_image_format)
        
        self.check_auto_save = QCheckBox("Enregistrement automatique")
        self.check_auto_save.setToolTip("Sauvegarder automatiquement les sessions")
        form_format.addRow(self.check_auto_save)
        
        self.spin_max_duration = QSpinBox()
        self.spin_max_duration.setRange(10, 3600)
        self.spin_max_duration.setSuffix(" secondes")
        self.spin_max_duration.setToolTip("Durée maximale d'une session")
        form_format.addRow("Durée max session:", self.spin_max_duration)
        
        group_format.setLayout(form_format)
        layout.addWidget(group_format)
        
        layout.addStretch()
        return widget
    
    # =================================================
    # ONGLET AVANCÉ
    # =================================================
    def _create_advanced_tab(self) -> QWidget:
        """Crée l'onglet des paramètres avancés"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Groupe: Logs et debug
        group_logs = QGroupBox("Journalisation et Debug")
        form_logs = QFormLayout()
        
        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.combo_log_level.setToolTip("Niveau de détail des logs")
        form_logs.addRow("Niveau de log:", self.combo_log_level)
        
        self.check_performance = QCheckBox("Moniteur de performances")
        self.check_performance.setToolTip("Afficher les FPS et latences")
        form_logs.addRow(self.check_performance)
        
        self.check_debug_overlay = QCheckBox("Overlay de debug")
        self.check_debug_overlay.setToolTip("Afficher les infos de debug sur l'image")
        form_logs.addRow(self.check_debug_overlay)
        
        group_logs.setLayout(form_logs)
        layout.addWidget(group_logs)
        
        # Groupe: Performances
        group_perf = QGroupBox("Performances")
        form_perf = QFormLayout()
        
        self.combo_thread_priority = QComboBox()
        self.combo_thread_priority.addItems(["low", "normal", "high"])
        self.combo_thread_priority.setToolTip("Priorité du thread de traitement")
        form_perf.addRow("Priorité thread:", self.combo_thread_priority)
        
        group_perf.setLayout(form_perf)
        layout.addWidget(group_perf)
        
        # Bouton d'information
        info_label = QLabel(
            "⚠️ <b>Attention :</b> Modifier ces paramètres peut affecter les performances.<br>"
            "Consultez la documentation avant de modifier."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { background-color: #fff3cd; padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)
        
        layout.addStretch()
        return widget
    
    # =================================================
    # GESTION DES PARAMÈTRES
    # =================================================
    def load_settings(self):
        """Charge les paramètres depuis la configuration"""
        config = self.config_manager.config
        
        # Caméra
        cam = config.get("camera", {})
        self.spin_camera_index.setValue(cam.get("index", 0))
        self.spin_width.setValue(cam.get("width", 640))
        self.spin_height.setValue(cam.get("height", 480))
        self.spin_fps.setValue(cam.get("fps", 30))
        self.spin_exposure.setValue(cam.get("exposure", -6))
        self.spin_gain.setValue(cam.get("gain", 0))
        self.check_auto_exposure.setChecked(cam.get("auto_exposure", True))
        
        # Détection
        det = config.get("detection", {})
        self.spin_canny_low.setValue(det.get("canny_threshold1", 50))
        self.spin_canny_high.setValue(det.get("canny_threshold2", 150))
        self.spin_min_radius.setValue(det.get("min_radius", 20))
        self.spin_max_radius.setValue(det.get("max_radius", 100))
        self.spin_dp.setValue(det.get("dp", 1.2))
        self.spin_min_dist.setValue(det.get("min_dist", 50))
        self.spin_param1.setValue(det.get("param1", 50))
        self.spin_param2.setValue(det.get("param2", 30))
        self.spin_morphology.setValue(det.get("morphology_kernel_size", 5))
        self.spin_gaussian.setValue(det.get("gaussian_blur", 5))
        
        # Enregistrement
        rec = config.get("recording", {})
        self.edit_save_path.setText(rec.get("save_path", "recordings"))
        self.combo_image_format.setCurrentText(rec.get("image_format", "png"))
        self.check_auto_save.setChecked(rec.get("auto_save", True))
        self.spin_max_duration.setValue(rec.get("max_duration", 300))
        
        # Avancé
        adv = config.get("advanced", {})
        self.combo_log_level.setCurrentText(adv.get("log_level", "INFO"))
        self.check_performance.setChecked(adv.get("enable_performance_monitor", False))
        self.check_debug_overlay.setChecked(adv.get("show_debug_overlay", False))
        self.combo_thread_priority.setCurrentText(adv.get("thread_priority", "normal"))
    
    def get_settings(self) -> Dict[str, Any]:
        """Récupère tous les paramètres actuels"""
        return {
            "camera": {
                "index": self.spin_camera_index.value(),
                "width": self.spin_width.value(),
                "height": self.spin_height.value(),
                "fps": self.spin_fps.value(),
                "exposure": self.spin_exposure.value(),
                "gain": self.spin_gain.value(),
                "auto_exposure": self.check_auto_exposure.isChecked()
            },
            "detection": {
                "canny_threshold1": self.spin_canny_low.value(),
                "canny_threshold2": self.spin_canny_high.value(),
                "min_radius": self.spin_min_radius.value(),
                "max_radius": self.spin_max_radius.value(),
                "dp": self.spin_dp.value(),
                "min_dist": self.spin_min_dist.value(),
                "param1": self.spin_param1.value(),
                "param2": self.spin_param2.value(),
                "morphology_kernel_size": self.spin_morphology.value(),
                "gaussian_blur": self.spin_gaussian.value()
            },
            "recording": {
                "save_path": self.edit_save_path.text(),
                "image_format": self.combo_image_format.currentText(),
                "auto_save": self.check_auto_save.isChecked(),
                "max_duration": self.spin_max_duration.value()
            },
            "advanced": {
                "log_level": self.combo_log_level.currentText(),
                "enable_performance_monitor": self.check_performance.isChecked(),
                "show_debug_overlay": self.check_debug_overlay.isChecked(),
                "thread_priority": self.combo_thread_priority.currentText()
            }
        }
    
    def apply_settings(self):
        """Applique les paramètres sans fermer la fenêtre"""
        settings = self.get_settings()
        self.settings_changed.emit(settings)
        logger.info("Paramètres appliqués")
    
    def save_and_close(self):
        """Sauvegarde les paramètres et ferme la fenêtre"""
        settings = self.get_settings()
        self.config_manager.save(settings)
        self.settings_changed.emit(settings)
        logger.info("Paramètres sauvegardés et appliqués")
        self.accept()
    
    def restore_defaults(self):
        """Restaure les paramètres par défaut"""
        reply = QMessageBox.question(
            self,
            "Restaurer les valeurs par défaut",
            "Êtes-vous sûr de vouloir restaurer les valeurs par défaut ?\n"
            "Cette action ne peut pas être annulée.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Supprimer le fichier de config et recharger
            if self.config_manager.config_path.exists():
                self.config_manager.config_path.unlink()
            self.config_manager._ensure_config_exists()
            self.config_manager.load()
            self.load_settings()
            logger.info("Paramètres par défaut restaurés")
    
    def browse_save_path(self):
        """Ouvre un dialogue pour sélectionner le dossier de sauvegarde"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le dossier de sauvegarde",
            self.edit_save_path.text()
        )
        if folder:
            self.edit_save_path.setText(folder)


# =====================================================
# TEST DU MODULE
# =====================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app = QApplication(sys.argv)
    
    dialog = SettingsDialog()
    
    # Connexion du signal pour tester
    def on_settings_changed(settings):
        print("\n🔧 Nouveaux paramètres:")
        print(json.dumps(settings, indent=2))
    
    dialog.settings_changed.connect(on_settings_changed)
    
    dialog.show()
    sys.exit(app.exec())
