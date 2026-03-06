"""
main_application.py
===================
Interface Examen V3.28 (Historique : Nettoyage couleurs et Francisation).
"""

import sys
import time
import os
# Imports explicites pour forcer la détection par PyInstaller
import shiboken6
import PySide6

import cv2
import numpy as np
import json
from datetime import datetime
import logging
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QComboBox, QGroupBox, QMessageBox,
    QStatusBar, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QRadioButton, QButtonGroup, QSplitter,
    QTextEdit, QFileDialog, QSizePolicy, QMenu, QProgressDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer, QPoint, QTranslator, QLibraryInfo
from PySide6.QtGui import QImage, QPixmap, QAction, QColor, QCursor, QKeyEvent

# --- IMPORTS PROJET ---
from camera_engine import CameraEngine
from settings_dialog import SettingsDialog, ConfigManager
from plr_test_engine import PLRTestEngine
from plr_analyzer import PLRAnalyzer
from plr_results_viewer import PLRGraphWidget, PLRResultsDialog
from db_manager import DatabaseManager
from welcome_screen import WelcomeScreen
from calibration_dialog import CalibrationDialog
from pdf_generator import PDFGenerator
from styles import apply_modern_theme
from hardware_manager import HardwareManager

logging.basicConfig(level=logging.INFO)

class CameraThread(QThread):
    """
    Thread dédié à la capture vidéo pour ne pas bloquer l'interface graphique.
    Gère le cycle de vie de CameraEngine.
    """
    frame_ready = Signal(np.ndarray)
    pupil_detected = Signal(dict)
    fps_updated = Signal(float)
    error_occurred = Signal(str)
    camera_started = Signal()

    def __init__(self, camera_index: int = 0):
        super().__init__()
        self.camera: Optional[CameraEngine] = None
        self.camera_index = camera_index
        self.running = False
        self.fps_divisor = 1   # 1 = 30fps, 2 = 15fps (une frame sur deux)
        self._frame_counter = 0

    def run(self) -> None:
        """Boucle principale du thread."""
        try:
            self.camera = CameraEngine(self.camera_index)
            if not self.camera.is_ready():
                raise Exception("Impossible d'initialiser la caméra.\nEst-elle bien branchée ?")

            self.running = True
            self._frame_counter = 0
            self.camera.record_skip = self.fps_divisor
            self.camera_started.emit()

            consecutive_failures = 0
            MAX_FAILURES = 10

            while self.running:
                frame, pupil_data = self.camera.grab_and_detect()
                if frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_FAILURES:
                        raise Exception("Perte du signal vidéo (Déconnexion).")
                    self.msleep(30)
                    continue
                consecutive_failures = 0

                self._frame_counter += 1

                # Émission du FPS effectif (après diviseur) toutes les 15 frames raw
                if self._frame_counter % 15 == 0:
                    self.fps_updated.emit(self.camera.fps / self.fps_divisor)

                # Envoi frame + données uniquement si on n'est pas en mode skip
                if self._frame_counter % self.fps_divisor == 0:
                    self.frame_ready.emit(frame)
                    if pupil_data:
                        self.pupil_detected.emit(pupil_data)

                self.msleep(1)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.camera:
                self.camera.release()

    def stop(self):
        self.running = False
        self.wait(2000)

    def set_fps(self, fps: int):
        """Définit le diviseur de frames (pour 15fps uniquement)."""
        self.fps_divisor = 2 if fps == 15 else 1
        if self.camera:
            self.camera.record_skip = self.fps_divisor

    def set_threshold(self, v: int):
        if self.camera: self.camera.set_threshold(v)

    def set_blur(self, v: int):
        if self.camera: self.camera.set_blur_kernel(v)

    def set_display_mode(self, m: str):
        if self.camera: self.camera.set_display_mode(m)

    def start_recording(self, f: str):
        if self.camera: self.camera.start_recording(f)

    def stop_recording(self):
        if self.camera: self.camera.stop_recording()

class VideoWidget(QLabel):
    def __init__(self): super().__init__(); self.setAlignment(Qt.AlignCenter); self.setStyleSheet("background:black; border:2px solid #444;"); self.setMinimumSize(320, 240)
    @Slot(np.ndarray)
    def update_frame(self, f): 
        try: self.setPixmap(QPixmap.fromImage(QImage(cv2.cvtColor(f,cv2.COLOR_BGR2RGB).data, f.shape[1], f.shape[0], f.shape[1]*3, QImage.Format_RGB888)).scaled(self.size(), Qt.KeepAspectRatio))
        except: pass

