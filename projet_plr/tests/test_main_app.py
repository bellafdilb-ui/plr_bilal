"""
tests/test_main_app.py
======================
Test de la fenêtre principale avec Mocking complet des dépendances.
"""
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QCloseEvent
import numpy as np
from main_application import MainWindow, ControlPanel, VideoWidget, FlashOverlay

@pytest.fixture
def mock_dependencies(monkeypatch):
    """Remplace toutes les classes externes par des Mocks."""
    # 1. Database
    mock_db = MagicMock()
    mock_db.get_patient_history.return_value = []
    monkeypatch.setattr("main_application.DatabaseManager", lambda: mock_db)
    
    # 2. Config
    mock_conf = MagicMock()
    mock_conf.config = {"camera": {}, "protocol": {}, "detection": {}}
    mock_conf.get.return_value = {}
    monkeypatch.setattr("main_application.ConfigManager", lambda: mock_conf)
    
    # 3. Hardware & Thread Caméra
    monkeypatch.setattr("main_application.HardwareManager", MagicMock)
    
    # 4. CameraThread (Fix pour éviter spec=int causé par MagicMock(0))
    class MockCameraThread:
        def __init__(self, *args, **kwargs):
            self.frame_ready = MagicMock()
            self.pupil_detected = MagicMock()
            self.fps_updated = MagicMock()
            self.error_occurred = MagicMock()
            self.camera_started = MagicMock()
            self.camera = MagicMock()
            self.camera.threshold_val = 50
            self.camera.blur_val = 5
        def start(self): pass
        def stop(self): pass
        def set_threshold(self, v): pass
        def set_blur(self, v): pass
        def set_display_mode(self, m): pass

    monkeypatch.setattr("main_application.CameraThread", MockCameraThread)
    
    return mock_db

def test_mainwindow_startup(qtbot, mock_dependencies):
    """Vérifie que la fenêtre s'ouvre avec un patient."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    assert "Rex" in win.windowTitle()
    assert win.is_camera_ready is False # Le thread mocké n'a pas encore émis le signal

def test_start_test_logic(qtbot, mock_dependencies):
    """Vérifie la logique de lancement d'examen."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # On simule que la caméra est prête
    win.on_camera_started()
    assert win.is_camera_ready is True
    
    # On mock le moteur de test pour vérifier qu'il est appelé
    with patch("main_application.PLRTestEngine") as MockEngine:
        win.init_engine() # Initialise le moteur mocké
        win.start_test()
        
        assert win.is_test_running is True
        MockEngine.return_value.start_test.assert_called()

def test_ui_controls_during_test(qtbot, mock_dependencies):
    """Vérifie que l'interface se verrouille pendant l'examen."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Setup : Caméra prête
    win.on_camera_started()
    
    # 1. Lancement de l'examen
    with patch("main_application.PLRTestEngine"):
        win.init_engine()
        win.start_test()
        
        # VÉRIFICATION : Les contrôles doivent être désactivés
        assert win.is_test_running is True
        assert win.controls.bt.isEnabled() is False
        assert win.controls.pb.format() != "Terminé"
        
        # 2. Fin de l'examen (Simulation)
        meta = {'csv_path': 'dummy.csv', 'flash_timestamp': 1.0, 'config': {'flash_duration_ms': 200}}
        
        # On mock les vérifications de fichier pour éviter le "return" précoce
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1000), \
             patch("main_application.PLRAnalyzer") as MockAnalyzer:
            
            # On configure l'analyseur pour qu'il ne plante pas
            MockAnalyzer.return_value.analyze.return_value = {'amplitude_mm': 1.0}
            MockAnalyzer.return_value.data = None
            
            win.on_test_finished(meta)
            
            # VÉRIFICATION : Les contrôles doivent être réactivés
            assert win.is_test_running is False
            assert win.controls.bt.isEnabled() is True
            assert win.controls.pb.format() == "Terminé"

def test_discard_exam(qtbot, mock_dependencies, tmp_path):
    """Vérifie que 'Jeter' supprime bien le fichier temporaire."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Création d'un fichier dummy
    f = tmp_path / "temp_exam.csv"
    f.write_text("data")
    
    win.temp_result_meta = {'csv': str(f), 'metrics': {}}
    
    # Action : Jeter
    win.discard_exam()
    
    # Vérification
    assert not f.exists() # Le fichier doit avoir disparu
    assert win.temp_result_meta is None # Les métadonnées doivent être vidées

