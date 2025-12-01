"""
main_application.py
===================
Interface principale de l'application PLR (Pupillary Light Reflex).
Version: 2.0.0 (Version Vétérinaire Complète)

Fonctionnalités:
- Point d'entrée : Écran d'accueil (Gestion Patients/Animaux)
- Interface Examen : Vidéo temps réel, Contrôles, Calibration
- Moteur de Test : Protocole multi-flash configurable
- Analyse & Résultats : Traitement immédiat et sauvegarde DB
"""

import sys
import cv2
import numpy as np
import os
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QComboBox,
    QGroupBox, QMessageBox, QStatusBar, QInputDialog, QSizePolicy
)
from PySide6.QtCore import (
    Qt, Signal, Slot, QThread, QTimer, QSize
)
from PySide6.QtGui import (
    QImage, QPixmap, QColor
)

# --- IMPORTS DES MODULES PROJET ---
from camera_engine import CameraEngine
from settings_dialog import SettingsDialog, ConfigManager
from plr_test_engine import PLRTestEngine, TestPhase
from plr_analyzer import PLRAnalyzer
from plr_results_viewer import PLRResultsViewer
from db_manager import DatabaseManager
from welcome_screen import WelcomeScreen
from calibration_dialog import CalibrationDialog

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Alias pour compatibilité
pyqtSignal = Signal
pyqtSlot = Slot


