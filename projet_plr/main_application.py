"""
main_application.py
===================
Interface Examen Vétérinaire Intégrée.
Version: 3.4.0 (Latéralité dans la Main Window)
"""

import sys
import cv2
import numpy as np
import os
import logging
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QComboBox, QGroupBox, QMessageBox, 
    QStatusBar, QInputDialog, QSplitter, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer
from PySide6.QtGui import QImage, QPixmap, QAction, QColor

from camera_engine import CameraEngine
from settings_dialog import SettingsDialog, ConfigManager
from plr_test_engine import PLRTestEngine
from plr_analyzer import PLRAnalyzer
from plr_results_viewer import PLRGraphWidget
from db_manager import DatabaseManager
from welcome_screen import WelcomeScreen
from calibration_dialog import CalibrationDialog

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
    frame_ready = Signal(np.ndarray)
    pupil_detected = Signal(dict)
    fps_updated = Signal(float)
    error_occurred = Signal(str)
    camera_started = Signal()
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera = None
        self.camera_index = camera_index
        self.running = False
    def run(self):
        try:
            self.camera = CameraEngine(self.camera_index)
            self.running = True
            self.camera_started.emit()
            while self.running:
                frame, pupil_data = self.camera.grab_and_detect()
                self.frame_ready.emit(frame)
                if pupil_data: self.pupil_detected.emit(pupil_data)
                self.fps_updated.emit(self.camera.fps)
                self.msleep(1)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.camera: self.camera.release()
    def stop(self):
        self.running = False
        self.wait(2000)
    def set_threshold(self, v): 
        if self.camera: self.camera.set_threshold(v)
    def set_blur(self, v): 
        if self.camera: self.camera.set_blur_kernel(v)
    def set_display_mode(self, m): 
        if self.camera: self.camera.set_display_mode(m)
    def start_recording(self, f): 
        if self.camera: self.camera.start_csv_recording(f)
    def stop_recording(self): 
        if self.camera: self.camera.stop_csv_recording()

class VideoWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: black;")
        self.setMinimumSize(400, 300)
    @Slot(np.ndarray)
    def update_frame(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch*w, QImage.Format.Format_RGB888)
            self.setPixmap(QPixmap.fromImage(img).scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except: pass

# --- CONTROL PANEL MODIFIÉ (Avec Latéralité) ---
class ControlPanel(QWidget):
    threshold_changed = Signal(int)
    blur_changed = Signal(int)
    display_mode_changed = Signal(str)
    test_requested = Signal()
    settings_requested = Signal()
    reset_camera_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        lay = QVBoxLayout(self)
        
        # 1. LATÉRALITÉ (Nouveau)
        grp_eye = QGroupBox("Choix de l'Œil")
        grp_eye.setStyleSheet("QGroupBox { border: 1px solid #999; font-weight: bold; }")
        h_eye = QHBoxLayout()
        self.eye_group = QButtonGroup(self)
        
        self.rad_od = QRadioButton("OD (Droit)")
        self.rad_od.setStyleSheet("color: #d32f2f; font-weight: bold;")
        self.rad_od.setChecked(True)
        
        self.rad_og = QRadioButton("OG (Gauche)")
        self.rad_og.setStyleSheet("color: #1976d2; font-weight: bold;")
        
        self.eye_group.addButton(self.rad_od)
        self.eye_group.addButton(self.rad_og)
        h_eye.addWidget(self.rad_od)
        h_eye.addWidget(self.rad_og)
        grp_eye.setLayout(h_eye)
        lay.addWidget(grp_eye)

        # 2. Réglages
        grp_set = QGroupBox("Réglages Caméra")
        flay = QVBoxLayout()
        
        self.sl_thresh = QSlider(Qt.Horizontal)
        self.sl_thresh.setRange(0, 255)
        self.sl_thresh.setValue(50)
        self.sl_thresh.valueChanged.connect(self.threshold_changed.emit)
        flay.addWidget(QLabel("Seuil"))
        flay.addWidget(self.sl_thresh)
        
        self.sl_blur = QSlider(Qt.Horizontal)
        self.sl_blur.setRange(1, 21)
        self.sl_blur.setValue(5)
        self.sl_blur.setSingleStep(2)
        self.sl_blur.valueChanged.connect(self.blur_changed.emit)
        flay.addWidget(QLabel("Flou"))
        flay.addWidget(self.sl_blur)

        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["Normal", "ROI", "Binaire", "Mosaïque"])
        self.cb_mode.currentTextChanged.connect(self._on_mode)
        flay.addWidget(QLabel("Vue"))
        flay.addWidget(self.cb_mode)
        grp_set.setLayout(flay)
        lay.addWidget(grp_set)
        
        # 3. Actions
        self.btn_test = QPushButton("▶ LANCER EXAMEN")
        self.btn_test.setFixedHeight(50)
        self.btn_test.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; font-size: 14px; border-radius: 5px;")
        self.btn_test.clicked.connect(self.test_requested.emit)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid grey; border-radius: 5px; text-align: center; background: #eee; } QProgressBar::chunk { background-color: #28a745; }")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Prêt")
        
        self.btn_reset = QPushButton("🔄 Réinit. Caméra")
        self.btn_reset.setStyleSheet("background-color: #e67e22; color: white; padding: 5px; border-radius: 4px;")
        self.btn_reset.clicked.connect(self.reset_camera_requested.emit)

        lay.addWidget(self.btn_test)
        lay.addWidget(self.progress_bar)
        lay.addSpacing(10)
        lay.addWidget(self.btn_reset)
        lay.addStretch()
        
        self.lbl_info = QLabel("--")
        self.lbl_info.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_info)

    def _on_mode(self, t): self.display_mode_changed.emit({"Normal":"normal","ROI":"roi","Binaire":"binary","Mosaïque":"mosaic"}[t])
    def update_info(self, d=None, q=None):
        if d: self.lbl_info.setText(f"Ø: {d:.2f}mm | Q: {q:.0f}%")
        
    def get_selected_eye(self):
        return "OD" if self.rad_od.isChecked() else "OG"

