"""
test_config.py
==============
Tests du ConfigManager (lecture/écriture/valeurs par défaut).
"""
import json
import pytest
from settings_dialog import ConfigManager


class TestConfigManager:
    def test_creates_default_on_missing_file(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        assert cm.config != {}
        assert "general" in cm.config
        assert "protocol" in cm.config

    def test_load_existing_config(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        data = {"general": {"language": "en"}, "camera": {"index": 1}}
        cfg_path.write_text(json.dumps(data), encoding='utf-8')

        cm = ConfigManager(str(cfg_path))
        assert cm.config["general"]["language"] == "en"
        assert cm.config["camera"]["index"] == 1

    def test_save_and_reload(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        cm.config["general"]["language"] = "en"
        cm.save()

        cm2 = ConfigManager(cfg_path)
        assert cm2.config["general"]["language"] == "en"

    def test_save_with_argument(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        new_conf = {"test_key": "test_value"}
        cm.save(new_conf)
        assert cm.config == new_conf

    def test_get_nested_key(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        # La config par défaut a protocol.flash_delay_s = 2
        val = cm.get("protocol", "flash_delay_s")
        assert val == 2

    def test_get_section(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        protocol = cm.get("protocol")
        assert isinstance(protocol, dict)
        assert "flash_duration_ms" in protocol

    def test_get_missing_key_returns_default(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        val = cm.get("protocol", "nonexistent", d=42)
        assert val == 42

    def test_get_missing_section_returns_empty_dict(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        val = cm.get("nonexistent_section")
        assert val == {}

    def test_default_config_has_all_sections(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        for section in ("general", "camera", "detection", "protocol", "recording"):
            assert section in cm.config, f"Section manquante : {section}"

    def test_default_detection_params(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        det = cm.get("detection")
        assert det["canny_threshold1"] == 50
        assert det["gaussian_blur"] == 5
        assert det["roi_width"] == 400

    def test_default_flash_color(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        cm = ConfigManager(cfg_path)
        assert cm.get("protocol", "default_color") == "WHITE"
