"""
main_application.py
===================
Interface Examen V3.22 (Indicateur État Caméra + Sécurité Lancement).
"""

import sys
import os
import cv2
import numpy as np
import json
from datetime import datetime
import logging

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QComboBox, QGroupBox, QMessageBox, 
    QStatusBar, QProgressBar, QTableWidget, QTableWidgetItem, 
    QHeaderView, QAbstractItemView, QRadioButton, QButtonGroup, QSplitter,
    QTextEdit, QFileDialog, QSizePolicy, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer, QPoint, QTranslator, QLibraryInfo
from PySide6.QtGui import QImage, QPixmap, QAction, QColor, QCursor

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

logging.basicConfig(level=logging.INFO)

class FlashOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #FFFFFF;")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(1.0)
        self.setGeometry(QApplication.primaryScreen().geometry())

class CameraThread(QThread):
    frame_ready = Signal(np.ndarray); pupil_detected = Signal(dict); fps_updated = Signal(float); error_occurred = Signal(str); camera_started = Signal()
    def __init__(self, camera_index=0): super().__init__(); self.camera=None; self.camera_index=camera_index; self.running=False
    def run(self):
        try:
            self.camera=CameraEngine(self.camera_index)
            if not self.camera.is_ready(): raise Exception("Impossible d'initialiser la caméra.\nEst-elle bien branchée ?")
            self.running=True; self.camera_started.emit()
            while self.running: 
                f,p=self.camera.grab_and_detect()
                if f is None: raise Exception("Perte du signal vidéo (Déconnexion).")
                self.frame_ready.emit(f); (self.pupil_detected.emit(p) if p else None); self.msleep(1)
        except Exception as e: self.error_occurred.emit(str(e))
        finally: (self.camera.release() if self.camera else None)
    def stop(self): self.running=False; self.wait(2000)
    def set_threshold(self,v): (self.camera.set_threshold(v) if self.camera else None)
    def set_blur(self,v): (self.camera.set_blur_kernel(v) if self.camera else None)
    def set_display_mode(self,m): (self.camera.set_display_mode(m) if self.camera else None)
    def start_recording(self,f): (self.camera.start_csv_recording(f) if self.camera else None)
    def stop_recording(self): (self.camera.stop_csv_recording() if self.camera else None)

class VideoWidget(QLabel):
    def __init__(self): super().__init__(); self.setAlignment(Qt.AlignCenter); self.setStyleSheet("background:black; border:2px solid #444;"); self.setMinimumSize(400,300)
    @Slot(np.ndarray)
    def update_frame(self, f): 
        try: self.setPixmap(QPixmap.fromImage(QImage(cv2.cvtColor(f,cv2.COLOR_BGR2RGB).data, f.shape[1], f.shape[0], f.shape[1]*3, QImage.Format_RGB888)).scaled(self.size(), Qt.KeepAspectRatio))
        except: pass