# ===========================
# WIDGET FLASH (STIMULUS)
# ===========================
class FlashOverlay(QWidget):
    """
    Fenêtre plein écran blanche pour simuler le flash lumineux.
    Elle se superpose à l'interface pendant la phase 'Stimulation'.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #FFFFFF;")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setCursor(Qt.BlankCursor)
        self.setWindowOpacity(1.0)
        
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)


# ===========================
# THREAD CAMÉRA
# ===========================
class CameraThread(QThread):
    """Thread dédié pour la capture/détection caméra."""
    
    frame_ready = pyqtSignal(np.ndarray)
    pupil_detected = pyqtSignal(dict)
    fps_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    camera_started = pyqtSignal()
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera = None
        self.camera_index = camera_index
        self.running = False
        self.config_manager = ConfigManager()
    
    def run(self):
        try:
            self.camera = CameraEngine(self.camera_index)
            self.running = True
            
            # Signaler que la caméra est prête
            self.camera_started.emit()
            
            while self.running:
                frame, pupil_data = self.camera.grab_and_detect()
                self.frame_ready.emit(frame)
                
                if pupil_data:
                    self.pupil_detected.emit(pupil_data)
                
                self.fps_updated.emit(self.camera.fps)
                self.msleep(1)
        
        except Exception as e:
            self.error_occurred.emit(f"Erreur caméra: {str(e)}")
        
        finally:
            if self.camera:
                self.camera.release()
    
    def stop(self):
        self.running = False
        self.wait(2000)

    # Proxy methods
    def set_threshold(self, value):
        if self.camera: self.camera.set_threshold(value)
    
    def set_blur(self, value):
        if self.camera: self.camera.set_blur_kernel(value)
    
    def set_display_mode(self, mode):
        if self.camera: self.camera.set_display_mode(mode)


# ===========================
# WIDGET VIDÉO
# ===========================
class VideoWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #000000; border: 2px solid #666;")
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    @pyqtSlot(np.ndarray)
    def update_frame(self, frame):
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            qt_image = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            self.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass


# ===========================
# PANNEAU DE CONTRÔLE
# ===========================
class ControlPanel(QWidget):
    threshold_changed = pyqtSignal(int)
    blur_changed = pyqtSignal(int)
    display_mode_changed = pyqtSignal(str)
    test_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Affichage
        display_group = QGroupBox("👁️ Affichage")
        display_layout = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Normal", "ROI", "Binaire", "Mosaïque"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        display_layout.addWidget(QLabel("Mode:"))
        display_layout.addWidget(self.mode_combo)
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # Détection
        detection_group = QGroupBox("🔍 Détection")
        detection_layout = QVBoxLayout()
        self.threshold_label = QLabel("Seuil: 50")
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 255)
        self.threshold_slider.setValue(50)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        self.blur_label = QLabel("Flou: 5")
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(1, 21)
        self.blur_slider.setValue(5)
        self.blur_slider.setSingleStep(2)
        self.blur_slider.valueChanged.connect(self._on_blur_changed)
        detection_layout.addWidget(self.threshold_label)
        detection_layout.addWidget(self.threshold_slider)
        detection_layout.addWidget(self.blur_label)
        detection_layout.addWidget(self.blur_slider)
        detection_group.setLayout(detection_layout)
        layout.addWidget(detection_group)
        
        # Actions
        actions_group = QGroupBox("⚡ Actions")
        actions_layout = QVBoxLayout()
        self.test_btn = QPushButton("▶ LANCER TEST PLR")
        self.test_btn.setStyleSheet("""
            QPushButton { background-color: #28a745; color: white; font-weight: bold; font-size: 14px; padding: 12px; border-radius: 5px; }
            QPushButton:hover { background-color: #218838; }
        """)
        self.test_btn.clicked.connect(self.test_requested.emit)
        self.settings_btn = QPushButton("⚙ Options")
        self.settings_btn.setStyleSheet("""
            QPushButton { background-color: #007bff; color: white; font-weight: bold; padding: 10px; border-radius: 5px; }
            QPushButton:hover { background-color: #0056b3; }
        """)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        actions_layout.addWidget(self.test_btn)
        actions_layout.addWidget(self.settings_btn)
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # Infos
        info_group = QGroupBox("📊 Informations")
        info_layout = QVBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.diameter_label = QLabel("Diamètre: --")
        self.quality_label = QLabel("Qualité: --")
        info_layout.addWidget(self.fps_label)
        info_layout.addWidget(self.diameter_label)
        info_layout.addWidget(self.quality_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        layout.addStretch()
        self.setLayout(layout)
        self.setFixedWidth(280)

    def _on_threshold_changed(self, value):
        self.threshold_label.setText(f"Seuil: {value}")
        self.threshold_changed.emit(value)
    
    def _on_blur_changed(self, value):
        if value % 2 == 0: value += 1
        self.blur_slider.setValue(value)
        self.blur_label.setText(f"Flou: {value}")
        self.blur_changed.emit(value)
    
    def _on_mode_changed(self, text):
        mode_map = {"Normal": "normal", "ROI": "roi", "Binaire": "binary", "Mosaïque": "mosaic"}
        self.display_mode_changed.emit(mode_map[text])
    
    def update_info(self, fps=None, diameter=None, quality=None):
        if fps is not None: self.fps_label.setText(f"FPS: {fps:.1f}")
        if diameter is not None: self.diameter_label.setText(f"Diamètre: {diameter:.2f} mm")
        if quality is not None:
            color = "#008000" if quality > 80 else "#d35400"
            self.quality_label.setText(f"<span style='color:{color}; font-weight:bold'>Qualité: {quality:.0f}%</span>")


# ===========================
# FENÊTRE PRINCIPALE
# ===========================
class MainWindow(QMainWindow):
    """Fenêtre principale orchestrant le tout."""
    
    def __init__(self, patient_data=None):
        super().__init__()
        self.patient_data = patient_data
        self.config_manager = ConfigManager()
        self.db = DatabaseManager()
        self.camera_thread = None
        self.test_engine = None
        self.flash_overlay = None
        
        self.setup_ui()
        self.start_camera()
        
        # Titre personnalisé
        if self.patient_data:
            self.setWindowTitle(f"PLR Analyzer - Examen de {self.patient_data['name']} ({self.patient_data['species']})")
    
    def setup_ui(self):
        self.setWindowTitle("PLR Analyzer - Pupillary Light Reflex")
        self.setGeometry(100, 100, 1200, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        self.video_widget = VideoWidget()
        main_layout.addWidget(self.video_widget, stretch=3)
        self.control_panel = ControlPanel()
        main_layout.addWidget(self.control_panel)
        central_widget.setLayout(main_layout)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🟢 Prêt")
        
        self._create_menu_bar()
        self._apply_light_theme()
        
        # Connexions
        self.control_panel.threshold_changed.connect(self._on_threshold_changed)
        self.control_panel.blur_changed.connect(self._on_blur_changed)
        self.control_panel.display_mode_changed.connect(self._on_display_mode_changed)
        self.control_panel.test_requested.connect(self._on_test_requested)
        self.control_panel.settings_requested.connect(self._on_settings_requested)

    def _apply_light_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #f0f2f5; color: #000000; font-family: 'Segoe UI', Arial; }
            QGroupBox { font-weight: bold; border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; padding-top: 15px; background-color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #333; }
            QLabel { color: #000; }
            QStatusBar { background-color: #e9ecef; }
        """)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Fichier")
        file_menu.addAction("Quitter", self.close, "Ctrl+Q")
        
        opts_menu = menu_bar.addMenu("Options")
        opts_menu.addAction("⚙ Réglages...", self._on_settings_requested)
        opts_menu.addAction("📏 Calibration...", self._on_calibration_requested)
        
        help_menu = menu_bar.addMenu("Aide")
        help_menu.addAction("À propos", self._show_about)

    # --- CAMÉRA ---
    def start_camera(self):
        self.camera_thread = CameraThread(0)
        self.camera_thread.frame_ready.connect(self.video_widget.update_frame)
        self.camera_thread.pupil_detected.connect(self._on_pupil_detected)
        self.camera_thread.fps_updated.connect(lambda fps: self.control_panel.update_info(fps=fps))
        self.camera_thread.error_occurred.connect(lambda e: self.status_bar.showMessage(f"🔴 {e}"))
        
        self.camera_thread.camera_started.connect(self._init_test_engine)
        self.camera_thread.start()

    def _init_test_engine(self):
        if self.camera_thread and self.camera_thread.camera:
            # Charger et appliquer la calibration
            camera_config = self.config_manager.config.get("camera", {})
            saved_ratio = camera_config.get("mm_per_pixel", 0.05)
            self.camera_thread.camera.mm_per_pixel = float(saved_ratio)
            
            # Initialiser moteur de test
            self.test_engine = PLRTestEngine(self.camera_thread.camera)
            
            # Connexions
            self.test_engine.phase_changed.connect(self._on_test_phase_changed)
            self.test_engine.flash_triggered.connect(self._on_flash_triggered)
            self.test_engine.test_finished.connect(self._on_test_finished)
            self.test_engine.progress_updated.connect(self._on_test_progress)
            self.test_engine.error_occurred.connect(lambda e: QMessageBox.warning(self, "Erreur Test", e))
            
            print("✅ Moteur PLR initialisé")
            self.status_bar.showMessage(f"🟢 Prêt (Calibration: {saved_ratio} mm/px)")

    def stop_camera(self):
        if self.camera_thread:
            self.camera_thread.stop()

    # --- SLOTS UI ---
    @pyqtSlot(dict)
    def _on_pupil_detected(self, data):
        self.control_panel.update_info(diameter=data['diameter_mm'], quality=data['quality_score'])

    def _on_threshold_changed(self, v): 
        if self.camera_thread: self.camera_thread.set_threshold(v)
    def _on_blur_changed(self, v): 
        if self.camera_thread: self.camera_thread.set_blur(v)
    def _on_display_mode_changed(self, m): 
        if self.camera_thread: self.camera_thread.set_display_mode(m)

    def _on_settings_requested(self):
        dialog = SettingsDialog(self, self.config_manager)
        dialog.settings_changed.connect(self._on_settings_applied)
        dialog.exec()

    def _on_settings_applied(self, settings):
        if self.camera_thread:
            det = settings.get('detection', {})
            if 'canny_threshold1' in det: self.camera_thread.set_threshold(det['canny_threshold1'])
            if 'gaussian_blur' in det: self.camera_thread.set_blur(det['gaussian_blur'])
        self.status_bar.showMessage("✅ Paramètres sauvegardés", 3000)

    def _on_calibration_requested(self):
        if not self.camera_thread or not self.camera_thread.camera:
            QMessageBox.critical(self, "Erreur", "La caméra doit être active.")
            return
        
        dialog = CalibrationDialog(self.camera_thread.camera, self)
        
        def on_calib_saved(new_ratio):
            print(f"📏 Nouvelle calibration : {new_ratio:.6f}")
            self.status_bar.showMessage(f"Calibration mise à jour : {new_ratio:.5f} mm/px", 5000)
            
        dialog.calibration_saved.connect(on_calib_saved)
        dialog.exec()

    # --- LOGIQUE TEST ---
    def _on_test_requested(self):
        if not self.test_engine:
            if self.camera_thread and self.camera_thread.camera: self._init_test_engine()
            if not self.test_engine:
                QMessageBox.critical(self, "Erreur", "Moteur de test non initialisé.")
                return
        
        # ID Patient
        if self.patient_data:
            patient_ref = f"{self.patient_data['name']}_{self.patient_data['tattoo_id']}"
        else:
            patient_ref, ok = QInputDialog.getText(self, "Nouveau Test", "ID Patient :")
            if not ok: return

        # Configuration Protocole
        protocol_config = self.config_manager.config.get("protocol", {})
        self.test_engine.configure(
            baseline_duration=protocol_config.get("baseline_duration", 2.0),
            flash_count=protocol_config.get("flash_count", 1),
            flash_duration_ms=protocol_config.get("flash_duration_ms", 200),
            response_duration=protocol_config.get("response_duration", 5.0)
        )
        
        self.control_panel.setEnabled(False)
        self.test_engine.start_test(patient_ref)

    def _on_test_phase_changed(self, phase_name):
        self.status_bar.showMessage(f"🔬 TEST EN COURS : Phase {phase_name}")

    def _on_flash_triggered(self, active):
        if active:
            if not self.flash_overlay: self.flash_overlay = FlashOverlay()
            self.flash_overlay.showFullScreen()
            QApplication.processEvents()
        else:
            if self.flash_overlay:
                self.flash_overlay.close()
                self.flash_overlay = None

    def _on_test_progress(self, elapsed, phase):
        pass

    def _on_test_finished(self, results_meta):
        self.control_panel.setEnabled(True)
        self.status_bar.showMessage("✅ Analyse en cours...")
        
        # 1. Analyse
        analyzer = PLRAnalyzer()
        if analyzer.load_data(results_meta['csv_path']):
            analyzer.preprocess()
            
            # Paramètres flash pour l'analyse
            flash_ts = results_meta['flash_timestamp']
            metrics = analyzer.analyze(flash_timestamp=flash_ts)
            
            # Injection infos flash pour visu
            flash_dur_ms = results_meta['config'].get('flash_duration_ms', 200)
            metrics['flash_timestamp'] = flash_ts
            metrics['flash_duration_s'] = flash_dur_ms / 1000.0
            
            # 2. Sauvegarde DB
            if self.patient_data:
                exam_id = self.db.save_exam(
                    patient_id=self.patient_data['id'],
                    csv_path=results_meta['csv_path'],
                    results=metrics
                )
                print(f"💾 Examen sauvegardé ID {exam_id}")
            
            # 3. Visu
            viewer = PLRResultsViewer(self, data=analyzer.data, results=metrics)
            viewer.exec()
            self.status_bar.showMessage("Prêt")
        else:
            QMessageBox.warning(self, "Erreur", "Analyse impossible (fichier vide ?)")

    def _show_about(self):
        QMessageBox.about(self, "À propos", "<h3>PLR Vet Analyzer</h3><p>Version 2.0</p>")

    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Quitter", "Voulez-vous quitter ?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.stop_camera()
            event.accept()
        else:
            event.ignore()

# ===========================
# POINT D'ENTRÉE
# ===========================
def main():
    os.makedirs("data/plr_results", exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    welcome = WelcomeScreen()
    
    def start_app(patient_data):
        global window 
        window = MainWindow(patient_data)
        window.show()
        # Note: WelcomeScreen se ferme de lui-même
        
    welcome.patient_selected.connect(start_app)
    welcome.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()