class ControlPanel(QWidget):
    threshold_changed = Signal(int)
    blur_changed = Signal(int)
    display_mode_changed = Signal(str)
    fps_changed = Signal(int)
    test_requested = Signal()
    settings_requested = Signal()
    reset_camera_requested = Signal()
    reset_hardware_requested = Signal()
    color_changed = Signal(str)
    intensity_changed = Signal(int)

    def __init__(self): super().__init__(); self.setup_ui()
    def setup_ui(self):
        l=QVBoxLayout(self); l.setSpacing(10)
        
        # CHOIX OEIL
        ge=QGroupBox(self.tr("Choix de l'Œil")); he=QHBoxLayout(); self.eg=QButtonGroup(self)
        self.rod=QRadioButton(self.tr("OD (Droit)")); self.rod.setStyleSheet("color:#d32f2f;font-weight:bold;"); self.rod.setChecked(True)
        self.rog=QRadioButton(self.tr("OG (Gauche)")); self.rog.setStyleSheet("color:#1976d2;font-weight:bold;")
        self.eg.addButton(self.rod); self.eg.addButton(self.rog); he.addWidget(self.rod); he.addWidget(self.rog); ge.setLayout(he); l.addWidget(ge)
        
        # CHOIX COULEUR FLASH
        gc=QGroupBox(self.tr("Stimulus Chromatique")); hc=QHBoxLayout(); self.cg=QButtonGroup(self)
        self.rc_blue = QRadioButton(self.tr("Bleu")); self.rc_blue.setStyleSheet("color:#007bff; font-weight:bold;")
        self.rc_red = QRadioButton(self.tr("Rouge")); self.rc_red.setStyleSheet("color:#dc3545; font-weight:bold;")
        self.rc_white = QRadioButton(self.tr("Achromatique")); self.rc_white.setStyleSheet("color:#555; font-weight:bold;")
        self.rc_white.setChecked(True)
        self.cg.addButton(self.rc_blue); self.cg.addButton(self.rc_red); self.cg.addButton(self.rc_white)
        hc.addWidget(self.rc_blue); hc.addWidget(self.rc_red); hc.addWidget(self.rc_white)
        gc.setLayout(hc); l.addWidget(gc)
        self.cg.buttonClicked.connect(lambda: self.color_changed.emit(self.get_selected_color()))

        # INTENSITE FLASH
        gi=QGroupBox(self.tr("Intensité Flash")); li=QVBoxLayout()
        self.lbl_intensity=QLabel("100 %"); self.lbl_intensity.setAlignment(Qt.AlignCenter); self.lbl_intensity.setStyleSheet("font-weight:bold;")
        self.slider_intensity=QSlider(Qt.Horizontal); self.slider_intensity.setRange(0,100); self.slider_intensity.setValue(100)
        self.slider_intensity.valueChanged.connect(self._on_intensity_change)
        li.addWidget(self.lbl_intensity); li.addWidget(self.slider_intensity); gi.setLayout(li); l.addWidget(gi)

        # REGLAGES
        gs=QGroupBox(self.tr("Réglages Caméra")); fl=QVBoxLayout()
        self.st=QSlider(Qt.Horizontal); self.st.setRange(0,255); self.st.setValue(50); self.st.valueChanged.connect(self.threshold_changed.emit)
        self.sb=QSlider(Qt.Horizontal); self.sb.setRange(1,21); self.sb.setValue(5); self.sb.valueChanged.connect(self.blur_changed.emit)
        self.cm=QComboBox(); self.cm.addItems(["Normal","ROI","Binaire","Mosaïque"]); self.cm.currentTextChanged.connect(lambda t:self._on_mode(t))
        # Sélecteur FPS
        self.fps_grp = QButtonGroup(self)
        self.rb_15fps = QRadioButton("15 fps")
        self.rb_30fps = QRadioButton("30 fps"); self.rb_30fps.setChecked(True)
        self.rb_40fps = QRadioButton("40 fps")
        self.rb_60fps = QRadioButton("60 fps")
        self.rb_max  = QRadioButton("Max")
        for rb in (self.rb_15fps, self.rb_30fps, self.rb_40fps, self.rb_60fps, self.rb_max):
            self.fps_grp.addButton(rb)
        hfps1 = QHBoxLayout(); hfps1.addWidget(self.rb_15fps); hfps1.addWidget(self.rb_30fps); hfps1.addWidget(self.rb_40fps)
        hfps2 = QHBoxLayout(); hfps2.addWidget(self.rb_60fps); hfps2.addWidget(self.rb_max)
        vfps = QVBoxLayout(); vfps.setSpacing(2); vfps.addLayout(hfps1); vfps.addLayout(hfps2)
        wfps = QWidget(); wfps.setLayout(vfps)
        self.fps_grp.buttonClicked.connect(lambda: self.fps_changed.emit(self._get_fps_value()))
        fl.addWidget(QLabel(self.tr("Seuil"))); fl.addWidget(self.st); fl.addWidget(QLabel(self.tr("Flou"))); fl.addWidget(self.sb); fl.addWidget(QLabel(self.tr("Vue"))); fl.addWidget(self.cm); fl.addWidget(QLabel(self.tr("FPS"))); fl.addWidget(wfps); gs.setLayout(fl); l.addWidget(gs)
        
        # BOUTON LANCER
        self.bt=QPushButton(self.tr("▶ LANCER EXAMEN")); self.bt.setFixedHeight(45); self.bt.setStyleSheet("background:#28a745;color:white;font-weight:bold;border-radius:5px;"); self.bt.clicked.connect(self.test_requested.emit)
        
        self.pb=QProgressBar(); self.pb.setAlignment(Qt.AlignCenter); self.pb.setValue(0); self.pb.setStyleSheet("QProgressBar{border:1px solid #999;border-radius:5px;text-align:center;} QProgressBar::chunk{background-color:#28a745;}")
        self.br=QPushButton(self.tr("🔄 Réinit. Caméra")); self.br.setStyleSheet("background:#e67e22;color:white;padding:5px;border-radius:4px;"); self.br.clicked.connect(self.reset_camera_requested.emit)
        self.bh=QPushButton(self.tr("🔌 Réinit. Matériel")); self.bh.setStyleSheet("background:#6c757d;color:white;padding:5px;border-radius:4px;"); self.bh.clicked.connect(self.reset_hardware_requested.emit)
        l.addWidget(self.bt); l.addWidget(self.pb); l.addWidget(self.br); l.addWidget(self.bh); l.addStretch()
        
    def _on_mode(self, t: str): 
        mode = "normal"
        if "ROI" in t: mode="roi"
        elif "Binaire" in t or "Binary" in t: mode="binary"
        elif "Mosa" in t: mode="mosaic"
        self.display_mode_changed.emit(mode)
        
    def _on_intensity_change(self, v): self.lbl_intensity.setText(f"{v} %"); self.intensity_changed.emit(v)
    def get_intensity_percent(self): return self.slider_intensity.value()
    def set_intensity_percent(self, v): self.slider_intensity.setValue(v)

    def _get_fps_value(self) -> int:
        if self.rb_15fps.isChecked(): return 15
        if self.rb_30fps.isChecked(): return 30
        if self.rb_40fps.isChecked(): return 40
        if self.rb_60fps.isChecked(): return 60
        return 0  # Max = 0 (pas de limite)

    def get_selected_eye(self) -> str: return "OD" if self.rod.isChecked() else "OG"
    
    def get_selected_color(self) -> str: 
        if self.rc_blue.isChecked(): return "BLUE"
        if self.rc_red.isChecked(): return "RED"
        return "WHITE"

    def set_button_running(self, running):
        if running:
            self.bt.setText(self.tr("EN COURS..."))
            self.bt.setStyleSheet("background:#17a2b8;color:white;font-weight:bold;")
            self.bt.setEnabled(False)
        else:
            self.bt.setText(self.tr("▶ LANCER EXAMEN"))
            self.bt.setStyleSheet("background:#28a745;color:white;font-weight:bold;")
            # L'activation est gérée par check_ready_state() dans MainWindow

