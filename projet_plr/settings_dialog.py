"""
Fenêtre de paramètres pour PLR Analyzer
Version: 1.3.1 (Fix: Ajout méthode set)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QPushButton, QGroupBox, QLineEdit, QFileDialog, QMessageBox
)

from PySide6.QtCore import Qt, Signal

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
                "protocol": {
                    "baseline_duration": 2.0,
                    "flash_count": 1,
                    "flash_duration_ms": 200,
                    "response_duration": 5.0
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
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            return self.config
        except Exception as e:
            logger.error(f"Erreur chargement config: {e}")
            return {}
    
    def save(self, config: Dict[str, Any] = None):
        if config:
            self.config = config
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
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
    
    settings_changed = Signal(dict)

    def __init__(self, parent=None, config_manager: ConfigManager = None):
        super().__init__(parent)
        self.config_manager = config_manager or ConfigManager()
        self.setWindowTitle("Paramètres - PLR Analyzer")
        self.setMinimumSize(750, 650)
        self.setup_ui()
        self.apply_stylesheet()
        self.load_settings()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_protocol_tab(), "🧪 Protocole")
        self.tabs.addTab(self._create_camera_tab(), "📹 Caméra")
        self.tabs.addTab(self._create_detection_tab(), "🎯 Détection")
        self.tabs.addTab(self._create_recording_tab(), "💾 Enregistrement")
        self.tabs.addTab(self._create_advanced_tab(), "⚙️ Avancé")
        
        layout.addWidget(self.tabs)
        
        # Boutons
        buttons_layout = QHBoxLayout()
        self.btn_restore = QPushButton("🔄 Valeurs par défaut")
        self.btn_restore.clicked.connect(self.restore_defaults)
        self.btn_cancel = QPushButton("❌ Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply = QPushButton("✅ Appliquer")
        self.btn_apply.clicked.connect(self.apply_settings)
        self.btn_ok = QPushButton("💾 OK")
        self.btn_ok.clicked.connect(self.save_and_close)
        self.btn_ok.setDefault(True)
        
        buttons_layout.addWidget(self.btn_restore)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_apply)
        buttons_layout.addWidget(self.btn_ok)
        layout.addLayout(buttons_layout)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog, QWidget { background-color: #ffffff; color: #000000; font-size: 10pt; }
            QGroupBox { font-weight: bold; border: 1px solid #cccccc; border-radius: 5px; margin-top: 10px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #333333; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #f8f9fa; border: 1px solid #ced4da; padding: 6px; border-radius: 4px; }
            QPushButton { background-color: #e2e6ea; border: 1px solid #dae0e5; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #dbe2ef; }
            QPushButton[text="✅ Appliquer"], QPushButton[text="💾 OK"] { background-color: #007bff; color: white; border: 1px solid #0056b3; }
            QTabWidget::pane { border: 1px solid #cccccc; background-color: #ffffff; }
            QTabBar::tab { background: #f1f3f5; color: #495057; padding: 10px 15px; border: 1px solid #dee2e6; }
            QTabBar::tab:selected { background: #ffffff; color: #007bff; border-bottom: 2px solid #007bff; font-weight: bold; }
        """)

    # --- NOUVEL ONGLET PROTOCOLE ---
    def _create_protocol_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Configuration du Test PLR")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.spin_baseline = QDoubleSpinBox()
        self.spin_baseline.setRange(0.5, 30.0)
        self.spin_baseline.setSingleStep(0.5)
        self.spin_baseline.setSuffix(" s")
        form.addRow("Durée Baseline (Repos):", self.spin_baseline)
        
        self.spin_flash_count = QSpinBox()
        self.spin_flash_count.setRange(1, 10)
        self.spin_flash_count.setSuffix(" flash(s)")
        form.addRow("Nombre de Flashs:", self.spin_flash_count)
        
        self.spin_flash_duration = QSpinBox()
        self.spin_flash_duration.setRange(10, 5000)
        self.spin_flash_duration.setSingleStep(10)
        self.spin_flash_duration.setSuffix(" ms")
        form.addRow("Durée du Flash:", self.spin_flash_duration)
        
        self.spin_response = QDoubleSpinBox()
        self.spin_response.setRange(1.0, 60.0)
        self.spin_response.setSingleStep(0.5)
        self.spin_response.setSuffix(" s")
        form.addRow("Durée Réponse (par cycle):", self.spin_response)
        
        group.setLayout(form)
        layout.addWidget(group)
        
        info_label = QLabel("Le test suivra la séquence : Baseline ➔ [Flash ➔ Réponse] x N")
        info_label.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        return widget

    # --- AUTRES ONGLETS ---
    def _create_camera_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group_sel = QGroupBox("Caméra")
        form_sel = QFormLayout()
        self.spin_camera_index = QSpinBox()
        form_sel.addRow("Index:", self.spin_camera_index)
        group_sel.setLayout(form_sel)
        layout.addWidget(group_sel)
        
        group_res = QGroupBox("Image")
        form_res = QFormLayout()
        self.spin_width = QSpinBox()
        self.spin_width.setRange(320, 3840)
        self.spin_width.setSingleStep(160)
        self.spin_height = QSpinBox()
        self.spin_height.setRange(240, 2160)
        self.spin_height.setSingleStep(120)
        self.spin_fps = QSpinBox()
        form_res.addRow("Largeur:", self.spin_width)
        form_res.addRow("Hauteur:", self.spin_height)
        form_res.addRow("FPS:", self.spin_fps)
        group_res.setLayout(form_res)
        layout.addWidget(group_res)
        
        group_exp = QGroupBox("Exposition")
        form_exp = QFormLayout()
        self.check_auto_exposure = QCheckBox("Auto")
        self.spin_exposure = QSpinBox()
        self.spin_exposure.setRange(-15, 0)
        self.spin_gain = QSpinBox()
        form_exp.addRow("Mode Auto:", self.check_auto_exposure)
        form_exp.addRow("Exposition:", self.spin_exposure)
        form_exp.addRow("Gain:", self.spin_gain)
        group_exp.setLayout(form_exp)
        layout.addWidget(group_exp)
        
        self.check_auto_exposure.toggled.connect(lambda c: [self.spin_exposure.setEnabled(not c), self.spin_gain.setEnabled(not c)])
        layout.addStretch()
        return widget

    def _create_detection_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group_canny = QGroupBox("Canny (Contours)")
        form_canny = QFormLayout()
        self.spin_canny_low = QSpinBox()
        self.spin_canny_low.setRange(1, 255)
        self.spin_canny_high = QSpinBox()
        self.spin_canny_high.setRange(1, 255)
        form_canny.addRow("Seuil Bas:", self.spin_canny_low)
        form_canny.addRow("Seuil Haut:", self.spin_canny_high)
        group_canny.setLayout(form_canny)
        layout.addWidget(group_canny)
        
        group_hough = QGroupBox("Hough (Cercles)")
        form_hough = QFormLayout()
        self.spin_min_radius = QSpinBox()
        self.spin_max_radius = QSpinBox()
        self.spin_max_radius.setRange(10, 500)
        self.spin_dp = QDoubleSpinBox()
        self.spin_min_dist = QSpinBox()
        self.spin_param1 = QSpinBox()
        self.spin_param1.setRange(1, 300)
        self.spin_param2 = QSpinBox()
        form_hough.addRow("Rayon Min:", self.spin_min_radius)
        form_hough.addRow("Rayon Max:", self.spin_max_radius)
        form_hough.addRow("DP:", self.spin_dp)
        form_hough.addRow("Dist Min:", self.spin_min_dist)
        form_hough.addRow("Param1:", self.spin_param1)
        form_hough.addRow("Param2:", self.spin_param2)
        group_hough.setLayout(form_hough)
        layout.addWidget(group_hough)
        
        group_pre = QGroupBox("Prétraitement")
        form_pre = QFormLayout()
        self.spin_gaussian = QSpinBox()
        self.spin_morphology = QSpinBox()
        form_pre.addRow("Flou:", self.spin_gaussian)
        form_pre.addRow("Morpho:", self.spin_morphology)
        group_pre.setLayout(form_pre)
        layout.addWidget(group_pre)
        
        layout.addStretch()
        return widget

    def _create_recording_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Sauvegarde")
        form = QFormLayout()
        self.edit_save_path = QLineEdit()
        btn = QPushButton("...")
        btn.clicked.connect(self.browse_save_path)
        h = QHBoxLayout()
        h.addWidget(self.edit_save_path)
        h.addWidget(btn)
        
        self.combo_image_format = QComboBox()
        self.combo_image_format.addItems(["png", "jpg"])
        self.check_auto_save = QCheckBox("Auto-Save")
        self.spin_max_duration = QSpinBox()
        self.spin_max_duration.setRange(10, 3600)
        
        layout.addWidget(group)
        group.setLayout(QVBoxLayout())
        group.layout().addLayout(h)
        group.layout().addWidget(QLabel("Format:"))
        group.layout().addWidget(self.combo_image_format)
        group.layout().addWidget(self.check_auto_save)
        group.layout().addWidget(QLabel("Durée Max (s):"))
        group.layout().addWidget(self.spin_max_duration)
        
        layout.addStretch()
        return widget

    def _create_advanced_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("Debug")
        form = QFormLayout()
        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["INFO", "DEBUG"])
        self.check_performance = QCheckBox("Perf Monitor")
        self.check_debug_overlay = QCheckBox("Overlay Debug")
        self.combo_thread_priority = QComboBox()
        self.combo_thread_priority.addItems(["normal", "high"])
        
        form.addRow("Logs:", self.combo_log_level)
        form.addRow("Priorité:", self.combo_thread_priority)
        form.addRow(self.check_performance)
        form.addRow(self.check_debug_overlay)
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- LOGIQUE ---
    def load_settings(self):
        conf = self.config_manager.config
        
        # Protocol
        prot = conf.get("protocol", {})
        self.spin_baseline.setValue(prot.get("baseline_duration", 2.0))
        self.spin_flash_count.setValue(prot.get("flash_count", 1))
        self.spin_flash_duration.setValue(prot.get("flash_duration_ms", 200))
        self.spin_response.setValue(prot.get("response_duration", 5.0))
        
        # Camera
        cam = conf.get("camera", {})
        self.spin_camera_index.setValue(cam.get("index", 0))
        self.spin_width.setValue(cam.get("width", 640))
        self.spin_height.setValue(cam.get("height", 480))
        self.spin_fps.setValue(cam.get("fps", 30))
        self.spin_exposure.setValue(cam.get("exposure", -6))
        self.spin_gain.setValue(cam.get("gain", 0))
        self.check_auto_exposure.setChecked(cam.get("auto_exposure", True))
        
        # Detection
        det = conf.get("detection", {})
        self.spin_canny_low.setValue(det.get("canny_threshold1", 50))
        self.spin_canny_high.setValue(det.get("canny_threshold2", 150))
        self.spin_min_radius.setValue(det.get("min_radius", 20))
        self.spin_max_radius.setValue(det.get("max_radius", 100))
        self.spin_dp.setValue(det.get("dp", 1.2))
        self.spin_min_dist.setValue(det.get("min_dist", 50))
        self.spin_param1.setValue(det.get("param1", 50))
        self.spin_param2.setValue(det.get("param2", 30))
        self.spin_gaussian.setValue(det.get("gaussian_blur", 5))
        self.spin_morphology.setValue(det.get("morphology_kernel_size", 5))
        
        # Rec / Adv
        self.edit_save_path.setText(conf.get("recording", {}).get("save_path", "recordings"))

    def get_settings(self) -> Dict[str, Any]:
        return {
            "protocol": {
                "baseline_duration": self.spin_baseline.value(),
                "flash_count": self.spin_flash_count.value(),
                "flash_duration_ms": self.spin_flash_duration.value(),
                "response_duration": self.spin_response.value()
            },
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
                "gaussian_blur": self.spin_gaussian.value(),
                "morphology_kernel_size": self.spin_morphology.value()
            },
            "recording": {
                "save_path": self.edit_save_path.text()
            },
            "advanced": {}
        }

    def apply_settings(self):
        self.settings_changed.emit(self.get_settings())
    
    def save_and_close(self):
        s = self.get_settings()
        self.config_manager.save(s)
        self.settings_changed.emit(s)
        self.accept()
        
    def restore_defaults(self):
        if self.config_manager.config_path.exists():
            self.config_manager.config_path.unlink()
        self.config_manager._ensure_config_exists()
        self.config_manager.load()
        self.load_settings()

    def browse_save_path(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier", self.edit_save_path.text())
        if d: self.edit_save_path.setText(d)

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    d = SettingsDialog()
    d.settings_changed.connect(lambda s: print(json.dumps(s, indent=2)))
    d.show()
    sys.exit(app.exec())