"""
test_plr_engine.py
==================
Tests du moteur de séquence PLR (PLRTestEngine).
"""
import pytest
import time
import threading
from unittest.mock import MagicMock
from plr_test_engine import PLRTestEngine


@pytest.fixture
def mock_camera(tmp_path):
    """Crée une fausse caméra qui simule les opérations d'enregistrement."""
    cam = MagicMock()
    cam.is_ready.return_value = True
    cam.recording = False
    cam.start_time = time.time()

    def fake_start_recording(base_path):
        cam.recording = True
        cam.start_time = time.time()
        # Créer les fichiers factices
        open(base_path + ".csv", 'w').close()
        open(base_path + ".avi", 'w').close()

    def fake_stop_recording():
        cam.recording = False

    cam.start_recording.side_effect = fake_start_recording
    cam.stop_recording.side_effect = fake_stop_recording
    return cam


@pytest.fixture
def engine(mock_camera):
    return PLRTestEngine(mock_camera)


# ─── Configuration ───────────────────────────────────────────────────

class TestConfigure:
    def test_default_values(self, engine):
        assert engine.flash_delay == 2.0
        assert engine.flash_count == 1
        assert engine.response_duration == 5.0

    def test_configure_updates_params(self, engine):
        engine.configure(flash_delay=1.5, flash_count=2,
                         flash_duration_ms=500, response_duration=3.0)
        assert engine.flash_delay == 1.5
        assert engine.flash_count == 2
        assert engine.flash_duration_s == 0.5
        assert engine.response_duration == 3.0

    def test_configure_duration_conversion(self, engine):
        engine.configure(flash_duration_ms=1234)
        assert engine.flash_duration_s == pytest.approx(1.234, rel=1e-3)


# ─── Start / Stop ────────────────────────────────────────────────────

class TestStartStop:
    def test_start_sets_running(self, engine):
        engine.start_test("ref01")
        assert engine.is_running is True
        assert engine.ref_name == "ref01"
        # Laisser le thread démarrer puis cleanup
        time.sleep(0.2)
        engine.stop_test()

    def test_stop_clears_running(self, engine, mock_camera):
        engine.is_running = True
        mock_camera.recording = True
        engine.stop_test()
        assert engine.is_running is False
        mock_camera.stop_recording.assert_called_once()


# ─── Notify flash fired ─────────────────────────────────────────────

class TestNotifyFlash:
    def test_notify_sets_event(self, engine, mock_camera):
        engine.is_running = True
        mock_camera.recording = True
        mock_camera.start_time = time.time() - 2.0

        engine.notify_flash_fired()

        assert engine._flash_event.is_set()
        assert engine._flash_timestamp is not None
        assert engine._flash_timestamp == pytest.approx(2.0, abs=0.5)

    def test_notify_when_not_running(self, engine, mock_camera):
        """notify_flash_fired sans enregistrement ne doit pas crasher."""
        engine.is_running = False
        mock_camera.recording = False
        engine.notify_flash_fired()
        assert engine._flash_event.is_set()
        assert engine._flash_timestamp is None


# ─── Séquence complète (rapide) ──────────────────────────────────────

class TestSequence:
    def test_full_sequence_with_flash(self, engine, mock_camera, qtbot):
        """Simule une séquence complète avec flash déclenché rapidement."""
        engine.configure(flash_delay=0.1, flash_count=1,
                         flash_duration_ms=50, response_duration=0.2)

        # Lancer la séquence
        with qtbot.waitSignal(engine.test_finished, timeout=10000) as blocker:
            engine.start_test("test_auto")
            # Simuler le flash 200ms après le départ
            time.sleep(0.2)
            mock_camera.recording = True
            engine.notify_flash_fired()

        meta = blocker.args[0]
        assert 'csv_path' in meta
        assert 'flash_timestamp' in meta
        assert meta['config']['flash_delay_s'] == 0.1

    def test_sequence_timeout_without_flash(self, engine, mock_camera):
        """Sans flash, la séquence doit timeout et s'arrêter proprement."""
        engine.configure(flash_delay=0.0, flash_count=1,
                         flash_duration_ms=50, response_duration=0.1)
        # Mettre un timeout très court pour le test
        engine.flash_delay = 0.0

        engine.start_test("test_timeout")
        # Pas de notify_flash_fired → timeout dans _run_sequence
        # Le timeout interne est flash_delay + 30s, trop long pour un test unitaire.
        # On teste plutôt que stop_test débloque proprement.
        time.sleep(0.3)
        engine.stop_test()
        assert engine.is_running is False

    def test_camera_not_ready(self, engine, mock_camera):
        """Si la caméra n'est pas prête, la séquence ne démarre pas."""
        mock_camera.is_ready.return_value = False
        engine.start_test("test_no_cam")
        time.sleep(0.3)
        # Le thread s'est terminé sans lancer l'enregistrement
        mock_camera.start_recording.assert_not_called()