def test_save_new_exam(qtbot, mock_dependencies):
    """Vérifie l'appel à la base de données lors de la sauvegarde."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Setup état "Résultat en attente"
    win.temp_result_meta = {'csv': 'path.csv', 'metrics': {'amp': 1}}
    win.current_laterality = 'OD'
    win.txt_comments.setText("Test Commentaire")
    
    # Action : Sauvegarder
    win.save_new_exam()
    
    # Vérification : La méthode save_exam du mock DB a-t-elle été appelée ?
    # mock_dependencies est notre mock_db retourné par la fixture
    mock_dependencies.save_exam.assert_called_once()
    
    # Vérification des arguments passés
    args, kwargs = mock_dependencies.save_exam.call_args
    assert args[0] == 1    # Patient ID
    assert args[1] == 'OD' # Latéralité
    assert kwargs['comments'] == "Test Commentaire"
    assert win.temp_result_meta is None # Doit être reset après sauvegarde

def test_comparison_logic(qtbot, mock_dependencies):
    """Vérifie la logique de sélection automatique pour comparaison."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # On simule 2 examens dans l'historique
    win.table_hist.setRowCount(2)
    
    # Ligne 0 : OD (Même côté que l'actuel)
    win.table_hist.setItem(0, 1, QTableWidgetItem("OD"))
    chk0 = QTableWidgetItem(); chk0.setCheckState(Qt.Unchecked)
    chk0.setData(Qt.UserRole, {'id': 10, 'laterality': 'OD', 'csv_path': 'f1.csv'})
    win.table_hist.setItem(0, 5, chk0)
    
    # Ligne 1 : OG (L'autre œil -> Cible)
    win.table_hist.setItem(1, 1, QTableWidgetItem("OG"))
    chk1 = QTableWidgetItem(); chk1.setCheckState(Qt.Unchecked)
    chk1.setData(Qt.UserRole, {'id': 11, 'laterality': 'OG', 'csv_path': 'f2.csv'})
    win.table_hist.setItem(1, 5, chk1)
    
    win.current_laterality = 'OD'
    win.temp_result_meta = {'csv': 'dummy.csv', 'metrics': {}} # Simulation d'un résultat actif
    
    # On mock l'analyseur pour éviter qu'il cherche les fichiers CSV inexistants
    with patch("main_application.PLRAnalyzer") as MockAn:
        MockAn.return_value.load_data.return_value = True
        
        # Action : Comparer
        win.auto_compare_eyes()
        
        # Vérification : La case OG (Ligne 1) doit être cochée
        assert win.table_hist.item(1, 5).checkState() == Qt.Checked
        # La case OD (Ligne 0) doit rester décochée
        assert win.table_hist.item(0, 5).checkState() == Qt.Unchecked

