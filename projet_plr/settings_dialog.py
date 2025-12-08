"""
settings_dialog.py
==================
Paramètres (Avec gestion Clinique & Macros).
"""

import json
from pathlib import Path
from typing import Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QGroupBox, 
    QLineEdit, QFileDialog, QListWidget, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from db_manager import DatabaseManager

class ConfigManager:
    # (Code inchangé pour la gestion du fichier JSON...)
    def __init__(self, config_path="config/default_config.json"):
        self.config_path = Path(config_path)
        self.config = {}
        self._ensure_exists()
        self.load()
    def _ensure_exists(self):
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.save({"camera": {"index": 0, "width": 640, "height": 480}, 
                       "detection": {"canny_threshold1": 50, "gaussian_blur": 5, "roi_width":400, "roi_height":400},
                       "protocol": {"baseline_duration": 2.0, "flash_duration_ms": 200},
                       "recording": {"save_path": "recordings"}})
    def load(self):
        try: self.config = json.loads(self.config_path.read_text(encoding='utf-8'))
        except: pass
    def save(self, c=None):
        if c: self.config = c
        try: self.config_path.write_text(json.dumps(self.config, indent=4), encoding='utf-8')
        except: pass
    def get(self, s, k=None, d=None): return self.config.get(s, {}).get(k, d) if k else self.config.get(s, {})

