"""
tests/test_qa_comprehensive.py
==============================
QA Comprehensive Test Suite.
Focus: Hardware Protocol Integrity & Analyzer Synchronization Logic.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

# Import modules
from hardware_manager import HardwareManager
from plr_analyzer import PLRAnalyzer

# --- HARDWARE PROTOCOL TESTS ---
# Critical: Ensure commands sent to the microcontroller are exactly what is expected.

def test_hardware_command_formatting():
    """
    QA Check: Verify that configuration parameters are correctly converted 
    to the specific string format required by the firmware.
    """
    hw = HardwareManager()
    hw.is_connected = True
    hw.worker = MagicMock()
    
    # Scenario: Configure Blue Flash, 200ms, Intensity 50% (32768), Freq 10Hz
    hw.configure_flash_sequence(
        color="BLUE",
        duration_ms=200,
        intensity=32768,
        frequency=10.0,
        ambiance=0,
        flash_count=1
    )
    
    # Retrieve sent commands
    # The worker.send is called sequentially via a timer in the real class.
    # The first command is sent immediately, so it is popped from the queue.
    
    # 1. Check Color Mapping (First command sent immediately)
    hw.worker.send.assert_called()
    last_sent_cmd = hw.worker.send.call_args[0][0]
    assert "valeur: bleu" in last_sent_cmd, f"Expected 'bleu', got {last_sent_cmd}"
    
    # Inspect the remaining queue
    queue = hw.command_queue
    assert len(queue) > 0, "Command queue should not be empty"
    
    # 2. Check Duration Conversion (ms -> us)
    # 200ms * 1000 = 200000us
    assert "valeur: 200000" in queue[0], f"Expected '200000', got {queue[0]}"
    
    # 3. Check Intensity
    assert "valeur: 32768" in queue[1]
    
    # 4. Check Frequency
    assert "valeur: 10.0" in queue[2]

def test_hardware_safety_stop():
    """
    QA Check: Ensure stop_flash clears the queue to prevent 
    delayed firing after a stop command.
    """
    hw = HardwareManager()
    hw.is_connected = True
    hw.worker = MagicMock()
    
    # Fill queue with pending triggers
    hw.command_queue = ["CMD1", "CMD2", "depart_flash"]
    
    hw.stop_flash()
    
    # Queue must be cleared
    assert len(hw.command_queue) == 0
    # Immediate stop command sent
    hw.worker.send.assert_called_with("Type : commande, Commande :arret_flash")

# --- ANALYZER SYNCHRONIZATION TESTS ---
# Critical: The 'Black Frame' logic determines T0. If this fails, latency metrics are wrong.

def test_analyzer_t0_detection_logic():
    """
    QA Check: Verify T0 detection based on brightness drop (Black Frame).
    """
    analyzer = PLRAnalyzer()
    
    # Create synthetic data
    # 0.0s - 0.9s: Bright (Baseline)
    # 1.0s: DARK (Black Frame / Synchro) -> Brightness < 10
    # 1.1s: Bright (Flash Start)
    
    timestamps = [0.0, 0.5, 0.9, 1.0, 1.1, 1.2]
    brightness = [50,  50,  50,  5,   255, 255] # 5 is below threshold 10
    diameters  = [8,   8,   8,   0,   2,   2]   # Diameter 0 during black frame
    
    df = pd.DataFrame({
        'timestamp_s': timestamps,
        'brightness': brightness,
        'diameter_mm': diameters,
        'diameter_smooth': diameters,
        'velocity_mm_s': [0]*6
    })
    analyzer.data = df
    
    # Run detection
    t0 = analyzer.detect_t0_from_black_frame()
    
    # Expectation: T0 should be the timestamp of the frame *immediately following* the black frame
    # Black frame is at 1.0s. Next frame is 1.1s.
    assert t0 == 1.1, f"Expected T0 at 1.1s (Flash start), got {t0}"

def test_analyzer_missing_black_frame():
    """
    QA Check: Ensure analyzer behaves correctly if no sync frame is found.
    """
    analyzer = PLRAnalyzer()
    df = pd.DataFrame({
        'timestamp_s': [0.0, 1.0],
        'brightness': [50, 50], # No darkness
        'diameter_mm': [8, 8]
    })
    analyzer.data = df
    
    t0 = analyzer.detect_t0_from_black_frame()
    assert t0 is None

# --- FILENAME SANITIZATION TEST ---

def test_filename_sanitization_logic():
    """
    QA Check: Replicate the logic in MainWindow to ensure it handles edge cases.
    """
    # Logic copied from MainWindow
    def sanitize(name):
        s = "".join([c if c.isalnum() else "_" for c in name])
        if not s.replace("_", ""):
            return "Patient_Fallback"
        return s
    
    assert sanitize("Rex") == "Rex"
    assert sanitize("Jean-Pierre") == "Jean_Pierre"
    assert sanitize("O'Connor") == "O_Connor"
    assert sanitize("Dr. House") == "Dr__House"
    
    # Edge case: Empty result
    assert sanitize("!!!") == "Patient_Fallback"