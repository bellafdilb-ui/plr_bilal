"""
main_application.py
===================
Interface principale de l'application PLR (Pupillary Light Reflex).

Fonctionnalités:
- Affichage vidéo temps réel avec détection pupille
- Contrôles rapides (seuillage, flou, mode vue)
- Lancement des tests PLR
- Menu Options complet

Contrôles:
- Caméra toujours active (pas d'enregistrement par défaut)
- Sliders temps réel pour ajustements
- Bouton "Lancer Test" pour démarrer un protocole PLR
"""

import sys
import cv2
import numpy as np
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QSpinBox, QComboBox,
    QGroupBox, QMessageBox, QFileDialog, QStatusBar, QTextEdit,
    QSizePolicy, QFrame, QScrollArea, QLineEdit
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, Slot, QThread, QMutex, QWaitCondition,
    QSize, QRect, QPoint
)
from PySide6.QtGui import (
    QImage, QPixmap, QFont, QAction, QPainter, QPen, QColor,
    QKeySequence, QIcon
)

# Import du moteur caméra
from camera_engine import CameraEngine
from settings_dialog import SettingsDialog, ConfigManager

# Alias pour compatibilité
pyqtSignal = Signal
pyqtSlot = Slot

# ===========================
# THREAD CAMÉRA
# ===========================

class CameraThread(QThread):
    """Thread dédié pour la capture/détection caméra (évite freeze UI)"""
    
    # Signaux pour communication avec l'UI
    frame_ready = pyqtSignal(np.ndarray)  # Envoi frame OpenCV
    pupil_detected = pyqtSignal(dict)     # Envoi données pupille
    fps_updated = pyqtSignal(float)       # Envoi FPS
    error_occurred = pyqtSignal(str)      # Envoi erreur
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera = None
        self.camera_index = camera_index
        self.running = False
        self.config_manager = ConfigManager()
    
    def run(self):
        """Boucle principale du thread caméra"""
        try:
            # Initialisation caméra
            self.camera = CameraEngine(self.camera_index)
            self.running = True
            
            while self.running:
                # Capture + détection
                frame, pupil_data = self.camera.grab_and_detect()
                
                # Envoi frame pour affichage
                self.frame_ready.emit(frame)
                
                # Envoi données pupille (si détectée)
                if pupil_data:
                    self.pupil_detected.emit(pupil_data)
                
                # Envoi FPS
                self.fps_updated.emit(self.camera.fps)
                
                # Petite pause pour ne pas saturer le CPU
                self.msleep(1)
        
        except Exception as e:
            self.error_occurred.emit(f"Erreur caméra: {str(e)}")
        
        finally:
            if self.camera:
                self.camera.release()
    
    def stop(self):
        """Arrêt propre du thread"""
        self.running = False
        self.wait(2000)  # Attendre max 2 secondes
    
    # Méthodes pour contrôler la caméra depuis l'UI
    def set_threshold(self, value):
        if self.camera:
            self.camera.set_threshold(value)
    
    def set_blur(self, value):
        if self.camera:
            self.camera.set_blur_kernel(value)
    
    def set_display_mode(self, mode):
        if self.camera:
            self.camera.set_display_mode(mode)
    
    def set_roi(self, x, y, w, h):
        if self.camera:
            self.camera.set_roi(x, y, w, h)
    
    def start_recording(self, output_file):
        if self.camera:
            self.camera.start_recording(output_file)
    
    def stop_recording(self):
        if self.camera:
            self.camera.stop_recording()


# ===========================
# WIDGET VIDÉO
# ===========================

class VideoWidget(QLabel):
    """Widget pour affichage du flux vidéo"""
    
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #1e1e1e; border: 2px solid #444;")
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    @pyqtSlot(np.ndarray)
    def update_frame(self, frame):
        """Convertit frame OpenCV → QPixmap et affiche"""
        try:
            # Conversion BGR (OpenCV) → RGB (Qt)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # Création QImage
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Redimensionnement pour s'adapter au widget (garde ratio)
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.setPixmap(scaled_pixmap)
        
        except Exception as e:
            print(f"❌ Erreur affichage frame: {e}")