def test_batch_selection(qtbot, mock_dependencies):
    """Vérifie la sélection par lot dans l'historique."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Setup table
    win.table_hist.setRowCount(3)
    # Row 0: OD
    win.table_hist.setItem(0, 1, QTableWidgetItem("OD"))
    chk0 = QTableWidgetItem(); chk0.setCheckState(Qt.Unchecked)
    win.table_hist.setItem(0, 5, chk0)
    # Row 1: OG
    win.table_hist.setItem(1, 1, QTableWidgetItem("OG"))
    chk1 = QTableWidgetItem(); chk1.setCheckState(Qt.Unchecked)
    win.table_hist.setItem(1, 5, chk1)
    # Row 2: OD
    win.table_hist.setItem(2, 1, QTableWidgetItem("OD"))
    chk2 = QTableWidgetItem(); chk2.setCheckState(Qt.Unchecked)
    win.table_hist.setItem(2, 5, chk2)

    # Test OD
    win.batch_selection("OD")
    assert chk0.checkState() == Qt.Checked
    assert chk1.checkState() == Qt.Unchecked
    assert chk2.checkState() == Qt.Checked

    # Test ALL
    win.batch_selection("ALL")
    assert chk1.checkState() == Qt.Checked

    # Test NONE
    win.batch_selection("NONE")
    assert chk0.checkState() == Qt.Unchecked

def test_history_deletion(qtbot, mock_dependencies):
    """Vérifie la suppression d'un examen."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    ex_data = {'id': 10, 'exam_date': '2023-01-01', 'csv_path': 'del.csv'}
    
    # Mock QMessageBox to say YES (16384 = Yes)
    with patch("PySide6.QtWidgets.QMessageBox.question", return_value=16384): 
        # Mock DB delete
        mock_dependencies.delete_exam.return_value = True
        
        win.delete_history_item(ex_data)
        
        mock_dependencies.delete_exam.assert_called_with(10)

def test_macro_insertion(qtbot, mock_dependencies):
    """Vérifie l'insertion de macro."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Mock macros in DB
    mock_dependencies.get_macros.return_value = [{'id':1, 'content': 'Macro Test'}]
    win._load_macros()
    
    # Trigger insertion
    win.combo_macros.setCurrentIndex(1) # Index 0 is placeholder
    
    assert "Macro Test" in win.txt_comments.toPlainText()
    assert win.combo_macros.currentIndex() == 0 # Should reset

def test_key_press_trigger(qtbot, mock_dependencies):
    """Vérifie que la barre d'espace déclenche la simulation hardware."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Mock hardware
    with patch.object(win.hardware, 'simulate_trigger_press') as mock_trigger:
        qtbot.keyClick(win, Qt.Key_Space)
        mock_trigger.assert_called_once()

def test_camera_error_handling(qtbot, mock_dependencies):
    """Vérifie la gestion d'erreur caméra."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
        win.on_camera_error("Test Error")
        mock_crit.assert_called_once()
        assert win.is_camera_ready is False
        assert win.controls.bt.isEnabled() is False

def test_control_panel_signals(qtbot):
    """Vérifie les signaux du panneau de contrôle."""
    cp = ControlPanel()
    qtbot.addWidget(cp)
    
    # Threshold
    with qtbot.waitSignal(cp.threshold_changed) as blocker:
        cp.st.setValue(100)
    assert blocker.args[0] == 100
    
    # Blur
    with qtbot.waitSignal(cp.blur_changed) as blocker:
        cp.sb.setValue(10)
    assert blocker.args[0] == 10
    
    # Mode
    with qtbot.waitSignal(cp.display_mode_changed) as blocker:
        cp.cm.setCurrentText("ROI")
    assert blocker.args[0] == "roi"
    
    # Getters
    cp.rod.setChecked(True)
    assert cp.get_selected_eye() == "OD"
    cp.rog.setChecked(True)
    assert cp.get_selected_eye() == "OG"
    
    cp.rc_blue.setChecked(True)
    assert cp.get_selected_color() == "BLUE"

def test_video_widget_update(qtbot):
    """Vérifie la conversion d'image dans VideoWidget."""
    vw = VideoWidget()
    qtbot.addWidget(vw)
    
    # Frame noire 100x100
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    vw.update_frame(frame)
    assert vw.pixmap() is not None

def test_flash_overlay(qtbot):
    """Vérifie l'overlay de flash."""
    w = FlashOverlay()
    qtbot.addWidget(w)
    w.set_color("#FF0000")
    assert w.current_color == "#FF0000"
    w.show()
    assert w.isVisible()
    w.close()

