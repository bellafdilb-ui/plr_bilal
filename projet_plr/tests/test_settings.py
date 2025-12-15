"""
tests/test_settings.py
======================
Test de la boîte de dialogue des réglages et du ConfigManager.
"""
import pytest
from unittest.mock import MagicMock
import settings_dialog
from settings_dialog import SettingsDialog, ConfigManager

@pytest.fixture
def mock_db_settings(monkeypatch):
    """Mock la BDD pour ne pas bloquer l'ouverture du dialogue."""
    mock_cls = MagicMock()
    mock_inst = MagicMock()
    mock_inst.get_clinic_info.return_value = {}
    mock_inst.get_macros.return_value = []
    mock_cls.return_value = mock_inst
    monkeypatch.setattr(settings_dialog, "DatabaseManager", mock_cls)
    return mock_inst

def test_config_manager(tmp_path):
    """Vérifie lecture/écriture du fichier JSON."""
    cfg_file = tmp_path / "config.json"
    cm = ConfigManager(str(cfg_file))
    
    # Sauvegarde
    conf = {"general": {"language": "en"}}
    cm.save(conf)
    assert cfg_file.exists()
    
    # Relecture
    cm2 = ConfigManager(str(cfg_file))
    assert cm2.get("general", "language") == "en"

def test_settings_dialog_ui(qtbot, tmp_path, mock_db_settings):
    """Vérifie l'interaction avec l'interface des réglages."""
    cfg_file = tmp_path / "config_ui.json"
    cm = ConfigManager(str(cfg_file))
    
    dlg = SettingsDialog(config_manager=cm)
    qtbot.addWidget(dlg)
    
    # Modification d'une valeur via l'UI
    dlg.spin_baseline.setValue(10.0)
    
    # Vérification que get_settings récupère bien la valeur
    s = dlg.get_settings()
    assert s['protocol']['baseline_duration'] == 10.0