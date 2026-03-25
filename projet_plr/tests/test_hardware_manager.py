"""
test_hardware_manager.py
========================
Tests du HardwareManager : file d'attente de commandes, handshake, signaux d'examen.
Aucun port série réel n'est utilisé (tout est mocké).
"""
import pytest
from unittest.mock import MagicMock, patch
from hardware_manager import HardwareManager


@pytest.fixture
def hw():
    """Crée un HardwareManager avec un worker série mocké."""
    mgr = HardwareManager()
    mgr.worker = MagicMock()
    mgr.worker.running = True
    mgr.is_connected = True
    mgr._handshake_done = True
    return mgr


# ─── File d'attente de commandes ─────────────────────────────────────

class TestCommandQueue:
    def test_enqueue_sends_immediately_when_idle(self, hw):
        hw.enqueue_command("!test;")
        hw.worker.send.assert_called_once_with("!test;")
        assert hw._waiting_ok is True

    def test_enqueue_queues_when_busy(self, hw):
        hw._waiting_ok = True
        hw.enqueue_command("!cmd2;")
        # Ne doit PAS envoyer — juste mettre en file
        hw.worker.send.assert_not_called()
        assert len(hw.command_queue) == 1

    def test_ok_triggers_next_command(self, hw):
        """Simuler la réception de OK pour débloquer la file."""
        hw.enqueue_command("!cmd1;")
        hw.command_queue.append("!cmd2;")
        # Simuler la réception de OK
        hw._on_data_received("OK")
        # cmd2 doit avoir été envoyée
        assert hw.worker.send.call_count == 2

    def test_queue_empty_resets_state(self, hw):
        hw.enqueue_command("!cmd;")
        hw._on_data_received("OK")
        assert hw._waiting_ok is False
        assert hw.current_command is None

    def test_configure_flash_sequence_queues_4_commands(self, hw):
        hw.configure_flash_sequence("BLUE", 2000, intensity=100, delay_s=1)
        # 1re commande envoyée directement + 3 dans la file
        assert hw.worker.send.call_count == 1
        assert len(hw.command_queue) == 3


# ─── Handshake (protocole de connexion) ──────────────────────────────

class TestHandshake:
    def test_test_ok_completes_handshake(self, qtbot):
        hw = HardwareManager()
        hw._handshake_done = False
        hw.is_connected = False

        with qtbot.waitSignal(hw.connection_status_changed, timeout=1000) as blocker:
            hw._on_data_received("TEST OK")

        assert blocker.args[0] is True
        assert hw._handshake_done is True
        assert hw.is_connected is True

    def test_version_response_completes_handshake(self, qtbot):
        hw = HardwareManager()
        hw._handshake_done = False
        hw.is_connected = False

        with qtbot.waitSignal(hw.connection_status_changed, timeout=1000):
            hw._on_data_received("version 2.01")

        assert hw._handshake_done is True
        assert hw.is_connected is True

    def test_messages_ignored_before_handshake(self, hw):
        hw._handshake_done = False
        hw._exam_in_progress = False
        hw._on_data_received("F")
        # F ne doit pas être traité → exam_in_progress reste False
        assert hw._exam_in_progress is False


# ─── Signaux d'examen (D, F, f, A) ──────────────────────────────────

class TestExamSignals:
    def test_signal_D_emits_exam_started(self, hw, qtbot):
        with qtbot.waitSignal(hw.exam_started, timeout=1000):
            hw._on_data_received("D")
        assert hw._exam_in_progress is True

    def test_signal_F_emits_flash_fired(self, hw, qtbot):
        with qtbot.waitSignal(hw.flash_fired, timeout=1000):
            hw._on_data_received("F")
        assert hw._exam_in_progress is True

    def test_signal_f_emits_flash_fired(self, hw, qtbot):
        with qtbot.waitSignal(hw.flash_fired, timeout=1000):
            hw._on_data_received("f")

    def test_signal_A_emits_flash_ended(self, hw, qtbot):
        hw._exam_in_progress = True
        with qtbot.waitSignal(hw.flash_ended, timeout=1000):
            hw._on_data_received("A")
        assert hw._exam_in_progress is False