class ControlPanel(QWidget):
    threshold_changed=Signal(int); blur_changed=Signal(int); display_mode_changed=Signal(str); test_requested=Signal(); settings_requested=Signal(); reset_camera_requested=Signal()
    def __init__(self): super().__init__(); self.setup_ui()
    def setup_ui(self):
        l=QVBoxLayout(self); l.setSpacing(15)
        
        # --- NOUVEAU : INDICATEUR ETAT CAMERA ---
        self.lbl_cam_status = QLabel(self.tr("État Caméra : Inconnu"))
        self.lbl_cam_status.setAlignment(Qt.AlignCenter)
        self.lbl_cam_status.setFixedHeight(35)
        # Style par défaut (Gris)
        self.lbl_cam_status.setStyleSheet("background-color: #e0e0e0; color: #555; border-radius: 5px; font-weight: bold; font-size: 11pt;")
        l.addWidget(self.lbl_cam_status)
        # ----------------------------------------

        ge=QGroupBox(self.tr("Choix de l'Œil")); he=QHBoxLayout(); self.eg=QButtonGroup(self)
        self.rod=QRadioButton(self.tr("OD (Droit)")); self.rod.setStyleSheet("color:#d32f2f;font-weight:bold;"); self.rod.setChecked(True)
        self.rog=QRadioButton(self.tr("OG (Gauche)")); self.rog.setStyleSheet("color:#1976d2;font-weight:bold;")
        self.eg.addButton(self.rod); self.eg.addButton(self.rog); he.addWidget(self.rod); he.addWidget(self.rog); ge.setLayout(he); l.addWidget(ge)
        
        gs=QGroupBox(self.tr("Réglages Caméra")); fl=QVBoxLayout()
        self.st=QSlider(Qt.Horizontal); self.st.setRange(0,255); self.st.setValue(50); self.st.valueChanged.connect(self.threshold_changed.emit)
        self.sb=QSlider(Qt.Horizontal); self.sb.setRange(1,21); self.sb.setValue(5); self.sb.valueChanged.connect(self.blur_changed.emit)
        self.cm=QComboBox(); self.cm.addItems(["Normal","ROI","Binaire","Mosaïque"]); self.cm.currentTextChanged.connect(lambda t:self._on_mode(t))
        fl.addWidget(QLabel(self.tr("Seuil"))); fl.addWidget(self.st); fl.addWidget(QLabel(self.tr("Flou"))); fl.addWidget(self.sb); fl.addWidget(QLabel(self.tr("Vue"))); fl.addWidget(self.cm); gs.setLayout(fl); l.addWidget(gs)
        
        self.bt=QPushButton(self.tr("▶ LANCER EXAMEN")); self.bt.setFixedHeight(50); self.bt.setStyleSheet("background:#28a745;color:white;font-weight:bold;border-radius:5px;"); self.bt.clicked.connect(self.test_requested.emit)
        self.pb=QProgressBar(); self.pb.setAlignment(Qt.AlignCenter); self.pb.setValue(0); self.pb.setStyleSheet("QProgressBar{border:1px solid #999;border-radius:5px;text-align:center;} QProgressBar::chunk{background-color:#28a745;}")
        self.br=QPushButton(self.tr("🔄 Réinit. Caméra")); self.br.setStyleSheet("background:#e67e22;color:white;padding:5px;border-radius:4px;"); self.br.clicked.connect(self.reset_camera_requested.emit)
        l.addWidget(self.bt); l.addWidget(self.pb); l.addWidget(self.br); l.addStretch()
        
    def _on_mode(self,t): 
        mode = "normal"
        if "ROI" in t: mode="roi"
        elif "Binaire" in t or "Binary" in t: mode="binary"
        elif "Mosa" in t: mode="mosaic"
        self.display_mode_changed.emit(mode)
        
    def get_selected_eye(self): return "OD" if self.rod.isChecked() else "OG"

    # --- NOUVEAU : Fonction pour mettre à jour l'indicateur ---
    def set_camera_status(self, connected: bool):
        if connected:
            self.lbl_cam_status.setText(self.tr("✅ CAMÉRA CONNECTÉE"))
            self.lbl_cam_status.setStyleSheet("background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 5px; font-weight: bold;")
        else:
            self.lbl_cam_status.setText(self.tr("❌ CAMÉRA DÉCONNECTÉE"))
            self.lbl_cam_status.setStyleSheet("background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 5px; font-weight: bold;")

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
        self.total_test_duration = 0.0
        self.current_laterality = 'OD'
        
        # --- ETAT DE LA CAMERA ---
        self.is_camera_ready = False 
        
        self.setup_ui()
        self.start_camera()
        if self.patient: 
            self.setWindowTitle(self.tr("Dossier Patient : {name} ({species})").format(name=self.patient['name'], species=self.patient['species']))
            self.load_patient_history()

    def setup_ui(self):
        self.resize(1400, 950)
        central = QWidget(); self.setCentralWidget(central); main_lay = QHBoxLayout(central)
        
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0)
        self.video = VideoWidget(); self.controls = ControlPanel()
        self.controls.threshold_changed.connect(lambda v: self.camera_thread.set_threshold(v))
        self.controls.blur_changed.connect(lambda v: self.camera_thread.set_blur(v))
        self.controls.display_mode_changed.connect(lambda m: self.camera_thread.set_display_mode(m))
        self.controls.test_requested.connect(self.start_test)
        self.controls.reset_camera_requested.connect(self.reset_camera)
        ll.addWidget(self.video, 3); ll.addWidget(self.controls, 1)
        
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
        
        self.btn_update_comment.setStyleSheet("background:#007bff;color:white;font-weight:bold;padding:5px;"); self.btn_pdf.setStyleSheet("background:#17a2b8;color:white;font-weight:bold;padding:5px;")
        hl_act.addWidget(self.btn_save); hl_act.addWidget(self.btn_discard); hl_act.addWidget(self.btn_update_comment); hl_act.addWidget(self.btn_pdf); hl_act.addWidget(self.btn_excel)
        self.grp_actions.setLayout(hl_act); self.grp_actions.setVisible(False)
        
        self.grp_com = QGroupBox(self.tr("Rapport / Commentaires"))
        vl_com = QVBoxLayout(); hl_mac = QHBoxLayout()
        self.combo_macros = QComboBox(); self.combo_macros.addItem(self.tr("--- Insérer phrase type ---"))
        self._load_macros(); self.combo_macros.currentIndexChanged.connect(self._insert_macro)
        hl_mac.addWidget(self.combo_macros); hl_mac.addStretch()
        self.txt_comments = QTextEdit(); self.txt_comments.setPlaceholderText(self.tr("Observations..."))
        self.txt_comments.setMaximumHeight(80)
        vl_com.addLayout(hl_mac); vl_com.addWidget(self.txt_comments)
        self.grp_com.setLayout(vl_com)

        self.grp_hist = QGroupBox(self.tr("Historique (Clic Droit pour options, Clic Entête pour trier)")); vl_hist = QVBoxLayout()
        self.table_hist = QTableWidget(0, 5); self.table_hist.setHorizontalHeaderLabels([self.tr("Date & Heure"),self.tr("Oeil"),self.tr("Type"),self.tr("Note"),self.tr("Comp")])
        self.table_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_hist.setSelectionBehavior(QAbstractItemView.SelectRows); self.table_hist.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_hist.setSortingEnabled(True)
        self.table_hist.setContextMenuPolicy(Qt.CustomContextMenu); self.table_hist.customContextMenuRequested.connect(self.show_history_menu)
        self.table_hist.itemClicked.connect(self.on_history_clicked)
        vl_hist.addWidget(self.table_hist); self.grp_hist.setLayout(vl_hist)
        
        bl.addWidget(self.grp_actions); bl.addWidget(self.grp_com); bl.addWidget(self.grp_hist)
        right_split.addWidget(self.graph_widget); right_split.addWidget(bottom_w)
        right_split.setStretchFactor(0, 5); right_split.setStretchFactor(1, 5)
        
        main_lay.addWidget(QSplitter(Qt.Horizontal)); main_lay.itemAt(0).widget().addWidget(left); main_lay.itemAt(0).widget().addWidget(right_split); main_lay.itemAt(0).widget().setSizes([500,900])
        
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self._create_menu(); self.load_patient_history(); self._set_ui_state("IDLE")

    def _create_menu(self):
        m = self.menuBar()
        m.addMenu(self.tr("Fichier")).addAction(self.tr("Retour"), self.return_to_home)
        o = m.addMenu(self.tr("Options")); o.addAction(self.tr("Réglages"), self._settings); o.addAction(self.tr("Calibration"), self._calib)
        m.addMenu(self.tr("Aide")).addAction(self.tr("À propos"), lambda: QMessageBox.about(self,"Info","V3.22"))

    def show_history_menu(self, pos):
        item = self.table_hist.itemAt(pos)
        menu = QMenu(self)
        menu_select = menu.addMenu(self.tr("☑️ Sélection Comparaison"))
        act_all = menu_select.addAction(self.tr("Tout cocher")); act_none = menu_select.addAction(self.tr("Tout décocher"))
        act_od = menu_select.addAction(self.tr("Cocher OD uniquement")); act_og = menu_select.addAction(self.tr("Cocher OG uniquement"))
        menu.addSeparator()
        action_view = None; action_pdf = None; action_xls = None; action_del = None
        
        if item:
            self.table_hist.selectRow(item.row())
            ex_data = self.table_hist.item(item.row(), 4).data(Qt.UserRole)
            action_view = menu.addAction(self.tr("👁️ Voir / Éditer"))
            action_pdf = menu.addAction(self.tr("📄 Exporter PDF"))
            action_xls = menu.addAction(self.tr("📊 Exporter Excel (Data)"))
            menu.addSeparator()
            action_del = menu.addAction(self.tr("🗑️ Supprimer l'examen"))
        
        action = menu.exec(self.table_hist.mapToGlobal(pos))
        if action == act_all: self.batch_selection("ALL")
        elif action == act_none: self.batch_selection("NONE")
        elif action == act_od: self.batch_selection("OD")
        elif action == act_og: self.batch_selection("OG")
        elif item and action == action_view: self.on_history_clicked(self.table_hist.item(item.row(), 0))
        elif item and action == action_pdf: self.selected_historical_exam = ex_data; self.export_pdf()
        elif item and action == action_xls: self.selected_historical_exam = ex_data; self.export_excel()
        elif item and action == action_del: self.delete_history_item(ex_data)

    def batch_selection(self, mode):
        self.table_hist.blockSignals(True)
        for r in range(self.table_hist.rowCount()):
            item_chk = self.table_hist.item(r, 4); item_eye = self.table_hist.item(r, 1)
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
            if self.table_hist.item(r, 4).checkState() == Qt.Checked:
                ex = self.table_hist.item(r, 4).data(Qt.UserRole)
                try:
                    an = PLRAnalyzer(); an.load_data(ex['csv_path']); an.preprocess()
                    lat = ex.get('laterality', '?'); col = '#ff8a80' if lat == 'OD' else '#82b1ff'
                    curves.append({'label': f"{ex['exam_date'].split(' ')[0]} ({lat})", 'df': an.data, 'metrics': ex.get('results_data',{}), 'color': col, 'style':'-'})
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
        self.btn_update_comment.setVisible(False); self.btn_pdf.setVisible(False); self.btn_excel.setVisible(False)
        if state == "IDLE":
            self.grp_actions.setVisible(False); self.txt_comments.clear()
            self.graph_widget.axes.clear(); self.graph_widget.canvas.draw(); self.temp_result_meta = None
        elif state == "NEW_RESULT":
            self.grp_actions.setVisible(True); self.btn_save.setVisible(True); self.btn_discard.setVisible(True); self.btn_pdf.setVisible(True); self.btn_excel.setVisible(True)
            self.grp_actions.setTitle(self.tr("Nouveau Résultat (Non enregistré)")); self.grp_actions.setStyleSheet("background-color:#e3f2fd; font-weight:bold;")
        elif state == "HISTORY_VIEW":
            self.grp_actions.setVisible(True); self.btn_update_comment.setVisible(True); self.btn_pdf.setVisible(True); self.btn_excel.setVisible(True)
            self.grp_actions.setTitle(self.tr("Examen Historique")); self.grp_actions.setStyleSheet("background-color:#f0f4c3; font-weight:bold;")

    def start_camera(self):
        c = self.conf.config.get("camera", {})
        self.camera_thread = CameraThread(int(c.get("index", 0)))
        self.camera_thread.frame_ready.connect(self.video.update_frame)
        
        # Connexions des signaux d'état
        self.camera_thread.camera_started.connect(self.on_camera_started)
        self.camera_thread.error_occurred.connect(self.on_camera_error)
        self.camera_thread.camera_started.connect(self.init_engine)
        
        self.camera_thread.start()

    # --- SLOTS GESTION ETAT CAMERA ---
    def on_camera_started(self):
        """Appelé quand la caméra est prête."""
        self.is_camera_ready = True
        self.controls.set_camera_status(True)
        self.controls.bt.setEnabled(True)

    def on_camera_error(self, err_msg):
        """Appelé quand la caméra plante ou ne démarre pas."""
        self.is_camera_ready = False
        self.controls.set_camera_status(False)
        self.controls.bt.setEnabled(False)
        
        self.status.showMessage(self.tr("⚠️ Erreur Caméra"))
        QMessageBox.critical(self, self.tr("Erreur Caméra"), self.tr("Problème détecté :\n\n{err}\n\n👉 Vérifiez le branchement USB.\n👉 Cliquez ensuite sur '🔄 Réinit. Caméra'.").format(err=err_msg))

    def init_engine(self):
        # Cette fonction est maintenant appelée après on_camera_started
        c = self.conf.config.get("camera", {}); d = self.conf.config.get("detection", {})
        self.camera_thread.camera.mm_per_pixel = float(c.get("mm_per_pixel", 0.05))
        self.camera_thread.set_threshold(int(d.get("canny_threshold1", 50)))
        self.camera_thread.set_blur(int(d.get("gaussian_blur", 5)))
        self.camera_thread.camera.roi_w = int(d.get("roi_width", 400)); self.camera_thread.camera.roi_h = int(d.get("roi_height", 400))
        self.camera_thread.camera.roi_off_x = int(d.get("roi_offset_x", 0)); self.camera_thread.camera.roi_off_y = int(d.get("roi_offset_y", 0))
        self.controls.st.blockSignals(True); self.controls.st.setValue(self.camera_thread.camera.threshold_val); self.controls.st.blockSignals(False)
        self.controls.sb.blockSignals(True); self.controls.sb.setValue(self.camera_thread.camera.blur_val); self.controls.sb.blockSignals(False)
        self.engine = PLRTestEngine(self.camera_thread.camera)
        self.engine.flash_triggered.connect(self.trigger_flash)
        self.engine.test_finished.connect(self.on_test_finished)
        self.engine.progress_updated.connect(lambda e, p: [self.controls.pb.setValue(int(e*10)), self.controls.pb.setFormat(f"{p} : {e:.1f}s")])
        self.status.showMessage(self.tr("Prêt"))

    def reset_camera(self): 
        self.status.showMessage(self.tr("Reset..."))
        self.is_camera_ready = False
        self.controls.set_camera_status(False)
        self.stop_camera()
        QTimer.singleShot(1000, self.start_camera)

    def trigger_flash(self, on): (self.flash.showFullScreen() if on else self.flash.close()) if hasattr(self, 'flash') else (setattr(self, 'flash', FlashOverlay()), self.flash.showFullScreen() if on else self.flash.close())

    def start_test(self):
        # --- VERIFICATION CRITIQUE AVANT LANCEMENT ---
        if not self.engine or not self.is_camera_ready:
            QMessageBox.critical(self, self.tr("Erreur"), self.tr("Impossible de lancer l'examen : La caméra n'est pas connectée !"))
            return
        # ---------------------------------------------

        if self.temp_result_meta is not None:
            if QMessageBox.question(self, self.tr("Attention"), self.tr("Un examen est en cours.\nÉcraser ?"), QMessageBox.Yes|QMessageBox.No, QMessageBox.No) == QMessageBox.No: return
        self._set_ui_state("IDLE"); self.selected_historical_exam = None
        p = self.conf.config.get("protocol", {})
        base = p.get("baseline_duration", 2.0); flash_s = p.get("flash_duration_ms", 200) / 1000.0; resp = p.get("response_duration", 5.0); count = p.get("flash_count", 1)
        self.controls.pb.setRange(0, int((base + flash_s + resp)*count*10))
        self.engine.configure(baseline_duration=base, flash_count=count, flash_duration_ms=int(flash_s*1000), response_duration=resp)
        self.current_laterality = self.controls.get_selected_eye()
        self.engine.start_test(f"{self.patient['name']}_{self.current_laterality}")
        self.controls.setEnabled(False)

    def on_test_finished(self, meta):
        self.controls.setEnabled(True); self.controls.pb.setFormat(self.tr("Terminé"))
        if os.path.getsize(meta['csv_path']) < 100: return
        an = PLRAnalyzer()
        if an.load_data(meta['csv_path']):
            an.preprocess()
            met = an.analyze(flash_timestamp=meta['flash_timestamp'])
            met['flash_timestamp'] = meta['flash_timestamp']; met['flash_duration_s'] = meta['config']['flash_duration_ms'] / 1000.0
            col = '#b71c1c' if self.current_laterality == 'OD' else '#0d47a1'
            self.graph_widget.plot_data([{'label': f'Actuel ({self.current_laterality})', 'df': an.data, 'metrics': met, 'color': col}], clear=True)
            self.temp_result_meta = {'csv': meta['csv_path'], 'metrics': met}
            self._set_ui_state("NEW_RESULT")

    def load_patient_history(self):
        if not self.patient: return
        self.table_hist.setSortingEnabled(False)
        exams = self.db.get_patient_history(self.patient['id'])
        self.table_hist.setRowCount(0)
        for r, ex in enumerate(exams):
            self.table_hist.insertRow(r)
            date_display = ex['exam_date'][:-3] if len(ex['exam_date']) > 16 else ex['exam_date']
            self.table_hist.setItem(r, 0, QTableWidgetItem(date_display))
            lat = ex.get('laterality', '?')
            it = QTableWidgetItem(lat); it.setForeground(QColor('red' if lat=='OD' else 'blue')); self.table_hist.setItem(r, 1, it)
            self.table_hist.setItem(r, 2, QTableWidgetItem(ex.get('exam_type', 'PLR')))
            self.table_hist.setItem(r, 3, QTableWidgetItem("📝" if ex.get('comments') else ""))
            chk = QTableWidgetItem(); chk.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled); chk.setCheckState(Qt.Unchecked); chk.setData(Qt.UserRole, ex)
            self.table_hist.setItem(r, 4, chk)
        self.table_hist.setSortingEnabled(True)

    def on_history_clicked(self, item):
        if item.column() == 4:
            self._update_comparison_graph()
            return
        ex = self.table_hist.item(item.row(), 4).data(Qt.UserRole)
        self.selected_historical_exam = ex; self.temp_result_meta = None; self._set_ui_state("HISTORY_VIEW")
        self.txt_comments.setText(ex.get('comments', ''))
        try:
            an = PLRAnalyzer(); an.load_data(ex['csv_path']); an.preprocess()
            col = '#b71c1c' if ex.get('laterality') == 'OD' else '#0d47a1'
            self.graph_widget.plot_data([{'label': f"{ex['exam_date']} ({ex.get('laterality')})", 'df': an.data, 'metrics': ex.get('results_data',{}), 'color': col}], clear=True)
        except: pass

    def save_new_exam(self):
        if self.temp_result_meta:
            self.db.save_exam(self.patient['id'], self.current_laterality, self.temp_result_meta['csv'], results=self.temp_result_meta['metrics'], comments=self.txt_comments.toPlainText())
            self._set_ui_state("IDLE"); self.load_patient_history(); self.status.showMessage(self.tr("Sauvegardé."))

    def update_historical_comment(self):
        if self.selected_historical_exam:
            new = self.txt_comments.toPlainText(); eid = self.selected_historical_exam['id']
            if self.db.update_exam_comment(eid, new):
                self.load_patient_history(); self.status.showMessage(self.tr("Mis à jour."))
                self.selected_historical_exam['comments'] = new

    def discard_exam(self):
        if self.temp_result_meta:
            try: os.remove(self.temp_result_meta['csv'])
            except: pass
        self._set_ui_state("IDLE")

    def export_pdf(self):
        if self.selected_historical_exam: ex=self.selected_historical_exam; met=ex.get('results_data',{}); lat=ex.get('laterality'); dat=ex.get('exam_date')
        elif self.temp_result_meta: met=self.temp_result_meta['metrics']; lat=self.current_laterality; dat=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else: return
        fname = f"Rapport_{self.patient['name'].replace(' ','_')}_{dat.split(' ')[0]}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Exporter PDF"), fname, "PDF (*.pdf)")
        if path:
            gen = PDFGenerator(path)
            gen.generate(self.db.get_clinic_info(), {"name":self.patient['name'], "species":self.patient['species'], "breed":self.patient.get('breed',''), "id":self.patient['tattoo_id'], "owner":self.patient.get('owner_name','')},
                         {"date":dat, "laterality":lat}, met, self.txt_comments.toPlainText(), self.graph_widget.fig)
            QMessageBox.information(self, self.tr("Succès"), self.tr("PDF généré."))

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
                info = {"Patient":self.patient['name'],"ID":self.patient['tattoo_id'],"Espèce":self.patient['species'],"Date":dat,"Oeil":lat,"Commentaires":self.txt_comments.toPlainText()}
                with pd.ExcelWriter(path) as w:
                    pd.DataFrame(list({**info, **met}.items()), columns=["Param", "Valeur"]).to_excel(w, sheet_name="Résumé", index=False)
                    pd.read_csv(csv).to_excel(w, sheet_name="Raw_Data", index=False)
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
            d=s.get('detection',{}); self.camera_thread.camera.roi_w=int(d.get('roi_width',400)); self.camera_thread.camera.roi_h=int(d.get('roi_height',400))
            self.camera_thread.camera.roi_off_x=int(d.get('roi_offset_x',0)); self.camera_thread.camera.roi_off_y=int(d.get('roi_offset_y',0))
            self.camera_thread.set_threshold(int(d.get('canny_threshold1',50)))
    def _calib(self): (CalibrationDialog(self.camera_thread.camera, self).exec() if self.camera_thread else None)
    def return_to_home(self): self.stop_camera(); self.w=WelcomeScreen(); self.w.patient_selected.connect(lambda p:[self.w.close(), MainWindow(p).show()]); self.w.show(); self.close()
    def _show_about(self): QMessageBox.about(self, "Infos", "PLR V3.22")
    def stop_camera(self): (self.camera_thread.stop() if self.camera_thread else None)
    def closeEvent(self, e):
        try:
            det = self.conf.config.get("detection", {})
            det["canny_threshold1"] = self.controls.st.value(); det["gaussian_blur"] = self.controls.sb.value()
            self.conf.config["detection"] = det; self.conf.save()
        except: pass
        self.stop_camera(); e.accept()

def main():
    os.makedirs("data/plr_results", exist_ok=True)
    app = QApplication(sys.argv); app.setStyle("Fusion")
    
    # --- APPLIQUER LE STYLE ---
    apply_modern_theme(app)
    # --------------------------
    
    conf = ConfigManager()
    lang = conf.get("general", "language", "fr")
    if lang != "fr":
        trans = QTranslator()
        if trans.load(f"translations/app_{lang}.qm"):
            app.installTranslator(trans)

    global win; win = None 
    w = WelcomeScreen()
    def launch(p): global win; win = MainWindow(p); win.show()
    w.patient_selected.connect(launch); w.show(); sys.exit(app.exec())

if __name__ == "__main__": main()