# ===========================
# PANNEAU DE CONTRÔLE
# ===========================

class ControlPanel(QWidget):
    """Panneau latéral avec contrôles rapides"""
    
    # Signaux
    threshold_changed = pyqtSignal(int)
    blur_changed = pyqtSignal(int)
    display_mode_changed = pyqtSignal(str)
    test_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        """Construction de l'interface"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # === GROUPE AFFICHAGE ===
        display_group = QGroupBox("👁️ Affichage")
        display_layout = QVBoxLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Normal", "ROI", "Binaire", "Mosaïque"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        display_layout.addWidget(QLabel("Mode:"))
        display_layout.addWidget(self.mode_combo)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # === GROUPE DÉTECTION ===
        detection_group = QGroupBox("🔍 Détection")
        detection_layout = QVBoxLayout()
        
        # Slider seuillage
        self.threshold_label = QLabel("Seuil: 50")
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 255)
        self.threshold_slider.setValue(50)
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(25)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        
        detection_layout.addWidget(self.threshold_label)
        detection_layout.addWidget(self.threshold_slider)
        
        # Slider flou
        self.blur_label = QLabel("Flou: 5")
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(1, 21)
        self.blur_slider.setValue(5)
        self.blur_slider.setSingleStep(2)  # Garder impair
        self.blur_slider.valueChanged.connect(self._on_blur_changed)
        
        detection_layout.addWidget(self.blur_label)
        detection_layout.addWidget(self.blur_slider)
        
        detection_group.setLayout(detection_layout)
        layout.addWidget(detection_group)
        
        # === GROUPE ACTIONS ===
        actions_group = QGroupBox("⚡ Actions")
        actions_layout = QVBoxLayout()
        
        # Bouton Lancer Test
        self.test_btn = QPushButton("▶ LANCER TEST PLR")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        self.test_btn.clicked.connect(self.test_requested.emit)
        
        # Bouton Options
        self.settings_btn = QPushButton("⚙ Options")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        
        actions_layout.addWidget(self.test_btn)
        actions_layout.addWidget(self.settings_btn)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # === INFOS TEMPS RÉEL ===
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
        
        # Spacer pour pousser en haut
        layout.addStretch()
        
        self.setLayout(layout)
        self.setFixedWidth(280)
    
    # Slots internes
    def _on_threshold_changed(self, value):
        self.threshold_label.setText(f"Seuil: {value}")
        self.threshold_changed.emit(value)
    
    def _on_blur_changed(self, value):
        # Forcer impair
        if value % 2 == 0:
            value += 1
            self.blur_slider.setValue(value)
        self.blur_label.setText(f"Flou: {value}")
        self.blur_changed.emit(value)
    
    def _on_mode_changed(self, text):
        mode_map = {
            "Normal": "normal",
            "ROI": "roi",
            "Binaire": "binary",
            "Mosaïque": "mosaic"
        }
        self.display_mode_changed.emit(mode_map[text])
    
    # Méthodes publiques pour mise à jour
    def update_info(self, fps=None, diameter=None, quality=None):
        if fps is not None:
            self.fps_label.setText(f"FPS: {fps:.1f}")
        if diameter is not None:
            self.diameter_label.setText(f"Diamètre: {diameter:.2f} mm")
        if quality is not None:
            color = "green" if quality > 80 else "orange"
            self.quality_label.setText(f"<span style='color:{color}'>Qualité: {quality:.0f}%</span>")


# ===========================
# FENÊTRE PRINCIPALE
# ===========================

class MainWindow(QMainWindow):
    """Fenêtre principale de l'application"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.camera_thread = None
        self.setup_ui()
        self.start_camera()
    
    def setup_ui(self):
        """Construction de l'interface"""
        self.setWindowTitle("PLR Analyzer - Pupillary Light Reflex")
        self.setGeometry(100, 100, 1200, 700)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QHBoxLayout()
        
        # Vidéo à gauche
        self.video_widget = VideoWidget()
        main_layout.addWidget(self.video_widget, stretch=3)
        
        # Panneau de contrôle à droite
        self.control_panel = ControlPanel()
        main_layout.addWidget(self.control_panel)
        
        # Connexions signaux panneau
        self.control_panel.threshold_changed.connect(self._on_threshold_changed)
        self.control_panel.blur_changed.connect(self._on_blur_changed)
        self.control_panel.display_mode_changed.connect(self._on_display_mode_changed)
        self.control_panel.test_requested.connect(self._on_test_requested)
        self.control_panel.settings_requested.connect(self._on_settings_requested)
        
        central_widget.setLayout(main_layout)
        
        # Barre de statut
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🟢 Caméra active - Mode Navigation")
        
        # Menu bar
        self._create_menu_bar()
        
        # Style global
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: white;
            }
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 3px;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #3a3a3a;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #007bff;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)
    
    def _create_menu_bar(self):
        """Création du menu"""
        menu_bar = self.menuBar()
        
        # Menu Fichier
        file_menu = menu_bar.addMenu("Fichier")
        
        quit_action = file_menu.addAction("Quitter")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        
        # Menu Options
        options_menu = menu_bar.addMenu("Options")
        
        settings_action = options_menu.addAction("⚙ Réglages...")
        settings_action.triggered.connect(self._on_settings_requested)
        
        # Menu Aide
        help_menu = menu_bar.addMenu("Aide")
        
        about_action = help_menu.addAction("À propos")
        about_action.triggered.connect(self._show_about)




    # ===========================
    # GESTION CAMÉRA
    # ===========================
    
    def start_camera(self):
        """Démarre le thread caméra"""
        try:
            self.camera_thread = CameraThread(camera_index=0)
            
            # Connexion signaux
            self.camera_thread.frame_ready.connect(self.video_widget.update_frame)
            self.camera_thread.pupil_detected.connect(self._on_pupil_detected)
            self.camera_thread.fps_updated.connect(self._on_fps_updated)
            self.camera_thread.error_occurred.connect(self._on_camera_error)
            
            # Démarrage
            self.camera_thread.start()
            print("✅ Thread caméra démarré")
        
        except Exception as e:
            QMessageBox.critical(self, "Erreur Caméra", 
                               f"Impossible de démarrer la caméra:\n{str(e)}")
    
    def stop_camera(self):
        """Arrête proprement le thread caméra"""
        if self.camera_thread:
            print("⏳ Arrêt du thread caméra...")
            self.camera_thread.stop()
            self.camera_thread = None
            print("✅ Thread caméra arrêté")
    
    # ===========================
    # SLOTS SIGNAUX CAMÉRA
    # ===========================
    
    @pyqtSlot(dict)
    def _on_pupil_detected(self, pupil_data):
        """Mise à jour des infos pupille"""
        self.control_panel.update_info(
            diameter=pupil_data['diameter_mm'],
            quality=pupil_data['quality_score']
        )
    
    @pyqtSlot(float)
    def _on_fps_updated(self, fps):
        """Mise à jour FPS"""
        self.control_panel.update_info(fps=fps)
    
    @pyqtSlot(str)
    def _on_camera_error(self, error_msg):
        """Affichage erreur caméra"""
        QMessageBox.critical(self, "Erreur Caméra", error_msg)
        self.status_bar.showMessage(f"🔴 {error_msg}")
    
    # ===========================
    # SLOTS PANNEAU DE CONTRÔLE
    # ===========================
    
    def _on_threshold_changed(self, value):
        if self.camera_thread:
            self.camera_thread.set_threshold(value)
    
    def _on_blur_changed(self, value):
        if self.camera_thread:
            self.camera_thread.set_blur(value)
    
    def _on_display_mode_changed(self, mode):
        if self.camera_thread:
            self.camera_thread.set_display_mode(mode)
    
    def _on_test_requested(self):
        """Lancement d'un test PLR"""
        # TODO: Ouvrir dialogue de configuration test
        QMessageBox.information(self, "Test PLR", 
                              "Dialogue de test PLR à implémenter (MODULE 5)")
        self.status_bar.showMessage("⚠️ Fonction Test PLR en développement")
    
    def _on_settings_requested(self):
        """Ouverture menu options"""
        dialog = SettingsDialog(self,self.config_manager)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()
    
    def on_settings_changed(self, settings: dict):
        """Callback quand les paramètres changent"""
        print("🔧 Nouveaux paramètres reçus")
        
        # Appliquer les paramètres caméra
        if self.camera_thread and self.camera_thread.camera:
            cam_settings = settings.get('camera', {})
            
            # Appliquer résolution si changée
            if 'width' in cam_settings and 'height' in cam_settings:
                print(f"📹 Nouvelle résolution: {cam_settings['width']}x{cam_settings['height']}")
                # Note: Nécessite un redémarrage de la caméra pour prendre effet
            
            # Appliquer FPS
            if 'fps' in cam_settings:
                print(f"⏱️ Nouveau FPS: {cam_settings['fps']}")
        
        # Appliquer les paramètres de détection
        det_settings = settings.get('detection', {})
        if self.camera_thread:
            if 'canny_threshold1' in det_settings:
                self.camera_thread.set_threshold(det_settings['canny_threshold1'])
            
            if 'gaussian_blur' in det_settings:
                blur_value = det_settings['gaussian_blur']
                # Forcer impair
                if blur_value % 2 == 0:
                    blur_value += 1
                self.camera_thread.set_blur(blur_value)
        
        self.status_bar.showMessage("✅ Paramètres appliqués avec succès", 3000)


    def _show_about(self):
        """Affichage à propos"""
        QMessageBox.about(self, "À propos",
            "<h3>PLR Analyzer</h3>"
            "<p>Application d'analyse du réflexe pupillaire à la lumière</p>"
            "<p><b>Version:</b> 1.0.0-alpha</p>"
            "<p><b>Python:</b> 3.10+</p>"
            "<p><b>Librairies:</b> PyQt6, OpenCV</p>"
        )
    
    # ===========================
    # ÉVÉNEMENTS FENÊTRE
    # ===========================
    
    def closeEvent(self, event):
        """Fermeture propre de l'application"""
        reply = QMessageBox.question(self, "Quitter",
            "Voulez-vous vraiment quitter l'application ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            print("🛑 Fermeture de l'application...")
            self.stop_camera()
            event.accept()
        else:
            event.ignore()

# ====================================================
# CLASSE: OptionsDialog (AVEC STYLE FORCÉ)
# ====================================================
class OptionsDialog(QMessageBox):
    """Dialogue des options de configuration"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.setIcon(QMessageBox.Information)
        
        # STYLE FORCÉ POUR CONTRASTE
        self.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ffffff;
                font-size: 11pt;
                background-color: transparent;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0a3d91;
            }
        """)
        
        # Message avec formatage visible
        self.setText("<h2>Configuration de l'application</h2>")
        self.setInformativeText(
            "<p style='font-size: 10pt; line-height: 1.6;'>"
            "<b>📹 Caméra</b><br>"
            "Réglages disponibles dans l'interface principale<br><br>"
            "<b>🎯 Détection</b><br>"
            "Ajustez les seuils avec les curseurs latéraux<br><br>"
            "<b>💾 Données</b><br>"
            "Sauvegarde automatique dans <code>data/plr_results/</code><br><br>"
            "<b>Version :</b> 1.0.0"
            "</p>"
        )
        self.setStandardButtons(QMessageBox.Ok)




# ===========================
# POINT D'ENTRÉE
# ===========================

def main():
    """Fonction principale"""
    print("=" * 50)
    print("  PLR ANALYZER - Pupillary Light Reflex")
    print("=" * 50)
    print()
    
    # Création dossiers nécessaires
    os.makedirs("data/plr_results", exist_ok=True)
    
    # Application Qt
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Style moderne
    
    # Fenêtre principale
    window = MainWindow()
    window.show()
    
    print("✅ Application lancée")
    print("📹 Caméra active - Mode Navigation")
    print()
    
    # Boucle événements
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
