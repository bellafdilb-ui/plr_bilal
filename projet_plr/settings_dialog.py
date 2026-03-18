"""
settings_dialog.py
==================
Paramètres V4.1 (Ajout Default Flash Color).
"""

import json
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox,
    QLineEdit, QFileDialog, QListWidget, QMessageBox, QComboBox, QCheckBox,
    QSlider
)
from PySide6.QtCore import Qt, Signal
from db_manager import DatabaseManager

class ConfigManager:
    def __init__(self, config_path="config/default_config.json"):
        self.config_path = Path(config_path)
        self.config = {}
        self._ensure_exists()
        self.load()
    
    def _ensure_exists(self):
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default_conf = {
                "general": {"language": "fr", "enable_beep": True},
                "camera": {"index": 0, "width": 640, "height": 480}, 
                "detection": {"canny_threshold1": 50, "gaussian_blur": 5, "roi_width":400, "roi_height":400},
                "protocol": {"flash_delay_s": 2, "flash_duration_ms": 200, "response_duration": 5.0, "flash_count": 1, "default_color": "WHITE"},
                "recording": {"save_path": "recordings"}
            }
            self.save(default_conf)
            
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
        self.setWindowTitle(self.tr("Paramètres Globaux"))
        self.resize(900, 700)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_general(), self.tr("🌍 Général"))
        self.tabs.addTab(self._tab_protocol(), self.tr("🧪 Protocole"))
        self.tabs.addTab(self._tab_camera(), self.tr("📹 Caméra"))
        self.tabs.addTab(self._tab_detection(), self.tr("🎯 Détection"))
        self.tabs.addTab(self._tab_clinic(), self.tr("🏥 Clinique"))
        self.tabs.addTab(self._tab_macros(), self.tr("📝 Macros"))
        self.tabs.addTab(self._tab_debug(), self.tr("🔧 Debug"))
        layout.addWidget(self.tabs)
        btns = QHBoxLayout()
        btn_apply = QPushButton(self.tr("Appliquer")); btn_apply.clicked.connect(self.apply_settings)
        btn_ok = QPushButton(self.tr("OK")); btn_ok.clicked.connect(self.save_and_close)
        btns.addStretch(); btns.addWidget(btn_apply); btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _tab_general(self):
        w = QWidget(); l = QFormLayout(w)
        self.combo_lang = QComboBox(); self.combo_lang.addItem("Français", "fr"); self.combo_lang.addItem("English", "en")
        self.chk_beep = QCheckBox(self.tr("Activer le bip de démarrage"))
        lbl_info = QLabel(self.tr("<i>Le changement de langue nécessite un redémarrage de l'application.</i>")); lbl_info.setStyleSheet("color: gray;")
        l.addRow(self.tr("Langue :"), self.combo_lang); l.addRow("", self.chk_beep); l.addRow("", lbl_info)
        return w

    def _tab_protocol(self):
        w = QWidget(); l = QFormLayout(w)
        g = QGroupBox(self.tr("Chronologie (Secondes)"))
        fl = QFormLayout()
        self.spin_flash_delay = QSpinBox(); self.spin_flash_delay.setSuffix(" s"); self.spin_flash_delay.setRange(0, 5); self.spin_flash_delay.setSingleStep(1)
        self.spin_flash_s = QDoubleSpinBox(); self.spin_flash_s.setSuffix(" s"); self.spin_flash_s.setRange(0.01, 10.0); self.spin_flash_s.setSingleStep(0.1); self.spin_flash_s.setDecimals(2)
        self.spin_total_time = QDoubleSpinBox(); self.spin_total_time.setSuffix(" s"); self.spin_total_time.setRange(1.0, 120.0); self.spin_total_time.setSingleStep(1.0)
        
        # AJOUT COULEUR PAR DEFAUT
        self.combo_def_color = QComboBox()
        self.combo_def_color.addItem(self.tr("Bleu (480nm)"), "BLUE")
        self.combo_def_color.addItem(self.tr("Rouge (630nm)"), "RED")
        self.combo_def_color.addItem(self.tr("Achromatique (Blanc)"), "WHITE")

        # AJOUT PARAMETRES DISPOSITIF (Intensité, Fréquence, Ambiance)
        self.spin_flash_intensity = QSpinBox(); self.spin_flash_intensity.setRange(0, 65536); self.spin_flash_intensity.setSingleStep(100); self.spin_flash_intensity.setSuffix(" Cd")
        self.spin_frequency = QDoubleSpinBox(); self.spin_frequency.setRange(0.01, 60.0); self.spin_frequency.setSingleStep(0.1); self.spin_frequency.setSuffix(" Hz")
        self.spin_ambiance = QSpinBox(); self.spin_ambiance.setRange(0, 65536); self.spin_ambiance.setSingleStep(100); self.spin_ambiance.setSuffix(" u")

        fl.addRow(self.tr("1. Retard flash:"), self.spin_flash_delay)
        fl.addRow(self.tr("2. Flash:"), self.spin_flash_s)
        fl.addRow(self.tr("3. Durée TOTALE:"), self.spin_total_time)
        fl.addRow(self.tr("Couleur par défaut:"), self.combo_def_color)
        
        fl.addRow(self.tr("--- Paramètres Dispositif ---"), QLabel(""))
        fl.addRow(self.tr("Intensité Flash:"), self.spin_flash_intensity)
        fl.addRow(self.tr("Fréquence:"), self.spin_frequency)
        fl.addRow(self.tr("Ambiance:"), self.spin_ambiance)
        
        self.btn_test_hw = QPushButton(self.tr("🔌 Tester Connexion & Version"))
        self.btn_test_hw.clicked.connect(self.test_hardware)
        fl.addRow(self.btn_test_hw)
        
        g.setLayout(fl); l.addWidget(g); return w

    def _tab_camera(self):
        w = QWidget(); layout = QVBoxLayout(w)

        # --- Index caméra ---
        grp_general = QGroupBox(self.tr("Général")); fl = QFormLayout()
        self.spin_idx = QSpinBox()
        fl.addRow(self.tr("Index:"), self.spin_idx)
        grp_general.setLayout(fl); layout.addWidget(grp_general)

        # --- Réglages IC4 (The Imaging Source) ---
        self.grp_ic4 = QGroupBox(self.tr("Réglages Caméra IC4 (The Imaging Source)"))
        self.ic4_layout = QFormLayout()

        self._ic4_sliders = {}
        self._ic4_autos = {}

        # Brightness (= BlackLevel dans IC4)
        self.sl_brightness = QSlider(Qt.Horizontal); self.lbl_brightness = QLabel("--")
        self.sl_brightness.valueChanged.connect(lambda v: self._on_ic4_slider_float("BlackLevel", v))
        self._ic4_sliders["BlackLevel"] = (self.sl_brightness, self.lbl_brightness)
        hl = QHBoxLayout(); hl.addWidget(self.sl_brightness, 1); hl.addWidget(self.lbl_brightness)
        self.ic4_layout.addRow(self.tr("Brightness:"), hl)

        # Contrast
        self.sl_contrast = QSlider(Qt.Horizontal); self.lbl_contrast = QLabel("--")
        self.sl_contrast.valueChanged.connect(lambda v: self._on_ic4_slider("Contrast", v))
        self._ic4_sliders["Contrast"] = (self.sl_contrast, self.lbl_contrast)
        hl = QHBoxLayout(); hl.addWidget(self.sl_contrast, 1); hl.addWidget(self.lbl_contrast)
        self.ic4_layout.addRow(self.tr("Contrast:"), hl)

        # Gain + Auto
        self.sl_gain = QSlider(Qt.Horizontal); self.lbl_gain = QLabel("--")
        self.chk_gain_auto = QCheckBox(self.tr("Auto"))
        self.sl_gain.valueChanged.connect(lambda v: self._on_ic4_slider_float("Gain", v))
        self.chk_gain_auto.toggled.connect(lambda c: self._on_ic4_auto("GainAuto", c))
        self._ic4_sliders["Gain"] = (self.sl_gain, self.lbl_gain)
        self._ic4_autos["GainAuto"] = self.chk_gain_auto
        hl = QHBoxLayout(); hl.addWidget(self.sl_gain, 1); hl.addWidget(self.lbl_gain); hl.addWidget(self.chk_gain_auto)
        self.ic4_layout.addRow(self.tr("Gain:"), hl)

        # Exposure + Auto
        self.sl_exposure = QSlider(Qt.Horizontal); self.lbl_exposure = QLabel("--")
        self.chk_exposure_auto = QCheckBox(self.tr("Auto"))
        self.sl_exposure.valueChanged.connect(lambda v: self._on_ic4_slider_float("ExposureTime", v))
        self.chk_exposure_auto.toggled.connect(lambda c: self._on_ic4_auto("ExposureAuto", c))
        self._ic4_sliders["ExposureTime"] = (self.sl_exposure, self.lbl_exposure)
        self._ic4_autos["ExposureAuto"] = self.chk_exposure_auto
        hl = QHBoxLayout(); hl.addWidget(self.sl_exposure, 1); hl.addWidget(self.lbl_exposure); hl.addWidget(self.chk_exposure_auto)
        self.ic4_layout.addRow(self.tr("Exposure:"), hl)

        # Gamma
        self.sl_gamma = QSlider(Qt.Horizontal); self.lbl_gamma = QLabel("--")
        self.sl_gamma.valueChanged.connect(lambda v: self._on_ic4_slider_float("Gamma", v))
        self._ic4_sliders["Gamma"] = (self.sl_gamma, self.lbl_gamma)
        hl = QHBoxLayout(); hl.addWidget(self.sl_gamma, 1); hl.addWidget(self.lbl_gamma)
        self.ic4_layout.addRow(self.tr("Gamma:"), hl)

        # Bouton refresh
        self.btn_ic4_refresh = QPushButton(self.tr("Lire les valeurs caméra"))
        self.btn_ic4_refresh.clicked.connect(self._refresh_ic4_properties)
        self.ic4_layout.addRow(self.btn_ic4_refresh)

        self.lbl_ic4_status = QLabel(self.tr("Cliquez sur 'Lire les valeurs caméra' pour charger les réglages."))
        self.lbl_ic4_status.setStyleSheet("color: gray; font-style: italic;")
        self.ic4_layout.addRow(self.lbl_ic4_status)

        self.grp_ic4.setLayout(self.ic4_layout)
        layout.addWidget(self.grp_ic4)
        layout.addStretch()
        return w

    def _get_camera_engine(self):
        """Récupère le CameraEngine depuis la fenêtre principale."""
        main_win = self.parent()
        if main_win and hasattr(main_win, 'camera_thread') and main_win.camera_thread:
            return main_win.camera_thread.camera
        return None

    def _refresh_ic4_properties(self):
        """Lit les propriétés IC4 depuis la caméra et met à jour les sliders."""
        cam = self._get_camera_engine()
        # Debug : comprendre pourquoi la caméra n'est pas trouvée
        main_win = self.parent()
        print(f"[IC4-DEBUG] parent={type(main_win).__name__}, "
              f"has camera_thread={hasattr(main_win, 'camera_thread')}, "
              f"camera_thread={getattr(main_win, 'camera_thread', None)}, "
              f"cam={cam}, "
              f"use_ic4={cam._use_ic4 if cam else 'N/A'}")
        if not cam or not cam._use_ic4:
            self.lbl_ic4_status.setText(self.tr("Caméra IC4 non disponible (OpenCV ou déconnectée)."))
            self.lbl_ic4_status.setStyleSheet("color: #f44336; font-style: italic;")
            return

        props = cam.get_ic4_properties()
        if not props:
            self.lbl_ic4_status.setText(self.tr("Impossible de lire les propriétés."))
            self.lbl_ic4_status.setStyleSheet("color: #f44336; font-style: italic;")
            return

        # BlackLevel (float, affiché comme "Brightness")
        if "BlackLevel" in props:
            p = props["BlackLevel"]
            sl, lbl = self._ic4_sliders["BlackLevel"]
            sl.blockSignals(True)
            sl.setRange(int(p["min"]), int(p["max"]))
            sl.setValue(int(p["value"]))
            lbl.setText(str(int(p["value"])))
            sl.blockSignals(False)

        # Contrast (integer)
        if "Contrast" in props:
            p = props["Contrast"]
            sl, lbl = self._ic4_sliders["Contrast"]
            sl.blockSignals(True)
            sl.setRange(int(p["min"]), int(p["max"]))
            sl.setValue(int(p["value"]))
            lbl.setText(str(int(p["value"])))
            sl.blockSignals(False)

        # Gain (float, slider en centièmes pour la précision)
        if "Gain" in props:
            p = props["Gain"]
            sl, lbl = self._ic4_sliders["Gain"]
            sl.blockSignals(True)
            sl.setRange(int(p["min"] * 100), int(p["max"] * 100))
            sl.setValue(int(p["value"] * 100))
            lbl.setText(f"{p['value']:.2f} dB")
            sl.blockSignals(False)

        if "GainAuto" in props:
            chk = self._ic4_autos["GainAuto"]
            chk.blockSignals(True)
            chk.setChecked(props["GainAuto"]["value"] == "Continuous")
            chk.blockSignals(False)

        # Exposure (float µs)
        if "ExposureTime" in props:
            p = props["ExposureTime"]
            sl, lbl = self._ic4_sliders["ExposureTime"]
            sl.blockSignals(True)
            sl.setRange(int(p["min"]), min(int(p["max"]), 250000))
            sl.setValue(int(p["value"]))
            exp_us = p["value"]
            if exp_us > 1000:
                lbl.setText(f"1/{int(1000000/exp_us)}")
            else:
                lbl.setText(f"{exp_us:.0f} µs")
            sl.blockSignals(False)

        if "ExposureAuto" in props:
            chk = self._ic4_autos["ExposureAuto"]
            chk.blockSignals(True)
            chk.setChecked(props["ExposureAuto"]["value"] == "Continuous")
            chk.blockSignals(False)

        # Gamma (float, slider en centièmes)
        if "Gamma" in props:
            p = props["Gamma"]
            sl, lbl = self._ic4_sliders["Gamma"]
            sl.blockSignals(True)
            sl.setRange(int(p["min"] * 100), int(p["max"] * 100))
            sl.setValue(int(p["value"] * 100))
            lbl.setText(f"{p['value']:.2f}")
            sl.blockSignals(False)

        self.lbl_ic4_status.setText(self.tr("Propriétés chargées avec succès."))
        self.lbl_ic4_status.setStyleSheet("color: #4caf50; font-style: italic;")

    def _on_ic4_slider(self, prop_name, value):
        """Applique une propriété entière IC4 en temps réel."""
        cam = self._get_camera_engine()
        if cam:
            cam.set_ic4_property(prop_name, value)
        sl, lbl = self._ic4_sliders[prop_name]
        lbl.setText(str(value))

    def _on_ic4_slider_float(self, prop_name, value):
        """Applique une propriété flottante IC4."""
        cam = self._get_camera_engine()
        sl, lbl = self._ic4_sliders[prop_name]
        if prop_name == "Gain":
            real_val = value / 100.0
            if cam: cam.set_ic4_property(prop_name, real_val)
            lbl.setText(f"{real_val:.2f} dB")
        elif prop_name == "Gamma":
            real_val = value / 100.0
            if cam: cam.set_ic4_property(prop_name, real_val)
            lbl.setText(f"{real_val:.2f}")
        elif prop_name == "ExposureTime":
            if cam: cam.set_ic4_property(prop_name, float(value))
            if value > 1000:
                lbl.setText(f"1/{int(1000000/value)}")
            else:
                lbl.setText(f"{value} µs")
        elif prop_name == "BlackLevel":
            if cam: cam.set_ic4_property(prop_name, float(value))
            lbl.setText(str(value))

    def _on_ic4_auto(self, prop_name, checked):
        """Active/désactive un mode Auto IC4 (Gain ou Exposure)."""
        cam = self._get_camera_engine()
        if cam:
            cam.set_ic4_property(prop_name, "Continuous" if checked else "Off")

    def _tab_detection(self):
        w = QWidget(); l = QFormLayout(w)
        self.spin_canny = QSpinBox(); self.spin_canny.setRange(0, 255); self.spin_blur = QSpinBox(); self.spin_blur.setRange(1, 31); self.spin_blur.setSingleStep(2)
        self.spin_rw = QSpinBox(); self.spin_rw.setRange(50, 4000); self.spin_rh = QSpinBox(); self.spin_rh.setRange(50, 4000)
        self.spin_offx = QSpinBox(); self.spin_offx.setRange(-2000, 2000); self.spin_offy = QSpinBox(); self.spin_offy.setRange(-2000, 2000)
        l.addRow(self.tr("Seuil:"), self.spin_canny); l.addRow(self.tr("Flou:"), self.spin_blur); l.addRow(self.tr("Largeur ROI:"), self.spin_rw); l.addRow(self.tr("Hauteur ROI:"), self.spin_rh); l.addRow(self.tr("Offset X:"), self.spin_offx); l.addRow(self.tr("Offset Y:"), self.spin_offy); return w

    def _tab_clinic(self):
        w = QWidget(); l = QFormLayout(w)
        self.inp_clin_name = QLineEdit(); self.inp_clin_addr = QLineEdit(); self.inp_clin_doc = QLineEdit(); self.inp_clin_phone = QLineEdit(); self.inp_clin_logo = QLineEdit()
        btn = QPushButton("..."); btn.clicked.connect(lambda: self.inp_clin_logo.setText(QFileDialog.getOpenFileName(self, self.tr("Logo"))[0]))
        l.addRow(self.tr("Nom:"), self.inp_clin_name); l.addRow(self.tr("Adresse:"), self.inp_clin_addr); l.addRow(self.tr("Tel:"), self.inp_clin_phone); l.addRow(self.tr("Praticien:"), self.inp_clin_doc); h = QHBoxLayout(); h.addWidget(self.inp_clin_logo); h.addWidget(btn); l.addRow(self.tr("Logo:"), h); return w

    def _tab_macros(self):
        w = QWidget(); l = QVBoxLayout(w); h = QHBoxLayout()
        self.ic = QLineEdit(); self.ic.setPlaceholderText(self.tr("Saisissez votre phrase type ici..."))
        b = QPushButton(self.tr("Ajouter")); b.clicked.connect(self._add_macro)
        h.addWidget(self.ic); h.addWidget(b); self.lm = QListWidget()
        bd = QPushButton(self.tr("Supprimer Sélection")); bd.clicked.connect(self._del_macro)
        l.addLayout(h); l.addWidget(self.lm); l.addWidget(bd); self._refresh_macros(); return w

    def _tab_debug(self):
        w = QWidget(); l = QVBoxLayout(w)
        grp = QGroupBox(self.tr("Communication Série"))
        vl = QVBoxLayout()
        lbl = QLabel(self.tr("Ouvre la console de debug pour visualiser les échanges série avec le microcontrôleur."))
        lbl.setWordWrap(True)
        self.btn_open_serial = QPushButton(self.tr("Console Série (Debug µC)"))
        self.btn_open_serial.setStyleSheet("background:#1e1e1e;color:#00ff00;padding:10px 16px;border-radius:3px;font-family:Consolas,monospace;font-weight:bold;border:1px solid #555;font-size:14px;")
        self.btn_open_serial.clicked.connect(self._open_serial_console)
        vl.addWidget(lbl); vl.addWidget(self.btn_open_serial)
        grp.setLayout(vl); l.addWidget(grp); l.addStretch()
        return w

    def _open_serial_console(self):
        main_win = self.parent()
        if hasattr(main_win, 'serial_console_window'):
            main_win.serial_console_window.show()
            main_win.serial_console_window.raise_()
            main_win.serial_console_window.activateWindow()

    def _refresh_macros(self):
        self.lm.clear()
        for m in self.db.get_macros(): self.lm.addItem(f"{m['id']} : {m['content']}")
    def _add_macro(self): 
        if self.ic.text(): self.db.add_macro(self.ic.text()); self._refresh_macros(); self.ic.clear()
    def _del_macro(self): 
        if self.lm.currentItem(): self.db.delete_macro(int(self.lm.currentItem().text().split(" : ")[0])); self._refresh_macros()

    def load_settings(self):
        c = self.config_manager.config
        gen = c.get("general", {})
        lang = gen.get("language", "fr"); idx = 1 if lang == "en" else 0; self.combo_lang.setCurrentIndex(idx)
        self.chk_beep.setChecked(gen.get("enable_beep", True))
        p = c.get("protocol", {})
        delay = p.get("flash_delay_s", 2); flash_s = p.get("flash_duration_ms", 200) / 1000.0; resp = p.get("response_duration", 5.0)
        self.spin_flash_delay.setValue(int(delay)); self.spin_flash_s.setValue(flash_s); self.spin_total_time.setValue(delay + flash_s + resp)
        
        # Charge la couleur par défaut
        def_col = p.get("default_color", "BLUE")
        idx_col = 0
        if def_col == "RED": idx_col = 1
        elif def_col == "WHITE": idx_col = 2
        self.combo_def_color.setCurrentIndex(idx_col)

        # Charge les nouveaux paramètres (avec valeurs par défaut demandées)
        self.spin_flash_intensity.setValue(p.get("flash_intensity", 2000))
        self.spin_frequency.setValue(p.get("flash_frequency", 0.1))
        self.spin_ambiance.setValue(p.get("ambiance_intensity", 0))

        cm = c.get("camera", {}); self.spin_idx.setValue(cm.get("index", 0))
        d = c.get("detection", {}); self.spin_canny.setValue(d.get("canny_threshold1", 50)); self.spin_blur.setValue(d.get("gaussian_blur", 5)); self.spin_rw.setValue(d.get("roi_width", 400)); self.spin_rh.setValue(d.get("roi_height", 400)); self.spin_offx.setValue(d.get("roi_offset_x", 0)); self.spin_offy.setValue(d.get("roi_offset_y", 0))
        i = self.db.get_clinic_info()
        self.inp_clin_name.setText(i.get('name','')); self.inp_clin_addr.setText(i.get('address','')); self.inp_clin_doc.setText(i.get('doctor_name','')); self.inp_clin_phone.setText(i.get('phone','')); self.inp_clin_logo.setText(i.get('logo_path',''))

    def get_settings(self):
        delay = self.spin_flash_delay.value(); flash_s = self.spin_flash_s.value(); total = self.spin_total_time.value()
        if total <= (delay + flash_s): total = delay + flash_s + 2.0; self.spin_total_time.setValue(total)
        response = total - delay - flash_s
        lang_code = self.combo_lang.currentData()
        
        return {
            "general": {"language": lang_code, "enable_beep": self.chk_beep.isChecked()},
            "protocol": {
                "flash_delay_s": delay,
                "flash_duration_ms": int(flash_s * 1000), 
                "response_duration": round(response, 2), 
                "flash_count": 1,
                "default_color": self.combo_def_color.currentData(),
                "flash_intensity": self.spin_flash_intensity.value(),
                "flash_frequency": self.spin_frequency.value(),
                "ambiance_intensity": self.spin_ambiance.value()
            },
            "camera": {"index": self.spin_idx.value(), "width": 640, "height": 480},
            "detection": {"canny_threshold1": self.spin_canny.value(), "gaussian_blur": self.spin_blur.value(), "roi_width": self.spin_rw.value(), "roi_height": self.spin_rh.value(), "roi_offset_x": self.spin_offx.value(), "roi_offset_y": self.spin_offy.value()},
            "recording": {"save_path": "recordings"}
        }

    def apply_settings(self):
        self.settings_changed.emit(self.get_settings())
        self.db.set_clinic_info(self.inp_clin_name.text(), self.inp_clin_addr.text(), self.inp_clin_phone.text(), "", self.inp_clin_doc.text(), self.inp_clin_logo.text())

    def save_and_close(self): self.apply_settings(); self.config_manager.save(self.get_settings()); self.accept()

    def test_hardware(self):
        """Teste la connexion et demande la version."""
        main_win = self.parent()
        if not hasattr(main_win, 'hardware'): return

        hw = main_win.hardware
        if not hw.is_connected:
            QMessageBox.warning(self, self.tr("Erreur"), self.tr("Le matériel n'est pas connecté."))
            return

        # Connexion temporaire du signal
        try: hw.firmware_received.disconnect(self._on_firmware_received)
        except: pass
        hw.firmware_received.connect(self._on_firmware_received)
        hw.request_firmware_version()

    def _on_firmware_received(self, version):
        QMessageBox.information(self, self.tr("Succès"), self.tr("Matériel connecté.\nRéponse : {}").format(version))
        try: self.parent().hardware.firmware_received.disconnect(self._on_firmware_received)
        except: pass