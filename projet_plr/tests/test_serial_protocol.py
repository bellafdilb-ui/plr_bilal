"""
test_serial_protocol.py
=======================
Tests du protocole série PLR : format des commandes et parsing du buffer.
"""
import pytest
from serial_worker import SerialWorker
from hardware_manager import HardwareManager


# ─── Format des commandes (_fmt) ─────────────────────────────────────

class TestCommandFormat:
    def test_fmt_basic(self):
        assert HardwareManager._fmt("version=0") == "!version=0;"

    def test_fmt_empty(self):
        assert HardwareManager._fmt("") == "!;"

    def test_fmt_with_spaces(self):
        assert HardwareManager._fmt("couleur flash=bleu") == "!couleur flash=bleu;"


# ─── Commandes de configuration flash ────────────────────────────────

class TestFlashCommands:
    def setup_method(self):
        self.hw = HardwareManager()

    def test_set_flash_color_blue(self):
        assert self.hw.set_flash_color("BLUE") == "!couleur flash=bleu;"

    def test_set_flash_color_red(self):
        assert self.hw.set_flash_color("RED") == "!couleur flash=rouge;"

    def test_set_flash_color_white(self):
        assert self.hw.set_flash_color("WHITE") == "!couleur flash=blanc;"

    def test_set_flash_color_unknown_defaults_blanc(self):
        assert self.hw.set_flash_color("GREEN") == "!couleur flash=blanc;"

    def test_set_flash_duration_normal(self):
        assert self.hw.set_flash_duration(3) == "!durée flash=003;"

    def test_set_flash_duration_clamp_min(self):
        assert self.hw.set_flash_duration(0) == "!durée flash=001;"

    def test_set_flash_duration_clamp_max(self):
        assert self.hw.set_flash_duration(99) == "!durée flash=010;"

    def test_set_flash_intensity_normal(self):
        assert self.hw.set_flash_intensity(512) == "!intensité flash=0512;"

    def test_set_flash_intensity_clamp_min(self):
        assert self.hw.set_flash_intensity(-10) == "!intensité flash=0000;"

    def test_set_flash_intensity_clamp_max(self):
        assert self.hw.set_flash_intensity(9999) == "!intensité flash=1023;"

    def test_set_flash_delay_normal(self):
        assert self.hw.set_flash_delay(2) == "!retard flash=002;"

    def test_set_flash_delay_clamp_zero(self):
        assert self.hw.set_flash_delay(0) == "!retard flash=000;"

    def test_set_flash_delay_clamp_max(self):
        assert self.hw.set_flash_delay(10) == "!retard flash=005;"


# ─── Parsing du buffer série (SerialWorker._parse_buffer) ───────────

class TestBufferParsing:
    """Teste le parsing sans port série réel (on instancie puis on appelle _parse_buffer)."""

    def setup_method(self):
        self.w = SerialWorker.__new__(SerialWorker)
        self.w.ser = None  # Pas de port réel
        self.received = []
        # Connecter manuellement le signal
        self.w.data_received = _FakeSignal(self.received)

    def test_parse_test_ok(self):
        result = self.w._parse_buffer("TEST OK")
        assert result == ""
        assert self.received == ["TEST OK"]

    def test_parse_ok(self):
        result = self.w._parse_buffer("OK")
        assert result == ""
        assert self.received == ["OK"]

    def test_parse_signal_D(self):
        result = self.w._parse_buffer("D")
        assert result == ""
        assert self.received == ["D"]

    def test_parse_signal_F(self):
        result = self.w._parse_buffer("F")
        assert result == ""
        assert self.received == ["F"]

    def test_parse_signal_f(self):
        result = self.w._parse_buffer("f")
        assert result == ""
        assert self.received == ["f"]

    def test_parse_signal_A(self):
        result = self.w._parse_buffer("A")
        assert result == ""
        assert self.received == ["A"]

    def test_parse_version(self):
        result = self.w._parse_buffer("version 1.23")
        assert result == ""
        assert self.received == ["version 1.23"]

    def test_parse_empty(self):
        result = self.w._parse_buffer("")
        assert result == ""
        assert self.received == []

    def test_parse_leading_newlines(self):
        result = self.w._parse_buffer("\r\n\r\nOK")
        assert result == ""
        assert self.received == ["OK"]

    def test_parse_unknown_kept(self):
        """Un buffer inconnu est conservé pour accumulation."""
        result = self.w._parse_buffer("xyz")
        assert result == "xyz"
        assert self.received == []

    def test_test_ok_priority_over_ok(self):
        """'TEST OK' doit être détecté même s'il contient 'OK'."""
        result = self.w._parse_buffer("TEST OK")
        assert self.received == ["TEST OK"]


class _FakeSignal:
    """Simule un Signal Qt pour capturer les émissions."""
    def __init__(self, capture_list):
        self._list = capture_list

    def emit(self, value):
        self._list.append(value)