def test_mainwindow_close(qtbot, mock_dependencies):
    """Vérifie la fermeture et la sauvegarde de config."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Mock config save
    win.conf.save = MagicMock()
    
    # Trigger close
    event = QCloseEvent()
    win.closeEvent(event)
    
    assert event.isAccepted()
    win.conf.save.assert_called()

def test_reset_camera(qtbot, mock_dependencies):
    """Vérifie la réinitialisation de la caméra."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # On mock QTimer pour vérifier qu'il est bien lancé
    with patch("PySide6.QtCore.QTimer.singleShot") as mock_timer:
        win.reset_camera()
        assert win.is_camera_ready is False
        mock_timer.assert_called_once()

def test_menu_actions(qtbot, mock_dependencies):
    """Vérifie les actions du menu (Retour, Réglages, Calibration)."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # 1. Retour Accueil
    with patch("main_application.WelcomeScreen") as MockWelcome:
        win.return_to_home()
        assert win.isVisible() is False
        MockWelcome.return_value.show.assert_called()
        
    # 2. Réglages
    with patch("main_application.SettingsDialog") as MockSettings:
        win._settings()
        MockSettings.return_value.exec.assert_called()

def test_trigger_flash_logic(qtbot, mock_dependencies):
    """Vérifie la logique d'affichage du flash."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Force color
    win.current_color = "RED"
    
    # Trigger ON
    win.trigger_flash(True)
    assert win.flash.isVisible() is True
    assert win.flash.current_color == "#FF0000"
    
    # Trigger OFF
    win.trigger_flash(False)
    assert win.flash.isVisible() is False

def test_export_pdf_action(qtbot, mock_dependencies):
    """Vérifie l'appel à l'export PDF."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    win.temp_result_meta = {'csv': 'dummy.csv', 'metrics': {}}
    
    with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("test.pdf", "PDF")):
        with patch("main_application.PDFGenerator") as MockPDF:
            win.export_pdf()
            MockPDF.return_value.generate.assert_called()

def test_export_excel_ui(qtbot, mock_dependencies):
    """Vérifie l'interface d'export Excel."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    win.selected_historical_exam = {'id': 1, 'csv_path': 'dummy.csv', 'exam_date': '2023', 'laterality': 'OD'}
    
    with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("test.xlsx", "Excel")):
        with patch("os.path.exists", return_value=True):
            with patch("pandas.DataFrame.to_excel"), patch("pandas.read_csv"):
                win.export_excel()
                # Si pas d'exception, c'est passé

def test_update_historical_comment(qtbot, mock_dependencies):
    """Vérifie la mise à jour de commentaire historique."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    win.selected_historical_exam = {'id': 10, 'comments': 'Old'}
    win.txt_comments.setText("New Comment")
    
    mock_dependencies.update_exam_comment.return_value = True
    win.update_historical_comment()
    
    mock_dependencies.update_exam_comment.assert_called_with(10, "New Comment")
    assert win.selected_historical_exam['comments'] == "New Comment"

def test_apply_settings_logic(qtbot, mock_dependencies):
    """Vérifie l'application des réglages."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Mock camera thread
    win.camera_thread = MagicMock()
    win.camera_thread.camera_index = 0
    win.camera_thread.camera = MagicMock()
    
    settings = {
        "camera": {"index": 0},
        "detection": {
            "roi_width": 200, "roi_height": 200,
            "roi_offset_x": 10, "roi_offset_y": 10,
            "canny_threshold1": 100
        }
    }
    win._apply_set(settings)
    
    assert win.camera_thread.camera.roi_w == 200
    win.camera_thread.set_threshold.assert_called_with(100)

def test_show_about(qtbot, mock_dependencies):
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    with patch("PySide6.QtWidgets.QMessageBox.about") as mock_about:
        win._show_about()
        mock_about.assert_called()