class MainWindow(QMainWindow):
    def __init__(self, patient_data):
        super().__init__()
        self.patient = patient_data
        self.db = DatabaseManager()
        self.conf = ConfigManager()
        self.temp_result_meta = None 
        self.selected_historical_exam = None
        self.camera_thread = None
        self.engine = None
        self.real_flash_timestamp = None
        
        self.hardware = HardwareManager()
        self.hardware.trigger_pressed.connect(self.start_test)
        self.hardware.connection_status_changed.connect(self.on_hardware_status_changed)
        self.hardware.flash_fired.connect(self.on_hardware_flash_fired)
        
        # Timer pour la reconnexion automatique du matériel
        self.hw_reconnect_timer = QTimer(self)
        self.hw_reconnect_timer.setInterval(3000) # Tentative toutes les 3 secondes
        self.hw_reconnect_timer.timeout.connect(self.try_auto_reconnect_hw)

        self.is_camera_ready = False
        self.is_test_running = False 
        self.is_hardware_ready = False
        
        self.current_laterality = 'OD'
        self.current_color = 'BLUE'

        self.setup_ui()
        self.start_camera()
        self._apply_default_color()
        self.check_ready_state()

        if self.patient: 
            self.setWindowTitle(self.tr("Dossier Patient : {name} ({species})").format(name=self.patient['name'], species=self.patient['species']))
            self.load_patient_history()
            
        # Tentative de connexion silencieuse au démarrage. Le timer gère les échecs.
        self.hardware.connect_device()

    def check_ready_state(self):
        """Active le bouton 'Lancer' uniquement si tout est prêt."""
        ready = self.is_camera_ready and self.is_hardware_ready and not self.is_test_running
        self.controls.bt.setEnabled(ready)
        
        if not self.is_hardware_ready:
            self.controls.bt.setToolTip(self.tr("Le matériel n'est pas connecté"))
        elif not self.is_camera_ready:
            self.controls.bt.setToolTip(self.tr("La caméra n'est pas prête"))
        else:
            self.controls.bt.setToolTip("")

    def _apply_default_color(self):
        def_col = self.conf.get("protocol", "default_color", "WHITE")
        if def_col == "BLUE": self.controls.rc_blue.setChecked(True)
        elif def_col == "RED": self.controls.rc_red.setChecked(True)
        else: self.controls.rc_white.setChecked(True)

    def setup_ui(self):
        screen = QApplication.primaryScreen().availableGeometry()
        win_w = min(1400, int(screen.width() * 0.92))
        win_h = min(950, int(screen.height() * 0.92))
        self.resize(win_w, win_h)
        central = QWidget(); self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(4, 2, 4, 4)
        main_lay.setSpacing(2)

        # --- BARRE DE STATUT SUPÉRIEURE ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(2, 0, 2, 0)
        
        self.lbl_cam_status = QLabel(self.tr("Caméra: ?"))
        self.lbl_cam_status.setAlignment(Qt.AlignCenter); self.lbl_cam_status.setFixedHeight(30)

        self.lbl_hw_status = QLabel(self.tr("Appareil: ?"))
        self.lbl_hw_status.setAlignment(Qt.AlignCenter); self.lbl_hw_status.setFixedHeight(30)

        self.lbl_fps_status = QLabel("-- FPS")
        self.lbl_fps_status.setAlignment(Qt.AlignCenter); self.lbl_fps_status.setFixedSize(80, 30)
        self.lbl_fps_status.setStyleSheet("background-color:#e8f5e9; color:#1b5e20; border:2px solid #a5d6a7; border-radius:5px; font-weight:bold; font-size:13px;")

        top_bar.addWidget(self.lbl_cam_status); top_bar.addWidget(self.lbl_hw_status); top_bar.addWidget(self.lbl_fps_status); top_bar.addStretch()
        main_lay.addLayout(top_bar)
        
        # --- CONTENU PRINCIPAL ---
        left = QSplitter(Qt.Vertical)
        self.video = VideoWidget(); self.controls = ControlPanel()
        self.controls.threshold_changed.connect(lambda v: self.camera_thread.set_threshold(v))
        self.controls.blur_changed.connect(lambda v: self.camera_thread.set_blur(v))
        self.controls.display_mode_changed.connect(lambda m: self.camera_thread.set_display_mode(m))
        self.controls.fps_changed.connect(self.on_fps_changed)

        p = self.conf.config.get("protocol", {})
        self.controls.set_intensity_percent(int((p.get("flash_intensity", 65536)/65536.0)*100))
        self.controls.intensity_changed.connect(self.update_hardware_params)

        self.controls.test_requested.connect(self.start_test)
        self.controls.reset_camera_requested.connect(self.reset_camera)
        self.controls.reset_hardware_requested.connect(self.reset_hardware)
        self.controls.color_changed.connect(self.update_hardware_params)

        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidget(self.controls)
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ctrl_scroll.setFrameShape(QScrollArea.NoFrame)
        left.addWidget(self.video); left.addWidget(ctrl_scroll)
        left.setSizes([int(win_h * 0.45), int(win_h * 0.45)])
        
        right_split = QSplitter(Qt.Vertical)
        self.graph_widget = PLRGraphWidget()
        bottom_w = QWidget(); bl = QVBoxLayout(bottom_w); bl.setContentsMargins(0,0,0,0)
        
        self.grp_actions = QGroupBox(self.tr("Actions")); self.grp_actions.setStyleSheet("background-color:#f0f4c3; font-weight:bold;")
        self.grp_actions.setMaximumHeight(80); hl_act = QHBoxLayout()
        self.btn_save = QPushButton(self.tr("💾 SAUVEGARDER NOUVEAU")); self.btn_save.clicked.connect(self.save_new_exam)
        self.btn_discard = QPushButton(self.tr("🗑️ Jeter")); self.btn_discard.clicked.connect(self.discard_exam)
        self.btn_save.setStyleSheet("background:#28a745;color:white;font-weight:bold;padding:5px;"); self.btn_discard.setStyleSheet("background:#dc3545;color:white;padding:5px;")
        self.btn_update_comment = QPushButton(self.tr("💾 MAJ Commentaire")); self.btn_update_comment.clicked.connect(self.update_historical_comment)
        self.btn_pdf = QPushButton(self.tr("📄 EXPORT PDF")); self.btn_pdf.clicked.connect(self.export_pdf)
        self.btn_excel = QPushButton(self.tr("📊 EXPORT DATA")); self.btn_excel.clicked.connect(self.export_excel)
        self.btn_excel.setStyleSheet("background:#ff9800;color:white;font-weight:bold;padding:5px;")
        self.btn_compare = QPushButton(self.tr("🆚 Comparer OD/OG")); self.btn_compare.clicked.connect(self.auto_compare_eyes)
        self.btn_compare.setStyleSheet("background:#6f42c1;color:white;font-weight:bold;padding:5px;")
        
        self.btn_update_comment.setStyleSheet("background:#007bff;color:white;font-weight:bold;padding:5px;"); self.btn_pdf.setStyleSheet("background:#17a2b8;color:white;font-weight:bold;padding:5px;")
        self.btn_frames = QPushButton(self.tr("Film frame par frame")); self.btn_frames.clicked.connect(self.open_frames_viewer)
        self.btn_frames.setStyleSheet("background:#795548;color:white;font-weight:bold;padding:5px;")
        hl_act.addWidget(self.btn_save); hl_act.addWidget(self.btn_discard); hl_act.addWidget(self.btn_update_comment); hl_act.addWidget(self.btn_pdf); hl_act.addWidget(self.btn_excel); hl_act.addWidget(self.btn_compare); hl_act.addWidget(self.btn_frames)
        self.grp_actions.setLayout(hl_act); self.grp_actions.setVisible(False)
        
        self.grp_com = QGroupBox(self.tr("Rapport / Commentaires")); vl_com = QVBoxLayout(); hl_mac = QHBoxLayout()
        self.combo_macros = QComboBox(); self.combo_macros.addItem(self.tr("--- Insérer phrase type ---"))
        self._load_macros(); self.combo_macros.currentIndexChanged.connect(self._insert_macro)
        hl_mac.addWidget(self.combo_macros); hl_mac.addStretch(); self.txt_comments = QTextEdit(); self.txt_comments.setPlaceholderText(self.tr("Observations...")); self.txt_comments.setMaximumHeight(80); vl_com.addLayout(hl_mac); vl_com.addWidget(self.txt_comments); self.grp_com.setLayout(vl_com)

        self.grp_hist = QGroupBox(self.tr("Historique")); vl_hist = QVBoxLayout()
        self.table_hist = QTableWidget(0, 8); self.table_hist.setHorizontalHeaderLabels([self.tr("Date & Heure"),self.tr("Oeil"),self.tr("Stim"),self.tr("Type"),self.tr("Durée"),self.tr("Intensité (%)"), "", ""])
        self.table_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_hist.setSelectionBehavior(QAbstractItemView.SelectRows); self.table_hist.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_hist.setSortingEnabled(True); self.table_hist.setContextMenuPolicy(Qt.CustomContextMenu); self.table_hist.customContextMenuRequested.connect(self.show_history_menu); self.table_hist.itemClicked.connect(self.on_history_clicked); vl_hist.addWidget(self.table_hist); self.grp_hist.setLayout(vl_hist)
        
        bl.addWidget(self.grp_actions); bl.addWidget(self.grp_com); bl.addWidget(self.grp_hist)
        self.right_split = QSplitter(Qt.Vertical)
        self.right_split.addWidget(self.graph_widget); self.right_split.addWidget(bottom_w)
        QTimer.singleShot(0, self._restore_splitter)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left); splitter.addWidget(self.right_split); splitter.setSizes([int(win_w * 0.36), int(win_w * 0.64)])
        
        main_lay.addWidget(splitter)
        
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.lbl_flash_indicator = QLabel("⚡ FLASH")
        self.lbl_flash_indicator.setStyleSheet("background-color: #ffeb3b; color: #e65100; font-weight: bold; padding: 2px 5px; border-radius: 3px;")
        self.lbl_flash_indicator.setVisible(False)
        self.status.addPermanentWidget(self.lbl_flash_indicator)
        self._create_menu(); self.load_patient_history(); self._set_ui_state("IDLE")

    def _restore_splitter(self):
        """Restaure la position du séparateur graphique/historique depuis la config."""
        saved = self.conf.get("ui", "right_split_sizes", None)
        if saved and len(saved) == 2:
            self.right_split.setSizes(saved)
        else:
            # Défaut : 55% graphique, 45% historique
            total = sum(self.right_split.sizes())
            if total > 0:
                self.right_split.setSizes([int(total * 0.55), int(total * 0.45)])

    def set_camera_status(self, connected: bool):
        if connected:
            self.lbl_cam_status.setText(self.tr("✅ CAM"))
            self.lbl_cam_status.setStyleSheet("background-color: #d4edda; color: #155724; border: 2px solid #c3e6cb; border-radius: 5px; font-weight: bold; font-size: 14px;")
        else:
            self.lbl_cam_status.setText(self.tr("❌ CAM"))
            self.lbl_cam_status.setStyleSheet("background-color: #f8d7da; color: #721c24; border: 2px solid #f5c6cb; border-radius: 5px; font-weight: bold; font-size: 14px;")

    def set_hardware_status(self, connected: bool):
        if connected:
            self.lbl_hw_status.setText(self.tr("✅ HW"))
            self.lbl_hw_status.setStyleSheet("background-color: #d4edda; color: #155724; border: 2px solid #c3e6cb; border-radius: 5px; font-weight: bold; font-size: 14px;")
        else:
            self.lbl_hw_status.setText(self.tr("❌ HW"))
            self.lbl_hw_status.setStyleSheet("background-color: #f8d7da; color: #721c24; border: 2px solid #f5c6cb; border-radius: 5px; font-weight: bold; font-size: 14px;")

    # --- SIMULATION GÂCHETTE CLAVIER ---
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space:
            self.hardware.simulate_trigger_press()
        super().keyPressEvent(event)

    def start_test(self):
        if self.is_test_running: return
        if not self.engine or not self.is_camera_ready:
            QMessageBox.critical(self, self.tr("Erreur"), self.tr("Impossible de lancer l'examen : La caméra n'est pas connectée !"))
            return
        if self.temp_result_meta is not None:
             if QMessageBox.question(self, self.tr("Attention"), self.tr("Un examen est en cours.\nÉcraser ?"), QMessageBox.Yes|QMessageBox.No, QMessageBox.No) == QMessageBox.No: return

        if self.conf.get("general", "enable_beep", True):
            QApplication.beep()
        self.real_flash_timestamp = None
        self.is_test_running = True
        self.hardware.set_recording_state(True)
        self.controls.set_button_running(True)
        self._set_ui_state("IDLE")
        self.selected_historical_exam = None
        
        p = self.conf.config.get("protocol", {})
        base = p.get("baseline_duration", 2.0); flash_s = p.get("flash_duration_ms", 200) / 1000.0; resp = p.get("response_duration", 5.0); count = 1
        self.controls.pb.setRange(0, int((base + flash_s + resp)*count*10))
        self.engine.configure(baseline_duration=base, flash_count=count, flash_duration_ms=int(flash_s*1000), response_duration=resp)
        self.current_laterality = self.controls.get_selected_eye()
        self.current_color = self.controls.get_selected_color()
        
        # Assainissement du nom pour éviter les erreurs de fichier (ex: accents, slashs)
        safe_name = "".join([c if c.isalnum() else "_" for c in self.patient['name']])
        # Sécurité : Si le nom est vide ou ne contient que des underscores (ex: "!!!")
        if not safe_name.replace("_", ""):
            safe_name = f"Patient_{self.patient.get('id', 'Unknown')}"
        self.engine.start_test(f"{safe_name}_{self.current_laterality}_{self.current_color}")
        self.controls.setEnabled(False)

    def on_hardware_flash_fired(self):
        """Capture le moment précis où le flash hardware est envoyé."""
        if self.camera_thread and self.camera_thread.camera and self.camera_thread.camera.recording:
            self.real_flash_timestamp = time.time() - self.camera_thread.camera.start_time

    def on_test_finished(self, meta):
        self.is_test_running = False
        self.hardware.set_recording_state(False)
        self.controls.set_button_running(False)
        self.controls.setEnabled(True)
        self.controls.pb.setFormat(self.tr("Terminé"))
        self.check_ready_state()
        
        # Correction du timestamp si le hardware a tiré (Synchro Graphique)
        if self.real_flash_timestamp is not None:
            meta['flash_timestamp'] = self.real_flash_timestamp
            logging.info(f"Timestamp Flash corrigé (Hardware) : {self.real_flash_timestamp:.3f}s")

        # Vérification explicite si le fichier est vide ou inexistant
        if not os.path.exists(meta['csv_path']) or os.path.getsize(meta['csv_path']) < 100:
            QMessageBox.warning(self, self.tr("Données insuffisantes"), 
                                self.tr("Aucune donnée n'a été enregistrée.\n\nVérifiez que :\n1. La pupille est bien détectée (cercle vert).\n2. L'enregistrement n'a pas été interrompu."))
            self._set_ui_state("IDLE")
            return
            
        an = PLRAnalyzer()
        if not an.load_data(meta['csv_path']):
            QMessageBox.warning(self, self.tr("Erreur"), self.tr("Impossible de lire le fichier de données :\n") + meta['csv_path'])
            return
        an.preprocess()
        met = an.analyze(flash_timestamp=meta['flash_timestamp'])
        met['flash_timestamp'] = meta['flash_timestamp']; met['flash_duration_s'] = meta['config']['flash_duration_ms'] / 1000.0; met['flash_color'] = self.current_color 
        
        # AJOUT: Durée exacte et Intensité
        duration = 0.0
        if an.data is not None and not an.data.empty:
            duration = an.data['timestamp_s'].iloc[-1] - an.data['timestamp_s'].iloc[0]
        met['total_duration_s'] = round(duration, 2)
        met['flash_intensity_percent'] = self.controls.get_intensity_percent()
        
        col = '#b71c1c' if self.current_laterality == 'OD' else '#0d47a1'
        self.graph_widget.plot_data([{'label': f'Actuel ({self.current_laterality})', 'df': an.data, 'metrics': met, 'color': col}], clear=True)
        self.temp_result_meta = {'csv': meta['csv_path'], 'metrics': met}
        # Sauvegarde temporaire du chemin vidéo pour l'enregistrement final
        if 'video_path' in meta: self.temp_result_meta['video_path'] = meta['video_path']
        self._set_ui_state("NEW_RESULT")
        self.grp_actions.setTitle(self.tr("Nouveau Résultat | Durée: {}s | Intensité: {}%").format(met['total_duration_s'], met['flash_intensity_percent']))

    # ... (Le reste : load_patient_history, save, export... reste identique) ...
    def _create_menu(self):
        m = self.menuBar()
        m.addMenu(self.tr("Fichier")).addAction(self.tr("Retour"), self.return_to_home)
        o = m.addMenu(self.tr("Options")); o.addAction(self.tr("Réglages"), self._settings); o.addAction(self.tr("Calibration"), self._calib)
        m.addMenu(self.tr("Aide")).addAction(self.tr("À propos"), lambda: QMessageBox.about(self,"Info","V3.28"))

    def show_history_menu(self, pos):
        item = self.table_hist.itemAt(pos)
        menu = QMenu(self)
        menu_select = menu.addMenu(self.tr("☑️ Sélection Comparaison"))
        act_all = menu_select.addAction(self.tr("Tout cocher")); act_none = menu_select.addAction(self.tr("Tout décocher"))
        act_od = menu_select.addAction(self.tr("Cocher OD uniquement")); act_og = menu_select.addAction(self.tr("Cocher OG uniquement"))
        menu.addSeparator()
        action_view = None; action_pdf = None; action_xls = None; action_del = None; action_frames = None
        if item:
            self.table_hist.selectRow(item.row())
            chk_item = self.table_hist.item(item.row(), 7)
            if chk_item:
                ex_data = chk_item.data(Qt.UserRole)
                action_view = menu.addAction(self.tr("👁️ Voir / Éditer"))
                action_pdf = menu.addAction(self.tr("📄 Exporter PDF"))
                action_xls = menu.addAction(self.tr("📊 Exporter Excel (Data)"))
                _csv = ex_data.get('csv_path', '')
                if os.path.isfile(_csv.replace('.csv', '.avi')) or os.path.isdir(_csv.replace('.csv', '_frames')):
                    action_frames = menu.addAction(self.tr("Film frame par frame"))
                menu.addSeparator()
                action_del = menu.addAction(self.tr("🗑️ Supprimer l'examen"))
            else: ex_data = None
        action = menu.exec(self.table_hist.mapToGlobal(pos))
        if action == act_all: self.batch_selection("ALL")
        elif action == act_none: self.batch_selection("NONE")
        elif action == act_od: self.batch_selection("OD")
        elif action == act_og: self.batch_selection("OG")
        elif item and action == action_view: self.on_history_clicked(self.table_hist.item(item.row(), 0))
        elif item and action == action_pdf: self.selected_historical_exam = ex_data; self.export_pdf()
        elif item and action == action_xls: self.selected_historical_exam = ex_data; self.export_excel()
        elif item and action == action_frames: self.selected_historical_exam = ex_data; self.open_frames_viewer()
        elif item and action == action_del: self.delete_history_item(ex_data)

    def auto_compare_eyes(self):
        """Sélectionne automatiquement le dernier examen de l'autre œil pour comparaison."""
        # 1. Déterminer la latéralité de référence
        ref_lat = None
        if self.temp_result_meta and not self.selected_historical_exam:
            ref_lat = self.current_laterality
        elif self.selected_historical_exam:
            ref_lat = self.selected_historical_exam.get('laterality')
        
        if not ref_lat: return

        target_lat = 'OG' if ref_lat == 'OD' else 'OD'
        found = False

        # 2. Parcourir l'historique pour trouver le dernier examen de l'autre œil
        self.table_hist.blockSignals(True)
        for r in range(self.table_hist.rowCount()):
            item_lat = self.table_hist.item(r, 1)
            item_chk = self.table_hist.item(r, 7)
            
            # On décoche tout d'abord pour avoir une vue propre
            item_chk.setCheckState(Qt.Unchecked)
            
            # Si on trouve le premier match (le plus récent car trié par date DESC)
            if not found and item_lat.text() == target_lat:
                item_chk.setCheckState(Qt.Checked)
                found = True
                
            # Si on est en mode Historique, il faut aussi cocher l'examen qu'on regardait
            if self.selected_historical_exam:
                ex_data = item_chk.data(Qt.UserRole)
                if ex_data['id'] == self.selected_historical_exam['id']:
                    item_chk.setCheckState(Qt.Checked)

        self.table_hist.blockSignals(False)
        
        if found:
            self._update_comparison_graph()
            self.status.showMessage(self.tr("Comparaison OD/OG activée."))
        else:
            QMessageBox.information(self, self.tr("Info"), self.tr("Aucun examen de l'autre œil trouvé pour comparaison."))

    def batch_selection(self, mode):
        self.table_hist.blockSignals(True)
        for r in range(self.table_hist.rowCount()):
            item_chk = self.table_hist.item(r, 7); item_eye = self.table_hist.item(r, 1)
            should = False
            if mode == "ALL": should = True
            elif mode == "NONE": should = False
            elif mode == "OD" and item_eye.text() == "OD": should = True
            elif mode == "OG" and item_eye.text() == "OG": should = True
            item_chk.setCheckState(Qt.Checked if should else Qt.Unchecked)
        self.table_hist.blockSignals(False)
        self._update_comparison_graph()

    def _update_comparison_graph(self):
        curves = []
        if self.temp_result_meta and not self.selected_historical_exam:
            an = PLRAnalyzer(); an.load_data(self.temp_result_meta['csv']); an.preprocess()
            col = '#b71c1c' if self.current_laterality == 'OD' else '#0d47a1'
            curves.append({'label': self.tr('Actuel'), 'df': an.data, 'metrics': self.temp_result_meta['metrics'], 'color': col})
        for r in range(self.table_hist.rowCount()):
            if self.table_hist.item(r, 7).checkState() == Qt.Checked:
                ex = self.table_hist.item(r, 7).data(Qt.UserRole)
                try:
                    an = PLRAnalyzer(); an.load_data(ex['csv_path']); an.preprocess()
                    lat = ex.get('laterality', '?'); col = '#ff8a80' if lat == 'OD' else '#82b1ff'
                    stim = ex.get('results_data', {}).get('flash_color', '?')
                    curves.append({'label': f"{ex['exam_date'].split(' ')[0]} ({lat}-{stim})", 'df': an.data, 'metrics': ex.get('results_data',{}), 'color': col, 'style':'-'})
                except: pass
        self.graph_widget.plot_data(curves, clear=True)

    def delete_history_item(self, ex_data):
        if QMessageBox.question(self, self.tr("Supprimer"), self.tr("Supprimer l'examen du {date} ?").format(date=ex_data['exam_date']), QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_exam(ex_data['id']):
                try: 
                    if os.path.exists(ex_data['csv_path']): os.remove(ex_data['csv_path'])
                except: pass
                self.load_patient_history(); self._set_ui_state("IDLE"); self.status.showMessage(self.tr("Examen supprimé."))

    def _set_ui_state(self, state):
        self.btn_save.setVisible(False); self.btn_discard.setVisible(False)
        self.btn_update_comment.setVisible(False); self.btn_pdf.setVisible(False); self.btn_excel.setVisible(False); self.btn_compare.setVisible(False); self.btn_frames.setVisible(False)
        if state == "IDLE":
            self.grp_actions.setVisible(False); self.txt_comments.clear()
            # Utilisation de la méthode propre clear() qui réinitialise aussi les annotations
            self.graph_widget.clear(); self.temp_result_meta = None
        elif state == "NEW_RESULT":
            self.grp_actions.setVisible(True); self.btn_save.setVisible(True); self.btn_discard.setVisible(True); self.btn_pdf.setVisible(True); self.btn_excel.setVisible(True); self.btn_compare.setVisible(True); self.btn_frames.setVisible(True)
            self.grp_actions.setTitle(self.tr("Nouveau Résultat (Non enregistré)")); self.grp_actions.setStyleSheet("background-color:#e3f2fd; font-weight:bold;")
        elif state == "HISTORY_VIEW":
            self.grp_actions.setVisible(True); self.btn_update_comment.setVisible(True); self.btn_pdf.setVisible(True); self.btn_excel.setVisible(True); self.btn_compare.setVisible(True); self.btn_frames.setVisible(True)
            self.grp_actions.setTitle(self.tr("Examen Historique")); self.grp_actions.setStyleSheet("background-color:#f0f4c3; font-weight:bold;")

    def start_camera(self):
        c = self.conf.config.get("camera", {})
        self.camera_thread = CameraThread(int(c.get("index", 0)))
        self.camera_thread.frame_ready.connect(self.video.update_frame)
        self.camera_thread.camera_started.connect(self.on_camera_started)
        self.camera_thread.error_occurred.connect(self.on_camera_error)
        self.camera_thread.camera_started.connect(self.init_engine)
        self.camera_thread.fps_updated.connect(lambda fps: self.lbl_fps_status.setText(f"{fps:.0f} FPS"))
        self.camera_thread.start()

    def on_camera_started(self): self.is_camera_ready = True; self.set_camera_status(True); self.check_ready_state()
    def on_camera_error(self, err_msg): self.is_camera_ready = False; self.set_camera_status(False); self.check_ready_state(); self.status.showMessage(self.tr("⚠️ Erreur Caméra")); QMessageBox.critical(self, self.tr("Erreur Caméra"), self.tr("Problème détecté :\n\n{err}\n\n👉 Vérifiez le branchement USB.\n👉 Cliquez ensuite sur '🔄 Réinit. Caméra'.").format(err=err_msg))
    
    def on_hardware_status_changed(self, connected: bool):
        self.is_hardware_ready = connected
        self.set_hardware_status(connected)
        if connected:
            self.status.showMessage(self.tr("Matériel connecté sur le port {}.").format(self.hardware.current_port))
            self.hw_reconnect_timer.stop()
            self._send_initial_hardware_config()
        else:
            self.status.showMessage(self.tr("Matériel déconnecté. Recherche automatique..."))
            self.hw_reconnect_timer.start()
        self.check_ready_state()

    def init_engine(self):
        c = self.conf.config.get("camera", {}); d = self.conf.config.get("detection", {})
        self.camera_thread.camera.mm_per_pixel = float(c.get("mm_per_pixel", 0.05))
        self.camera_thread.set_threshold(int(d.get("canny_threshold1", 50)))
        self.camera_thread.set_blur(int(d.get("gaussian_blur", 5)))
        self.camera_thread.camera.roi_w = int(d.get("roi_width", 400)); self.camera_thread.camera.roi_h = int(d.get("roi_height", 400))
        self.camera_thread.camera.roi_off_x = int(d.get("roi_offset_x", 0)); self.camera_thread.camera.roi_off_y = int(d.get("roi_offset_y", 0))
        self.controls.st.blockSignals(True); self.controls.st.setValue(self.camera_thread.camera.threshold_val); self.controls.st.blockSignals(False)
        self.controls.sb.blockSignals(True); self.controls.sb.setValue(self.camera_thread.camera.blur_val); self.controls.sb.blockSignals(False)
        self.engine = PLRTestEngine(self.camera_thread.camera)
        
        # Connexion du signal de flash du moteur vers la méthode de gestion synchronisée
        self.engine.flash_triggered.connect(self.on_flash_triggered)
        
        self.engine.test_finished.connect(self.on_test_finished)
        self.engine.progress_updated.connect(lambda e, p: [self.controls.pb.setValue(int(e*10)), self.controls.pb.setFormat(f"{p} : {e:.1f}s")])
        self.status.showMessage(self.tr("Prêt"))

    def on_flash_triggered(self, active: bool):
        """Gère le déclenchement synchronisé (Ecran + Matériel)."""
        self.lbl_flash_indicator.setVisible(active)
        if active:
            self.hardware.lancer_sequence_synchro() # Séquence Synchro (Black Frame)

    def on_fps_changed(self, fps: int):
        """Change le FPS. Pour 15fps : diviseur seul. Pour les autres : mémorise + reset caméra."""
        self.camera_thread.set_fps(fps)
        if fps != 15:
            # DSHOW ne supporte pas le changement de FPS à chaud → mémorisation + redémarrage
            self.conf.config.setdefault("camera", {})["target_fps"] = fps
            self.reset_camera()

    def reset_camera(self): self.status.showMessage(self.tr("Reset...")); self.is_camera_ready = False; self.set_camera_status(False); self.check_ready_state(); self.stop_camera(); QTimer.singleShot(1000, self.start_camera)
    
    def reset_hardware(self):
        self.status.showMessage(self.tr("Connexion matériel..."))
        if self.connect_hardware_with_progress():
            QMessageBox.information(self, self.tr("Connexion Matériel"), self.tr("Le dispositif est bien connecté sur le port {}").format(self.hardware.current_port))
            self._send_initial_hardware_config()
        else:
            QMessageBox.warning(self, self.tr("Erreur Connexion"), self.tr("Impossible de connecter le dispositif.\nVérifiez le câble USB."))

    def try_auto_reconnect_hw(self):
        """Tente de reconnecter le matériel en arrière-plan si la connexion est perdue."""
        if not self.is_hardware_ready:
            logging.info("Tentative de reconnexion automatique du matériel...")
            self.hardware.connect_device()

    def connect_hardware_with_progress(self):
        """Tente de connecter le matériel avec une fenêtre de progression."""
        # Parent à None pour s'assurer qu'elle s'affiche au premier plan (TopLevel) même si MainWindow est cachée
        progress = QProgressDialog(self.tr("Initialisation du module en cours..."), None, 0, 0, None)
        progress.setWindowTitle(self.tr("Matériel"))
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.setStyleSheet("QProgressBar { text-align: center; }")
        
        progress.show()
        QApplication.processEvents()
        
        success = self.hardware.connect_device()
        
        progress.close()
        return success

    def load_patient_history(self):
        if not self.patient: return
        self.table_hist.setSortingEnabled(False)
        exams = self.db.get_patient_history(self.patient['id'])
        self.table_hist.setRowCount(0)
        for r, ex in enumerate(exams):
            self.table_hist.insertRow(r)
            date_display = ex['exam_date'][:-3] if len(ex['exam_date']) > 16 else ex['exam_date']
            self.table_hist.setItem(r, 0, QTableWidgetItem(date_display))
            
            # --- MODIFICATION OEIL ---
            lat = ex.get('laterality', '?')
            it = QTableWidgetItem(lat)
            # Pas de setForeground ici pour garder le noir standard
            self.table_hist.setItem(r, 1, it)
            
            # --- MODIFICATION STIMULUS (TRADUCTION) ---
            res_data = ex.get('results_data', {})
            stim = res_data.get('flash_color', 'WHITE')
            
            # Traduction Française
            stim_display = stim
            if stim == "BLUE": stim_display = "Bleu"
            elif stim == "RED": stim_display = "Rouge"
            elif stim == "WHITE": stim_display = "Blanc"
            
            it_stim = QTableWidgetItem(stim_display)
            if stim == 'BLUE': it_stim.setForeground(QColor('#007bff'))
            elif stim == 'RED': it_stim.setForeground(QColor('#dc3545'))
            self.table_hist.setItem(r, 2, it_stim)
            
            self.table_hist.setItem(r, 3, QTableWidgetItem(ex.get('exam_type', 'PLR')))
            
            dur = res_data.get('total_duration_s', '-')
            inte = res_data.get('flash_intensity_percent', '-')
            self.table_hist.setItem(r, 4, QTableWidgetItem(f"{dur} s" if dur != '-' else "-"))
            self.table_hist.setItem(r, 5, QTableWidgetItem(f"{inte} %" if inte != '-' else "-"))
            
            self.table_hist.setItem(r, 6, QTableWidgetItem("📝" if ex.get('comments') else ""))
            chk = QTableWidgetItem(); chk.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled); chk.setCheckState(Qt.Unchecked); chk.setData(Qt.UserRole, ex); self.table_hist.setItem(r, 7, chk)
        self.table_hist.setSortingEnabled(True)

    def on_history_clicked(self, item):
        if item.column() == 7: self._update_comparison_graph(); return
        chk_item = self.table_hist.item(item.row(), 7)
        if chk_item is None: return
        ex = chk_item.data(Qt.UserRole)
        self.selected_historical_exam = ex; self.temp_result_meta = None; self._set_ui_state("HISTORY_VIEW")
        self.txt_comments.setText(ex.get('comments', ''))
        try:
            an = PLRAnalyzer()
            if an.load_data(ex['csv_path']):
                an.preprocess()
                col = '#b71c1c' if ex.get('laterality') == 'OD' else '#0d47a1'
                self.graph_widget.plot_data([{'label': f"{ex['exam_date']} ({ex.get('laterality')})", 'df': an.data, 'metrics': ex.get('results_data',{}), 'color': col}], clear=True)
            else:
                QMessageBox.warning(self, self.tr("Fichier introuvable"), self.tr("Le fichier de données semble avoir été déplacé ou supprimé :\n") + ex['csv_path'])
        except Exception as e:
            QMessageBox.critical(self, self.tr("Erreur"), f"Erreur lors de l'affichage : {str(e)}")

    def open_frames_viewer(self):
        """Ouvre le visualiseur frame par frame pour l'examen actuellement affiché."""
        csv_path = None
        if self.selected_historical_exam:
            csv_path = self.selected_historical_exam.get('csv_path')
        elif self.temp_result_meta:
            csv_path = self.temp_result_meta.get('csv')

        if not csv_path:
            QMessageBox.warning(self, self.tr("Aucun examen"), self.tr("Aucun examen sélectionné."))
            return

        avi_path = csv_path.replace('.csv', '.avi')
        frames_dir = csv_path.replace('.csv', '_frames')
        if os.path.isfile(avi_path):
            video_source = avi_path
        elif os.path.isdir(frames_dir):
            video_source = frames_dir
        else:
            QMessageBox.information(self, self.tr("Vidéo indisponible"),
                self.tr("Aucune vidéo trouvée pour cet examen.\n\nFichier attendu :\n{0}").format(avi_path))
            return

        data = None
        results = {}
        if os.path.exists(csv_path):
            try:
                an = PLRAnalyzer()
                if an.load_data(csv_path):
                    an.preprocess()
                    data = an.data
                    results = an.analyze()
            except: pass

        d = PLRResultsDialog(self, data=data, results=results, title=self.tr("Film frame par frame"), video_path=video_source)
        d.exec()

    def open_frame_viewer(self):
        path = QFileDialog.getExistingDirectory(self, self.tr("Sélectionner le dossier de frames"), "data/plr_results")
        if path:
            # Tentative de déduction du CSV associé pour afficher les courbes
            csv_path = path
            if csv_path.endswith("_frames"):
                csv_path = csv_path[:-7] + ".csv"
            
            data = None
            results = {}
            
            if os.path.exists(csv_path):
                try:
                    an = PLRAnalyzer()
                    if an.load_data(csv_path):
                        an.preprocess()
                        data = an.data
                        results = an.analyze()
                except: pass
            
            d = PLRResultsDialog(self, data=data, results=results, title=self.tr("Visualiseur Frame par Frame"), video_path=path)
            d.exec()

    def save_new_exam(self):
        if self.temp_result_meta: 
            vid = self.temp_result_meta.get('video_path', '')
            self.db.save_exam(self.patient['id'], self.current_laterality, self.temp_result_meta['csv'], vid=vid, results=self.temp_result_meta['metrics'], comments=self.txt_comments.toPlainText())
            self._set_ui_state("IDLE"); self.load_patient_history(); self.status.showMessage(self.tr("Sauvegardé."))
    def update_historical_comment(self):
        if self.selected_historical_exam:
            new = self.txt_comments.toPlainText(); eid = self.selected_historical_exam['id']
            if self.db.update_exam_comment(eid, new): self.load_patient_history(); self.status.showMessage(self.tr("Mis à jour.")); self.selected_historical_exam['comments'] = new
    def discard_exam(self):
        if self.temp_result_meta:
            for key in ('csv', 'video_path'):
                try: os.remove(self.temp_result_meta[key])
                except: pass
        self._set_ui_state("IDLE")
    def export_pdf(self):
        if self.selected_historical_exam: ex=self.selected_historical_exam; met=ex.get('results_data',{}); lat=ex.get('laterality'); dat=ex.get('exam_date')
        elif self.temp_result_meta: met=self.temp_result_meta['metrics']; lat=self.current_laterality; dat=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else: return
        fname = f"Rapport_{self.patient['name'].replace(' ','_')}_{dat.split(' ')[0]}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Exporter PDF"), fname, "PDF (*.pdf)")
        if path:
            gen = PDFGenerator(path); exam_info = {"date":dat, "laterality":lat, "stimulus": met.get('flash_color', 'WHITE')}
            gen.generate(self.db.get_clinic_info(), {"name":self.patient['name'], "species":self.patient['species'], "breed":self.patient.get('breed',''), "id":self.patient['tattoo_id'], "owner":self.patient.get('owner_name','')}, exam_info, met, self.txt_comments.toPlainText(), self.graph_widget.fig); QMessageBox.information(self, self.tr("Succès"), self.tr("PDF généré."))
    def export_excel(self):
        if self.selected_historical_exam: ex=self.selected_historical_exam; csv=ex['csv_path']; met=ex.get('results_data',{}); lat=ex.get('laterality'); dat=ex.get('exam_date')
        elif self.temp_result_meta: csv=self.temp_result_meta['csv']; met=self.temp_result_meta['metrics']; lat=self.current_laterality; dat=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else: return
        if not os.path.exists(csv): QMessageBox.warning(self, self.tr("Erreur"), self.tr("Fichier source introuvable.")); return
        fname = f"Data_{self.patient['name'].replace(' ','_')}_{dat.split(' ')[0]}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export Excel"), fname, "Excel (*.xlsx)")
        if path:
            try:
                import pandas as pd
                info = {"Patient":self.patient['name'],"ID":self.patient['tattoo_id'],"Espèce":self.patient['species'],"Date":dat,"Oeil":lat,"Stimulus":met.get('flash_color','WHITE'), "Commentaires":self.txt_comments.toPlainText()}
                with pd.ExcelWriter(path) as w: pd.DataFrame(list({**info, **met}.items()), columns=["Param", "Valeur"]).to_excel(w, sheet_name="Résumé", index=False); pd.read_csv(csv).to_excel(w, sheet_name="Raw_Data", index=False)
                QMessageBox.information(self, self.tr("Succès"), self.tr("Export Excel réussi."))
            except Exception as e: QMessageBox.critical(self, self.tr("Erreur"), str(e))
    def _load_macros(self):
        self.combo_macros.blockSignals(True); self.combo_macros.clear(); self.combo_macros.addItem(self.tr("--- Insérer phrase type ---"))
        for m in self.db.get_macros(): self.combo_macros.addItem(m['content'][:60], m['content'])
        self.combo_macros.blockSignals(False)
    def _insert_macro(self, idx):
        if idx > 0: self.txt_comments.append(self.combo_macros.itemData(idx)); self.combo_macros.setCurrentIndex(0)
    def _settings(self): d = SettingsDialog(self, self.conf); d.settings_changed.connect(self._apply_set); d.exec(); self._load_macros()
    def _apply_set(self, s):
        idx = int(s.get("camera", {}).get("index", 0))
        if self.camera_thread and self.camera_thread.camera_index != idx: self.reset_camera(); return
        if self.camera_thread:
            d=s.get('detection',{}); self.camera_thread.camera.roi_w=int(d.get('roi_width',400)); self.camera_thread.camera.roi_h=int(d.get('roi_height',400)); self.camera_thread.camera.roi_off_x=int(d.get('roi_offset_x',0)); self.camera_thread.camera.roi_off_y=int(d.get('roi_offset_y',0)); self.camera_thread.set_threshold(int(d.get('canny_threshold1',50)))
        
        p = s.get("protocol", {})
        raw = p.get("flash_intensity", 65536)
        self.controls.set_intensity_percent(int((raw/65536.0)*100))
        
        # Mise à jour complète de la configuration hardware
        self.update_hardware_params()

    def _send_initial_hardware_config(self):
        """Envoie la configuration par défaut au matériel après connexion."""
        self.update_hardware_params()

    def update_hardware_params(self):
        """Envoie la configuration complète au matériel (Couleur, Durée, Intensité...)."""
        if not self.hardware.is_connected: return
        
        p = self.conf.config.get("protocol", {})
        flash_s = p.get("flash_duration_ms", 200) / 1000.0
        intensity = int((self.controls.get_intensity_percent() / 100.0) * 65536)
        frequency = p.get("flash_frequency", 0.1)
        ambiance = p.get("ambiance_intensity", 0)
        count = 1
        color = self.controls.get_selected_color()
        
        self.hardware.configure_flash_sequence(color, int(flash_s * 1000), intensity, frequency, ambiance, count)

    def _calib(self): (CalibrationDialog(self.camera_thread.camera, self).exec() if self.camera_thread else None)
    def return_to_home(self): self.stop_camera(); self.w=WelcomeScreen(); self.w.patient_selected.connect(lambda p:[self.w.close(), MainWindow(p).show()]); self.w.show(); self.close()
    def _show_about(self): QMessageBox.about(self, "Infos", "PLR V3.28")
    def stop_camera(self): (self.camera_thread.stop() if self.camera_thread else None)
    def closeEvent(self, e):
        try:
            det = self.conf.config.get("detection", {}); det["canny_threshold1"] = self.controls.st.value(); det["gaussian_blur"] = self.controls.sb.value(); self.conf.config["detection"] = det
            self.conf.config.setdefault("ui", {})["right_split_sizes"] = self.right_split.sizes()
            self.conf.save()
        except: pass
        self.stop_camera()
        self.hw_reconnect_timer.stop()
        if hasattr(self, 'hardware'): self.hardware.disconnect_device()
        e.accept()

def main():
    os.makedirs("data/plr_results", exist_ok=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_modern_theme(app)
    conf = ConfigManager()
    lang = conf.get("general", "language", "fr")
    if lang != "fr":
        trans = QTranslator()
        if trans.load(f"translations/app_{lang}.qm"): app.installTranslator(trans)
    global win; win = None 
    w = WelcomeScreen()
    def launch(p): global win; win = MainWindow(p); win.show()
    w.patient_selected.connect(launch); w.show(); sys.exit(app.exec())

if __name__ == "__main__": main()