# ===========================
# MAIN WINDOW VÉTÉRINAIRE
# ===========================
class MainWindow(QMainWindow):
    def __init__(self, patient_data):
        super().__init__()
        self.patient = patient_data
        self.db = DatabaseManager()
        self.conf = ConfigManager()
        self.temp_result_meta = None 
        self.camera_thread = None
        self.engine = None
        self.total_test_duration = 0.0
        
        self.setup_ui()
        self.start_camera()
        
        if self.patient:
            self.setWindowTitle(f"Dossier Patient : {self.patient['name']} ({self.patient['species']})")
            self.load_patient_history()

    def setup_ui(self):
        self.resize(1300, 800)
        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QHBoxLayout(central)
        
        # --- GAUCHE ---
        left_panel = QWidget()
        left_lay = QVBoxLayout(left_panel)
        self.video = VideoWidget()
        self.controls = ControlPanel()
        
        self.controls.threshold_changed.connect(lambda v: self.camera_thread.set_threshold(v) if self.camera_thread else None)
        self.controls.blur_changed.connect(lambda v: self.camera_thread.set_blur(v) if self.camera_thread else None)
        self.controls.display_mode_changed.connect(lambda m: self.camera_thread.set_display_mode(m) if self.camera_thread else None)
        self.controls.test_requested.connect(self.start_test)
        self.controls.reset_camera_requested.connect(self.reset_camera)
        
        left_lay.addWidget(self.video, stretch=3)
        left_lay.addWidget(self.controls, stretch=1)
        
        # --- DROITE ---
        right_panel = QWidget()
        right_lay = QVBoxLayout(right_panel)
        
        self.graph_widget = PLRGraphWidget()
        
        self.valid_group = QGroupBox("Validation Résultat")
        self.valid_group.setStyleSheet("QGroupBox { background-color: #f9fbe7; border: 1px solid #c0ca33; }")
        valid_lay = QHBoxLayout()
        self.btn_save = QPushButton("💾 SAUVEGARDER L'EXAMEN")
        self.btn_save.setStyleSheet("background-color: #007bff; color: white; padding: 10px; font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self.save_exam)
        self.btn_discard = QPushButton("🗑️ Jeter")
        self.btn_discard.setStyleSheet("background-color: #dc3545; color: white; padding: 10px; border-radius: 4px;")
        self.btn_discard.clicked.connect(self.discard_exam)
        valid_lay.addWidget(self.btn_save)
        valid_lay.addWidget(self.btn_discard)
        self.valid_group.setLayout(valid_lay)
        self.valid_group.setVisible(False) 
        
        self.grp_history = QGroupBox(f"Historique")
        hist_lay = QVBoxLayout()
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(4)
        self.table_history.setHorizontalHeaderLabels(["Date", "Oeil", "Type", "Comparer"])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_history.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_history.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_history.itemClicked.connect(self.on_history_clicked)
        hist_lay.addWidget(self.table_history)
        self.grp_history.setLayout(hist_lay)
        
        right_lay.addWidget(QLabel("<h3>Analyse Temps Réel</h3>"))
        right_lay.addWidget(self.graph_widget, stretch=4)
        right_lay.addWidget(self.valid_group)
        right_lay.addWidget(self.grp_history, stretch=2)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 800])
        main_lay.addWidget(splitter)
        
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._create_menu_bar()
        self._apply_light_theme()

    def _apply_light_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #f0f2f5; color: #000000; font-family: 'Segoe UI', Arial; }
            QGroupBox { font-weight: bold; border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; padding-top: 15px; background-color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #333; }
            QLabel { color: #000; }
            QStatusBar { background-color: #e9ecef; }
            QTableWidget { background-color: white; border: 1px solid #ccc; }
        """)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        f_menu = menu_bar.addMenu("Fichier")
        act_home = QAction("🏠 Retour à l'accueil", self)
        act_home.triggered.connect(self.return_to_home)
        f_menu.addAction(act_home)
        f_menu.addSeparator()
        act_quit = QAction("Quitter", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        f_menu.addAction(act_quit)
        
        o_menu = menu_bar.addMenu("Options")
        act_settings = QAction("⚙ Réglages...", self)
        act_settings.triggered.connect(self._on_settings_requested)
        o_menu.addAction(act_settings)
        act_calib = QAction("📏 Calibration...", self)
        act_calib.triggered.connect(self._on_calibration_requested)
        o_menu.addAction(act_calib)
        
        h_menu = menu_bar.addMenu("Aide")
        h_menu.addAction("À propos", self._show_about)

    def start_camera(self):
        self.camera_thread = CameraThread(0)
        self.camera_thread.frame_ready.connect(self.video.update_frame)
        self.camera_thread.pupil_detected.connect(lambda d: self.controls.update_info(d=d['diameter_mm'], q=d['quality_score']))
        self.camera_thread.camera_started.connect(self.init_engine)
        self.camera_thread.start()

    def init_engine(self):
        cam_conf = self.conf.config.get("camera", {})
        det_conf = self.conf.config.get("detection", {})
        ratio = float(cam_conf.get("mm_per_pixel", 0.05))
        self.camera_thread.camera.mm_per_pixel = ratio
        thresh = int(det_conf.get("canny_threshold1", 50))
        blur = int(det_conf.get("gaussian_blur", 5))
        self.camera_thread.set_threshold(thresh)
        self.camera_thread.set_blur(blur)
        self.controls.sl_thresh.blockSignals(True)
        self.controls.sl_thresh.setValue(thresh)
        self.controls.sl_thresh.blockSignals(False)
        self.controls.sl_blur.blockSignals(True)
        self.controls.sl_blur.setValue(blur)
        self.controls.sl_blur.blockSignals(False)
        self.engine = PLRTestEngine(self.camera_thread.camera)
        self.engine.flash_triggered.connect(self.trigger_flash)
        self.engine.test_finished.connect(self.on_test_finished)
        self.engine.progress_updated.connect(self.on_test_progress)
        self.status.showMessage(f"Prêt (Calibration: {ratio:.4f} mm/px)")

    def reset_camera(self):
        self.status.showMessage("⏳ Réinitialisation caméra...")
        self.stop_camera()
        QTimer.singleShot(500, self.start_camera)

    def trigger_flash(self, on):
        if on:
            self.flash = FlashOverlay()
            self.flash.showFullScreen()
            QApplication.processEvents()
        else:
            if hasattr(self, 'flash'): self.flash.close()

    def start_test(self):
        if not self.engine: 
            QMessageBox.warning(self, "Erreur", "Caméra non prête")
            return
        self.valid_group.setVisible(False) 
        self.graph_widget.axes.clear()     
        self.graph_widget.canvas.draw()
        
        pc = self.conf.config.get("protocol", {})
        base = pc.get("baseline_duration", 2.0)
        count = pc.get("flash_count", 1)
        flash = pc.get("flash_duration_ms", 200)
        resp = pc.get("response_duration", 5.0)
        
        self.total_test_duration = base + count * ((flash/1000.0) + resp)
        self.controls.progress_bar.setRange(0, int(self.total_test_duration * 10))
        self.controls.progress_bar.setValue(0)
        self.engine.configure(baseline_duration=base, flash_count=count, flash_duration_ms=flash, response_duration=resp)
        
        # RÉCUPÉRATION DE L'ŒIL SÉLECTIONNÉ
        current_eye = self.controls.get_selected_eye()
        ref = f"{self.patient['name']}_{self.patient['tattoo_id']}_{current_eye}"
        
        # On stocke l'info pour l'analyse
        self.current_laterality = current_eye
        
        self.engine.start_test(ref)
        self.controls.setEnabled(False)

    def on_test_progress(self, elapsed, phase_name):
        val = int(elapsed * 10)
        self.controls.progress_bar.setValue(val)
        self.controls.progress_bar.setFormat(f"{phase_name} : {elapsed:.1f}s / {self.total_test_duration:.1f}s")

    def on_test_finished(self, meta):
        self.controls.setEnabled(True)
        self.controls.progress_bar.setValue(self.controls.progress_bar.maximum())
        self.controls.progress_bar.setFormat("Terminé")
        self.status.showMessage("Analyse...")
        csv_path = meta['csv_path']
        try:
            if os.path.getsize(csv_path) < 100:
                QMessageBox.warning(self, "Erreur", "Examen vide.")
                try: os.remove(csv_path)
                except: pass
                return
        except: pass
        
        analyzer = PLRAnalyzer()
        if analyzer.load_data(csv_path):
            analyzer.preprocess()
            metrics = analyzer.analyze(flash_timestamp=meta['flash_timestamp'])
            metrics['flash_timestamp'] = meta['flash_timestamp']
            metrics['flash_duration_s'] = meta['config']['flash_duration_ms'] / 1000.0
            
            # Utilisation de la latéralité courante pour la couleur
            col = '#b71c1c' if self.current_laterality == 'OD' else '#0d47a1'
            curve_data = {
                'label': f'Actuel ({self.current_laterality})',
                'df': analyzer.data,
                'metrics': metrics,
                'color': col
            }
            self.graph_widget.plot_data([curve_data], clear=True)
            self.temp_result_meta = {'csv': meta['csv_path'], 'metrics': metrics}
            self.valid_group.setVisible(True)
            self.status.showMessage("Examen terminé.")

    def load_patient_history(self):
        if not self.patient: return
        exams = self.db.get_patient_history(self.patient['id'])
        self.table_history.setRowCount(0)
        for row, ex in enumerate(exams):
            self.table_history.insertRow(row)
            date_str = ex['exam_date'].split(" ")[0]
            lat = ex.get('laterality', '??')
            
            self.table_history.setItem(row, 0, QTableWidgetItem(date_str))
            
            item_lat = QTableWidgetItem(lat)
            if lat == 'OD': item_lat.setForeground(QColor('#d32f2f'))
            elif lat == 'OG': item_lat.setForeground(QColor('#1976d2'))
            item_lat.setTextAlignment(Qt.AlignCenter)
            self.table_history.setItem(row, 1, item_lat)
            
            self.table_history.setItem(row, 2, QTableWidgetItem(ex.get('exam_type', 'PLR')))
            
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            chk.setData(Qt.UserRole, ex)
            self.table_history.setItem(row, 3, chk)

    def on_history_clicked(self, item):
        if item.column() != 3: return
        curves_to_plot = []
        if self.temp_result_meta:
            analyzer = PLRAnalyzer()
            analyzer.load_data(self.temp_result_meta['csv'])
            analyzer.preprocess()
            col = '#b71c1c' if self.current_laterality == 'OD' else '#0d47a1'
            curves_to_plot.append({
                'label': f'Actuel ({self.current_laterality})',
                'df': analyzer.data,
                'metrics': self.temp_result_meta['metrics'],
                'color': col,
                'style': '-'
            })
        for row in range(self.table_history.rowCount()):
            chk_item = self.table_history.item(row, 3)
            if chk_item.checkState() == Qt.Checked:
                ex_data = chk_item.data(Qt.UserRole)
                try:
                    an = PLRAnalyzer()
                    if an.load_data(ex_data['csv_path']):
                        an.preprocess()
                        d_str = ex_data['exam_date'].split(" ")[0]
                        lat = ex_data.get('laterality', '?')
                        col = '#ff8a80' if lat == 'OD' else '#82b1ff'
                        curves_to_plot.append({
                            'label': f"{d_str} ({lat})",
                            'df': an.data,
                            'metrics': ex_data.get('results_data', {}),
                            'color': col,
                            'style': '--'
                        })
                except: pass
        self.graph_widget.plot_data(curves_to_plot, clear=True)

    def save_exam(self):
        if self.temp_result_meta:
            self.db.save_exam(
                self.patient['id'],
                self.current_laterality,
                self.temp_result_meta['csv'],
                results=self.temp_result_meta['metrics']
            )
            QMessageBox.information(self, "OK", "Examen enregistré.")
            self.valid_group.setVisible(False)
            self.load_patient_history()
            self.status.showMessage("Sauvegardé.")

    def discard_exam(self):
        if self.temp_result_meta:
            try: os.remove(self.temp_result_meta['csv'])
            except: pass
        self.valid_group.setVisible(False)
        self.graph_widget.axes.clear()
        self.graph_widget.canvas.draw()
        self.status.showMessage("Examen annulé.")

    def _on_settings_requested(self):
        dialog = SettingsDialog(self, self.conf)
        dialog.settings_changed.connect(self._apply_settings_live)
        dialog.exec()

    def _apply_settings_live(self, settings):
        if self.camera_thread and self.camera_thread.camera:
            det = settings.get('detection', {})
            thresh = int(det.get('canny_threshold1', 50))
            blur = int(det.get('gaussian_blur', 5))
            self.camera_thread.set_threshold(thresh)
            self.camera_thread.set_blur(blur)
            self.controls.sl_thresh.setValue(thresh)
            self.controls.sl_blur.setValue(blur)
            self.status.showMessage("✅ Réglages appliqués")

    def _on_calibration_requested(self):
        if not self.camera_thread or not self.camera_thread.camera: return
        dialog = CalibrationDialog(self.camera_thread.camera, self)
        dialog.calibration_saved.connect(lambda r: self.status.showMessage(f"Calibration : {r:.5f}"))
        dialog.exec()

    def return_to_home(self):
        self.stop_camera()
        self.welcome = WelcomeScreen()
        def restart_exam(p_data):
            self.new_window = MainWindow(p_data)
            self.new_window.show()
            self.welcome.close()
        self.welcome.patient_selected.connect(restart_exam)
        self.welcome.show()
        self.close()

    def _show_about(self):
        QMessageBox.about(self, "À propos", "<h3>PLR Vet Analyzer v3.4</h3>")

    def stop_camera(self):
        if self.camera_thread:
            self.camera_thread.stop()

    def closeEvent(self, e):
        self.stop_camera()
        e.accept()

def main():
    os.makedirs("data/plr_results", exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    welcome = WelcomeScreen()
    global win 
    def launch(p_data):
        global win
        win = MainWindow(p_data)
        win.show()
    welcome.patient_selected.connect(launch)
    welcome.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()