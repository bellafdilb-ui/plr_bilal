"""
main_application.py
===================
Interface Examen V3.13 (Protection anti-écrasement des données).
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
    QTextEdit, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer
from PySide6.QtGui import QImage, QPixmap, QAction, QColor

# --- IMPORTS PROJET ---
from camera_engine import CameraEngine
from settings_dialog import SettingsDialog, ConfigManager
from plr_test_engine import PLRTestEngine
from plr_analyzer import PLRAnalyzer
from plr_results_viewer import PLRGraphWidget
from db_manager import DatabaseManager
from welcome_screen import WelcomeScreen
from calibration_dialog import CalibrationDialog
from pdf_generator import PDFGenerator

logging.basicConfig(level=logging.INFO)

# ===========================
# WIDGETS UTILITAIRES
# ===========================
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
            self.camera=CameraEngine(self.camera_index); self.running=True; self.camera_started.emit()
            while self.running: f,p=self.camera.grab_and_detect(); self.frame_ready.emit(f); (self.pupil_detected.emit(p) if p else None); self.msleep(1)
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
        ge=QGroupBox("Choix de l'Œil"); he=QHBoxLayout(); self.eg=QButtonGroup(self)
        self.rod=QRadioButton("OD (Droit)"); self.rod.setStyleSheet("color:#d32f2f;font-weight:bold;"); self.rod.setChecked(True)
        self.rog=QRadioButton("OG (Gauche)"); self.rog.setStyleSheet("color:#1976d2;font-weight:bold;")
        self.eg.addButton(self.rod); self.eg.addButton(self.rog); he.addWidget(self.rod); he.addWidget(self.rog); ge.setLayout(he); l.addWidget(ge)
        
        gs=QGroupBox("Réglages Caméra"); fl=QVBoxLayout()
        self.st=QSlider(Qt.Horizontal); self.st.setRange(0,255); self.st.setValue(50); self.st.valueChanged.connect(self.threshold_changed.emit)
        self.sb=QSlider(Qt.Horizontal); self.sb.setRange(1,21); self.sb.setValue(5); self.sb.valueChanged.connect(self.blur_changed.emit)
        self.cm=QComboBox(); self.cm.addItems(["Normal","ROI","Binaire","Mosaïque"]); self.cm.currentTextChanged.connect(lambda t:self._on_mode(t))
        fl.addWidget(QLabel("Seuil")); fl.addWidget(self.st); fl.addWidget(QLabel("Flou")); fl.addWidget(self.sb); fl.addWidget(QLabel("Vue")); fl.addWidget(self.cm); gs.setLayout(fl); l.addWidget(gs)
        
        self.bt=QPushButton("▶ LANCER EXAMEN"); self.bt.setFixedHeight(50); self.bt.setStyleSheet("background:#28a745;color:white;font-weight:bold;border-radius:5px;"); self.bt.clicked.connect(self.test_requested.emit)
        self.pb=QProgressBar(); self.pb.setAlignment(Qt.AlignCenter); self.pb.setValue(0); self.pb.setStyleSheet("QProgressBar{border:1px solid #999;border-radius:5px;text-align:center;} QProgressBar::chunk{background-color:#28a745;}")
        self.br=QPushButton("🔄 Réinit. Caméra"); self.br.setStyleSheet("background:#e67e22;color:white;padding:5px;border-radius:4px;"); self.br.clicked.connect(self.reset_camera_requested.emit)
        l.addWidget(self.bt); l.addWidget(self.pb); l.addWidget(self.br); l.addStretch()
        self.li=QLabel("--"); self.li.setAlignment(Qt.AlignCenter); l.addWidget(self.li)
    def _on_mode(self,t): self.display_mode_changed.emit({"Normal":"normal","ROI":"roi","Binaire":"binary","Mosaïque":"mosaic"}[t])
    def update_info(self, d=None, q=None): self.li.setText(f"Ø: {d:.2f}mm | Q: {q:.0f}%")
    def get_selected_eye(self): return "OD" if self.rod.isChecked() else "OG"

# ===========================
# MAIN WINDOW
# ===========================
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
        
        self.setup_ui()
        self.start_camera()
        if self.patient:
            self.setWindowTitle(f"Dossier Patient : {self.patient['name']} ({self.patient['species']})")
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
        
        self.grp_actions = QGroupBox("Actions"); self.grp_actions.setStyleSheet("background-color:#f0f4c3; font-weight:bold;")
        self.grp_actions.setMaximumHeight(80); hl_act = QHBoxLayout()
        self.btn_save = QPushButton("💾 SAUVEGARDER NOUVEAU"); self.btn_save.clicked.connect(self.save_new_exam)
        self.btn_discard = QPushButton("🗑️ Jeter"); self.btn_discard.clicked.connect(self.discard_exam)
        self.btn_save.setStyleSheet("background:#28a745;color:white;font-weight:bold;padding:5px;"); self.btn_discard.setStyleSheet("background:#dc3545;color:white;padding:5px;")
        
        self.btn_update_comment = QPushButton("💾 MAJ Commentaire"); self.btn_update_comment.clicked.connect(self.update_historical_comment)
        self.btn_pdf = QPushButton("📄 EXPORT PDF"); self.btn_pdf.clicked.connect(self.export_pdf)
        self.btn_update_comment.setStyleSheet("background:#007bff;color:white;font-weight:bold;padding:5px;"); self.btn_pdf.setStyleSheet("background:#17a2b8;color:white;font-weight:bold;padding:5px;")
        
        hl_act.addWidget(self.btn_save); hl_act.addWidget(self.btn_discard) 
        hl_act.addWidget(self.btn_update_comment); hl_act.addWidget(self.btn_pdf)
        self.grp_actions.setLayout(hl_act); self.grp_actions.setVisible(False)
        
        self.grp_com = QGroupBox("Rapport / Commentaires")
        vl_com = QVBoxLayout(); hl_mac = QHBoxLayout()
        self.combo_macros = QComboBox(); self.combo_macros.addItem("--- Insérer phrase type ---")
        self._load_macros(); self.combo_macros.currentIndexChanged.connect(self._insert_macro)
        hl_mac.addWidget(self.combo_macros); hl_mac.addStretch()
        self.txt_comments = QTextEdit(); self.txt_comments.setPlaceholderText("Observations...")
        self.txt_comments.setMaximumHeight(80)
        vl_com.addLayout(hl_mac); vl_com.addWidget(self.txt_comments)
        self.grp_com.setLayout(vl_com)

        self.grp_hist = QGroupBox("Historique"); vl_hist = QVBoxLayout()
        self.table_hist = QTableWidget(0, 5); self.table_hist.setHorizontalHeaderLabels(["Date","Oeil","Type","Note","Comp"])
        self.table_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_hist.setSelectionBehavior(QAbstractItemView.SelectRows); self.table_hist.setEditTriggers(QAbstractItemView.NoEditTriggers)
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
        m.addMenu("Fichier").addAction("Retour", self.return_to_home)
        o = m.addMenu("Options"); o.addAction("Réglages", self._settings); o.addAction("Calibration", self._calib)
        m.addMenu("Aide").addAction("À propos", lambda: QMessageBox.about(self,"Info","V3.13"))

    def _set_ui_state(self, state):
        self.btn_save.setVisible(False); self.btn_discard.setVisible(False)
        self.btn_update_comment.setVisible(False); self.btn_pdf.setVisible(False)
        
        if state == "IDLE":
            self.grp_actions.setVisible(False); self.txt_comments.clear()
            self.graph_widget.axes.clear(); self.graph_widget.canvas.draw()
            # CRITIQUE : ON NETTOIE LA VARIABLE TEMPORAIRE ICI
            self.temp_result_meta = None
            
        elif state == "NEW_RESULT":
            self.grp_actions.setVisible(True); self.btn_save.setVisible(True); self.btn_discard.setVisible(True); self.btn_pdf.setVisible(True)
            self.grp_actions.setTitle("Nouveau Résultat (Non enregistré)"); self.grp_actions.setStyleSheet("background-color:#e3f2fd; font-weight:bold;")
            
        elif state == "HISTORY_VIEW":
            self.grp_actions.setVisible(True); self.btn_update_comment.setVisible(True); self.btn_pdf.setVisible(True)
            self.grp_actions.setTitle("Examen Historique"); self.grp_actions.setStyleSheet("background-color:#f0f4c3; font-weight:bold;")

    def start_camera(self):
        c = self.conf.config.get("camera", {})
        self.camera_thread = CameraThread(int(c.get("index", 0)))
        self.camera_thread.frame_ready.connect(self.video.update_frame)
        self.camera_thread.pupil_detected.connect(lambda d: self.controls.update_info(d['diameter_mm'], d['quality_score']))
        self.camera_thread.camera_started.connect(self.init_engine)
        self.camera_thread.start()

    def init_engine(self):
        c = self.conf.config.get("camera", {}); d = self.conf.config.get("detection", {})
        self.camera_thread.camera.mm_per_pixel = float(c.get("mm_per_pixel", 0.05))
        self.camera_thread.set_threshold(int(d.get("canny_threshold1", 50)))
        self.camera_thread.set_blur(int(d.get("gaussian_blur", 5)))
        self.camera_thread.camera.roi_w = int(d.get("roi_width", 400))
        self.camera_thread.camera.roi_h = int(d.get("roi_height", 400))
        self.camera_thread.camera.roi_off_x = int(d.get("roi_offset_x", 0))
        self.camera_thread.camera.roi_off_y = int(d.get("roi_offset_y", 0))
        self.controls.st.blockSignals(True); self.controls.st.setValue(self.camera_thread.camera.threshold_val); self.controls.st.blockSignals(False)
        self.controls.sb.blockSignals(True); self.controls.sb.setValue(self.camera_thread.camera.blur_val); self.controls.sb.blockSignals(False)
        self.engine = PLRTestEngine(self.camera_thread.camera)
        self.engine.flash_triggered.connect(self.trigger_flash)
        self.engine.test_finished.connect(self.on_test_finished)
        self.engine.progress_updated.connect(lambda e, p: [self.controls.pb.setValue(int(e*10)), self.controls.pb.setFormat(f"{p} : {e:.1f}s")])
        self.status.showMessage("Prêt")

    def reset_camera(self): self.stop_camera(); QTimer.singleShot(500, self.start_camera)
    def trigger_flash(self, on): (self.flash.showFullScreen() if on else self.flash.close()) if hasattr(self, 'flash') else (setattr(self, 'flash', FlashOverlay()), self.flash.showFullScreen() if on else self.flash.close())

    def start_test(self):
        if not self.engine: return
        
        # --- PROTECTION ANTI-ÉCRASEMENT ---
        if self.temp_result_meta is not None:
            reply = QMessageBox.question(self, "Attention", 
                                         "Un examen est en cours et non sauvegardé.\nVoulez-vous l'écraser ?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        # ----------------------------------

        self._set_ui_state("IDLE"); self.selected_historical_exam = None
        p = self.conf.config.get("protocol", {})
        self.controls.pb.setRange(0, int((p.get("baseline_duration", 2)+p.get("flash_count", 1)*6)*10))
        self.engine.configure(baseline_duration=p.get("baseline_duration", 2), flash_count=p.get("flash_count", 1), 
                              flash_duration_ms=p.get("flash_duration_ms", 200), response_duration=p.get("response_duration", 5))
        self.current_laterality = self.controls.get_selected_eye()
        self.engine.start_test(f"{self.patient['name']}_{self.current_laterality}")
        self.controls.setEnabled(False)

    def on_test_finished(self, meta):
        self.controls.setEnabled(True); self.controls.pb.setFormat("Terminé")
        if os.path.getsize(meta['csv_path']) < 100: return
        an = PLRAnalyzer()
        if an.load_data(meta['csv_path']):
            an.preprocess()
            met = an.analyze(flash_timestamp=meta['flash_timestamp'])
            met['flash_timestamp'] = meta['flash_timestamp']
            met['flash_duration_s'] = meta['config']['flash_duration_ms'] / 1000.0
            col = '#b71c1c' if self.current_laterality == 'OD' else '#0d47a1'
            self.graph_widget.plot_data([{'label': f'Actuel ({self.current_laterality})', 'df': an.data, 'metrics': met, 'color': col}], clear=True)
            self.temp_result_meta = {'csv': meta['csv_path'], 'metrics': met}
            self._set_ui_state("NEW_RESULT")

    def load_patient_history(self):
        if not self.patient: return
        exams = self.db.get_patient_history(self.patient['id'])
        self.table_hist.setRowCount(0)
        for r, ex in enumerate(exams):
            self.table_hist.insertRow(r)
            self.table_hist.setItem(r, 0, QTableWidgetItem(ex['exam_date'].split(" ")[0]))
            lat = ex.get('laterality', '?')
            it = QTableWidgetItem(lat)
            it.setForeground(QColor('red' if lat=='OD' else 'blue'))
            self.table_hist.setItem(r, 1, it)
            self.table_hist.setItem(r, 2, QTableWidgetItem(ex.get('exam_type', 'PLR')))
            note_icon = "📝" if ex.get('comments') else ""
            self.table_hist.setItem(r, 3, QTableWidgetItem(note_icon))
            chk = QTableWidgetItem(); chk.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled); chk.setCheckState(Qt.Unchecked); chk.setData(Qt.UserRole, ex)
            self.table_hist.setItem(r, 4, chk)

    def on_history_clicked(self, item):
        if item.column() == 4:
            curves = []
            if self.temp_result_meta and not self.selected_historical_exam:
                an = PLRAnalyzer(); an.load_data(self.temp_result_meta['csv']); an.preprocess()
                col = '#b71c1c' if self.current_laterality == 'OD' else '#0d47a1'
                curves.append({'label': 'Actuel', 'df': an.data, 'metrics': self.temp_result_meta['metrics'], 'color': col})
            for r in range(self.table_hist.rowCount()):
                it = self.table_hist.item(r, 4)
                if it.checkState() == Qt.Checked:
                    ex = it.data(Qt.UserRole)
                    try:
                        an = PLRAnalyzer(); an.load_data(ex['csv_path']); an.preprocess()
                        lat = ex.get('laterality', '?')
                        col = '#ff8a80' if lat == 'OD' else '#82b1ff'
                        curves.append({'label': f"{ex['exam_date'].split(' ')[0]} ({lat})", 'df': an.data, 'metrics': ex.get('results_data',{}), 'color': col, 'style':'--'})
                    except: pass
            self.graph_widget.plot_data(curves, clear=True)
            return

        ex_data = self.table_hist.item(item.row(), 4).data(Qt.UserRole)
        self.selected_historical_exam = ex_data
        self.temp_result_meta = None
        self._set_ui_state("HISTORY_VIEW")
        self.txt_comments.setText(ex_data.get('comments', ''))
        try:
            an = PLRAnalyzer(); an.load_data(ex_data['csv_path']); an.preprocess()
            lat = ex_data.get('laterality', '?')
            col = '#b71c1c' if lat == 'OD' else '#0d47a1'
            metrics = ex_data.get('results_data', {})
            self.graph_widget.plot_data([{'label': f"{ex_data['exam_date']} ({lat})", 'df': an.data, 'metrics': metrics, 'color': col}], clear=True)
        except Exception as e: print(f"Erreur chargement: {e}")

    def save_new_exam(self):
        if self.temp_result_meta:
            self.db.save_exam(
                self.patient['id'], self.current_laterality, 
                self.temp_result_meta['csv'], results=self.temp_result_meta['metrics'],
                comments=self.txt_comments.toPlainText()
            )
            self._set_ui_state("IDLE"); self.load_patient_history(); self.status.showMessage("Sauvegardé.")

    def update_historical_comment(self):
        if self.selected_historical_exam:
            new_com = self.txt_comments.toPlainText()
            eid = self.selected_historical_exam['id']
            if self.db.update_exam_comment(eid, new_com):
                self.load_patient_history(); self.status.showMessage("Commentaire mis à jour.")
                self.selected_historical_exam['comments'] = new_com

    def discard_exam(self):
        if self.temp_result_meta:
            try: os.remove(self.temp_result_meta['csv'])
            except: pass
        self._set_ui_state("IDLE")

    def export_pdf(self):
        target_exam, target_metrics, date_str, lat = None, {}, "", ""
        if self.selected_historical_exam:
            target_exam = self.selected_historical_exam; target_metrics = target_exam.get('results_data', {})
            lat = target_exam.get('laterality', '?'); date_str = target_exam.get('exam_date')
        elif self.temp_result_meta:
            target_metrics = self.temp_result_meta['metrics']; lat = self.current_laterality
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else: return

        safe_date = date_str.split(" ")[0] if date_str else "date"
        safe_name = self.patient['name'].replace(" ", "_")
        default_filename = f"Rapport_{safe_name}_{safe_date}.pdf"
        
        path, _ = QFileDialog.getSaveFileName(self, "Exporter PDF", default_filename, "PDF (*.pdf)")
        if path:
            clinic = self.db.get_clinic_info()
            pat_info = {"name": self.patient['name'], "species": self.patient['species'], "breed": self.patient.get('breed',''), "id": self.patient['tattoo_id'], "owner": self.patient.get('owner_name', '')}
            exam_info = {"date": date_str, "laterality": lat}
            gen = PDFGenerator(path)
            gen.generate(clinic, pat_info, exam_info, target_metrics, self.txt_comments.toPlainText(), self.graph_widget.fig)
            QMessageBox.information(self, "Succès", "PDF généré.")

    def _load_macros(self):
        self.combo_macros.blockSignals(True); self.combo_macros.clear(); self.combo_macros.addItem("--- Insérer phrase type ---")
        for m in self.db.get_macros(): self.combo_macros.addItem(m['title'], m['content'])
        self.combo_macros.blockSignals(False)

    def _insert_macro(self, idx):
        if idx > 0:
            txt = self.combo_macros.itemData(idx)
            cur = self.txt_comments.toPlainText()
            self.txt_comments.setText((cur + "\n" + txt).strip())
            self.combo_macros.setCurrentIndex(0)

    def _settings(self): d = SettingsDialog(self, self.conf); d.settings_changed.connect(self._apply_set); d.exec(); self._load_macros()
    def _apply_set(self, s):
        new_idx = int(s.get("camera", {}).get("index", 0))
        if self.camera_thread and self.camera_thread.camera_index != new_idx: self.reset_camera(); return
        if self.camera_thread:
            d = s.get('detection', {})
            self.camera_thread.camera.roi_w = int(d.get('roi_width', 400)); self.camera_thread.camera.roi_h = int(d.get('roi_height', 400))
            self.camera_thread.camera.roi_off_x = int(d.get('roi_offset_x', 0)); self.camera_thread.camera.roi_off_y = int(d.get('roi_offset_y', 0))
            self.camera_thread.set_threshold(int(d.get('canny_threshold1', 50)))

    def _calib(self): (CalibrationDialog(self.camera_thread.camera, self).exec() if self.camera_thread else None)
    def return_to_home(self): self.stop_camera(); self.w=WelcomeScreen(); self.w.patient_selected.connect(lambda p:[self.w.close(), MainWindow(p).show()]); self.w.show(); self.close()
    def _show_about(self): QMessageBox.about(self, "Infos", "PLR V3.13")
    def stop_camera(self): (self.camera_thread.stop() if self.camera_thread else None)
    def closeEvent(self, e): self.stop_camera(); e.accept()

def main():
    os.makedirs("data/plr_results", exist_ok=True)
    app = QApplication(sys.argv); app.setStyle("Fusion")
    w = WelcomeScreen(); global win; 
    def launch(p): global win; win=MainWindow(p); win.show()
    w.patient_selected.connect(launch); w.show(); sys.exit(app.exec())

if __name__ == "__main__": main()