# ─── Commandes IR ────────────────────────────────────────────────────

class TestIRCommands:
    def test_set_ir_on(self, hw):
        hw.set_ir(True)
        hw.worker.send.assert_called_with("!marche IR=1;")

    def test_set_ir_off(self, hw):
        hw.set_ir(False)
        hw.worker.send.assert_called_with("!arret IR=0;")

    def test_set_ir_when_disconnected(self):
        hw = HardwareManager()
        hw.is_connected = False
        hw.worker = MagicMock()
        hw.set_ir(True)
        hw.worker.send.assert_not_called()


# ─── Déconnexion ─────────────────────────────────────────────────────

class TestDisconnect:
    def test_disconnect_stops_worker(self, hw, qtbot):
        with qtbot.waitSignal(hw.connection_status_changed, timeout=1000) as blocker:
            hw.disconnect_device()
        assert blocker.args[0] is False
        assert hw.is_connected is False
        assert hw.worker is None

    def test_disconnect_sends_ir_off(self, hw):
        """Vérifier que disconnect éteint bien l'IR.
        disconnect appelle stop_flash puis set_ir(False) via enqueue_command.
        Les commandes passent par la file : stop_flash envoie 'arret pwm=0',
        puis set_ir met 'arret IR=0' en file. On simule les OK pour débloquer."""
        worker_ref = hw.worker
        # Simuler la réponse OK à chaque envoi pour débloquer la file
        def fake_send(cmd):
            hw._waiting_ok = False  # Simuler la réception immédiate du OK
        worker_ref.send.side_effect = fake_send

        hw.disconnect_device()
        calls = [str(c) for c in worker_ref.send.call_args_list]
        ir_off_sent = any("arret IR=0" in c for c in calls)
        assert ir_off_sent
        assert hw.is_connected is False


# ─── Start exam ──────────────────────────────────────────────────────

class TestStartExam:
    def test_start_exam_enqueues_depart(self, hw):
        hw.start_exam()
        hw.worker.send.assert_called_once_with("!depart=1234;")

    def test_start_exam_blocked_if_already_running(self, hw):
        hw._exam_in_progress = True
        hw.start_exam()
        hw.worker.send.assert_not_called()

    def test_stop_flash_clears_queue(self, hw):
        hw.command_queue = ["!cmd1;", "!cmd2;"]
        hw.stop_flash()
        # La file doit contenir uniquement la commande d'arrêt
        assert len(hw.command_queue) == 0  # arret pwm envoyé directement


# ─── Pupil position (axe xy) ─────────────────────────────────────────

class TestPupilPosition:
    def test_sends_coordinates(self, hw):
        hw.set_pupil_position(68, 81)
        hw.worker.send.assert_called_once()
        call_args = str(hw.worker.send.call_args)
        assert "axe xy=068081" in call_args

    def test_blocked_during_exam(self, hw):
        hw._exam_in_progress = True
        hw.set_pupil_position(100, 200)
        hw.worker.send.assert_not_called()

    def test_blocked_when_queue_active(self, hw):
        hw._waiting_ok = True
        hw.set_pupil_position(100, 200)
        hw.worker.send.assert_not_called()

    def test_blocked_when_commands_pending(self, hw):
        hw.command_queue = ["!cmd;"]
        hw.set_pupil_position(100, 200)
        hw.worker.send.assert_not_called()

    def test_rate_limited(self, hw):
        hw.set_pupil_position(10, 20)
        hw.set_pupil_position(30, 40)  # < 200ms après → ignoré
        assert hw.worker.send.call_count == 1

    def test_coordinates_clamped(self, hw):
        hw.set_pupil_position(-5, 1500)
        call_args = str(hw.worker.send.call_args)
        assert "axe xy=000999" in call_args