def test_camera_thread_lifecycle(qtbot):
    """Teste le cycle de vie du thread caméra (run, stop, erreurs)."""
    from main_application import CameraThread
    
    # 1. Test Run Success
    with patch("main_application.CameraEngine") as MockEng:
        mock_cam = MockEng.return_value
        mock_cam.is_ready.return_value = True
        mock_cam.grab_and_detect.return_value = (np.zeros((10,10,3), dtype=np.uint8), {})
        
        ct = CameraThread(0)
        
        # On intercepte msleep pour arrêter la boucle après 1 itération
        def stop_loop(*args): ct.running = False
        ct.msleep = stop_loop
        
        with qtbot.waitSignal(ct.camera_started):
            ct.run() # Appel synchrone pour tester la logique
            
        assert ct.camera is not None
        mock_cam.release.assert_called()

    # 2. Test Init Failure
    with patch("main_application.CameraEngine") as MockEng:
        MockEng.return_value.is_ready.return_value = False
        ct = CameraThread(0)
        with qtbot.waitSignal(ct.error_occurred):
            ct.run()

    # 3. Test Runtime Failure (Frame None)
    with patch("main_application.CameraEngine") as MockEng:
        mock_cam = MockEng.return_value
        mock_cam.is_ready.return_value = True
        mock_cam.grab_and_detect.return_value = (None, None) # Simule déconnexion
        
        ct = CameraThread(0)
        ct.msleep = lambda x: None # No sleep needed
        
        with qtbot.waitSignal(ct.error_occurred):
            ct.run()

    # 4. Test Setters
    ct = CameraThread(0)
    ct.camera = MagicMock()
    ct.set_threshold(10)
    ct.camera.set_threshold.assert_called_with(10)
    ct.set_blur(5)
    ct.camera.set_blur_kernel.assert_called_with(5)
    ct.set_display_mode("ROI")
    ct.camera.set_display_mode.assert_called_with("ROI")
    ct.start_recording("f.csv")
    ct.camera.start_csv_recording.assert_called_with("f.csv")
    ct.stop_recording()
    ct.camera.stop_csv_recording.assert_called()

def test_history_context_menu(qtbot, mock_dependencies):
    """Vérifie le menu contextuel de l'historique."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    # Setup table
    win.table_hist.setRowCount(1)
    win.table_hist.setItem(0, 0, QTableWidgetItem("Date"))
    chk = QTableWidgetItem()
    chk.setData(Qt.UserRole, {'id': 1, 'csv_path': 'path', 'exam_date': '2023'})
    win.table_hist.setItem(0, 5, chk)
    
    # Mock QMenu
    with patch("main_application.QMenu") as MockMenu:
        menu = MockMenu.return_value
        mock_action = MagicMock()
        menu.addAction.return_value = mock_action
        menu.exec.return_value = mock_action
        
        with patch.object(win.table_hist, 'itemAt') as mock_item_at:
            mock_item = MagicMock()
            mock_item.row.return_value = 0
            mock_item_at.return_value = mock_item
            
            with patch.object(win, 'on_history_clicked') as mock_handler:
                win.show_history_menu(QPoint(0,0))
                mock_handler.assert_called()

def test_history_display_colors(qtbot, mock_dependencies):
    """Vérifie les couleurs dans le tableau historique."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    exams = [
        {'id': 1, 'exam_date': '2023', 'laterality': 'OD', 'results_data': {'flash_color': 'BLUE'}},
        {'id': 2, 'exam_date': '2023', 'laterality': 'OG', 'results_data': {'flash_color': 'RED'}}
    ]
    mock_dependencies.get_patient_history.return_value = exams
    win.load_patient_history()
    
    assert win.table_hist.item(0, 2).foreground().color().name() == "#007bff"
    assert win.table_hist.item(1, 2).foreground().color().name() == "#dc3545"

def test_init_engine_config(qtbot, mock_dependencies):
    """Vérifie que init_engine configure bien la caméra et l'engine."""
    patient = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123'}
    win = MainWindow(patient)
    qtbot.addWidget(win)
    
    win.conf.config = {"camera": {"mm_per_pixel": 0.1}, "detection": {"canny_threshold1": 123, "gaussian_blur": 7}}
    win.camera_thread = MagicMock()
    win.camera_thread.camera = MagicMock()
    
    win.init_engine()
    
    assert win.camera_thread.camera.mm_per_pixel == 0.1
    win.camera_thread.set_threshold.assert_called_with(123)