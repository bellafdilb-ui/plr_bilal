"""
tests/test_hardware.py
======================
Test des signaux et de la logique HardwareManager.
"""
import pytest
from hardware_manager import HardwareManager

def test_connection_signal(qtbot):
    """Vérifie que la connexion émet le bon signal."""
    hw = HardwareManager()
    
    # On utilise qtbot pour "écouter" le signal connection_status_changed
    with qtbot.waitSignal(hw.connection_status_changed, timeout=1000) as blocker:
        hw.connect_device()
        
    # On vérifie que le signal a transporté "True"
    assert blocker.args[0] is True
    assert hw.is_connected is True

def test_trigger_simulation(qtbot):
    """Vérifie que la simulation de gâchette émet le signal."""
    hw = HardwareManager()
    
    with qtbot.waitSignal(hw.trigger_pressed, timeout=1000):
        hw.simulate_trigger_press()