class SettingsDialog(QDialog):
    settings_changed = Signal(dict)

    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.config_manager = config_manager or ConfigManager()
        self.db = DatabaseManager()
        self.setWindowTitle("Paramètres Globaux")
        self.resize(900, 700)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        self.tabs.addTab(self._tab_protocol(), "🧪 Protocole")
        self.tabs.addTab(self._tab_camera(), "📹 Caméra")
        self.tabs.addTab(self._tab_detection(), "🎯 Détection")
        self.tabs.addTab(self._tab_clinic(), "🏥 Clinique / PDF")  # NEW
        self.tabs.addTab(self._tab_macros(), "📝 Commentaires")   # NEW
        
        layout.addWidget(self.tabs)
        
        btns = QHBoxLayout()
        btn_apply = QPushButton("Appliquer"); btn_apply.clicked.connect(self.apply_settings)
        btn_ok = QPushButton("OK"); btn_ok.clicked.connect(self.save_and_close)
        btns.addStretch(); btns.addWidget(btn_apply); btns.addWidget(btn_ok)
        layout.addLayout(btns)

    # --- ONGLETS EXISTANTS ---
    def _tab_protocol(self):
        w = QWidget(); l = QFormLayout(w)
        self.spin_baseline = QDoubleSpinBox()
        self.spin_flash_dur = QSpinBox(); self.spin_flash_dur.setRange(10,5000)
        l.addRow("Baseline (s):", self.spin_baseline)
        l.addRow("Durée Flash (ms):", self.spin_flash_dur)
        return w

    def _tab_camera(self):
        w = QWidget(); l = QFormLayout(w)
        self.spin_idx = QSpinBox()
        l.addRow("Index Caméra:", self.spin_idx)
        return w

    def _tab_detection(self):
        w = QWidget(); l = QFormLayout(w)
        self.spin_canny = QSpinBox(); self.spin_canny.setRange(0, 255)
        self.spin_blur = QSpinBox(); self.spin_blur.setRange(1, 31); self.spin_blur.setSingleStep(2)
        self.spin_rw = QSpinBox(); self.spin_rw.setRange(50, 4000)
        self.spin_rh = QSpinBox(); self.spin_rh.setRange(50, 4000)
        self.spin_offx = QSpinBox(); self.spin_offx.setRange(-2000, 2000)
        self.spin_offy = QSpinBox(); self.spin_offy.setRange(-2000, 2000)
        
        l.addRow("Seuil Canny:", self.spin_canny)
        l.addRow("Flou Gaussien:", self.spin_blur)
        l.addRow("Largeur ROI:", self.spin_rw)
        l.addRow("Hauteur ROI:", self.spin_rh)
        l.addRow("Offset X:", self.spin_offx)
        l.addRow("Offset Y:", self.spin_offy)
        return w

    # --- NOUVEAUX ONGLETS ---
    def _tab_clinic(self):
        w = QWidget(); l = QFormLayout(w)
        self.inp_clin_name = QLineEdit()
        self.inp_clin_addr = QLineEdit()
        self.inp_clin_doc = QLineEdit()
        self.inp_clin_phone = QLineEdit()
        self.inp_clin_logo = QLineEdit()
        btn_logo = QPushButton("Choisir Logo..."); btn_logo.clicked.connect(self._pick_logo)
        
        l.addRow("Nom Clinique:", self.inp_clin_name)
        l.addRow("Adresse:", self.inp_clin_addr)
        l.addRow("Téléphone:", self.inp_clin_phone)
        l.addRow("Praticien:", self.inp_clin_doc)
        
        h = QHBoxLayout()
        h.addWidget(self.inp_clin_logo); h.addWidget(btn_logo)
        l.addRow("Logo (Image):", h)
        return w

    def _pick_logo(self):
        f, _ = QFileDialog.getOpenFileName(self, "Logo", "", "Images (*.png *.jpg)")
        if f: self.inp_clin_logo.setText(f)

    def _tab_macros(self):
        w = QWidget(); l = QVBoxLayout(w)
        
        h_add = QHBoxLayout()
        self.inp_macro_title = QLineEdit(); self.inp_macro_title.setPlaceholderText("Titre (ex: Normal)")
        self.inp_macro_content = QLineEdit(); self.inp_macro_content.setPlaceholderText("Texte (ex: Réflexe vif et symétrique, pas d'anomalie)")
        btn_add = QPushButton("Ajouter"); btn_add.clicked.connect(self._add_macro)
        h_add.addWidget(self.inp_macro_title); h_add.addWidget(self.inp_macro_content); h_add.addWidget(btn_add)
        
        self.list_macros = QListWidget()
        btn_del = QPushButton("Supprimer Sélection"); btn_del.clicked.connect(self._del_macro)
        
        l.addLayout(h_add)
        l.addWidget(self.list_macros)
        l.addWidget(btn_del)
        
        # Charger liste
        self._refresh_macros()
        return w

    def _refresh_macros(self):
        self.list_macros.clear()
        macros = self.db.get_macros()
        for m in macros:
            self.list_macros.addItem(f"{m['id']} : {m['title']} - {m['content']}")

    def _add_macro(self):
        t, c = self.inp_macro_title.text(), self.inp_macro_content.text()
        if t and c:
            self.db.add_macro(t, c)
            self._refresh_macros()
            self.inp_macro_title.clear(); self.inp_macro_content.clear()

    def _del_macro(self):
        item = self.list_macros.currentItem()
        if item:
            mid = int(item.text().split(" : ")[0])
            self.db.delete_macro(mid)
            self._refresh_macros()

    def load_settings(self):
        # JSON
        c = self.config_manager.config
        p = c.get("protocol", {})
        self.spin_baseline.setValue(p.get("baseline_duration", 2.0))
        self.spin_flash_dur.setValue(p.get("flash_duration_ms", 200))
        
        cm = c.get("camera", {})
        self.spin_idx.setValue(cm.get("index", 0))
        
        d = c.get("detection", {})
        self.spin_canny.setValue(d.get("canny_threshold1", 50))
        self.spin_blur.setValue(d.get("gaussian_blur", 5))
        self.spin_rw.setValue(d.get("roi_width", 400))
        self.spin_rh.setValue(d.get("roi_height", 400))
        self.spin_offx.setValue(d.get("roi_offset_x", 0))
        self.spin_offy.setValue(d.get("roi_offset_y", 0))
        
        # SQL (Clinique)
        info = self.db.get_clinic_info()
        self.inp_clin_name.setText(info.get('name', ''))
        self.inp_clin_addr.setText(info.get('address', ''))
        self.inp_clin_doc.setText(info.get('doctor_name', ''))
        self.inp_clin_phone.setText(info.get('phone', ''))
        self.inp_clin_logo.setText(info.get('logo_path', ''))

    def get_settings(self):
        return {
            "protocol": {
                "baseline_duration": self.spin_baseline.value(),
                "flash_duration_ms": self.spin_flash_dur.value(),
                "response_duration": 5.0, "flash_count": 1
            },
            "camera": {"index": self.spin_idx.value(), "width": 640, "height": 480},
            "detection": {
                "canny_threshold1": self.spin_canny.value(),
                "gaussian_blur": self.spin_blur.value(),
                "roi_width": self.spin_rw.value(),
                "roi_height": self.spin_rh.value(),
                "roi_offset_x": self.spin_offx.value(),
                "roi_offset_y": self.spin_offy.value()
            },
            "recording": {"save_path": "recordings"}
        }

    def apply_settings(self):
        self.settings_changed.emit(self.get_settings())
        # Save SQL
        self.db.set_clinic_info(
            self.inp_clin_name.text(), self.inp_clin_addr.text(),
            self.inp_clin_phone.text(), "", self.inp_clin_doc.text(),
            self.inp_clin_logo.text()
        )

    def save_and_close(self):
        self.apply_settings()
        self.config_manager.save(self.get_settings())
        self.accept()