"""
tests/test_engine.py
Test de la logique de séquençage (avec Mock Caméra).
"""
import pytest
import time
from plr_test_engine import PLRTestEngine

# --- LE MOCK (La Doublure) ---
class MockCamera:
    """Imite le comportement de CameraEngine sans matériel."""
    def __init__(self):
        self.is_recording = False
        self.threshold_val = 50
        self.blur_val = 5
        self.roi_w = 400
        self.roi_h = 400
        self.roi_off_x = 0
        self.roi_off_y = 0
        self.mm_per_pixel = 0.05
        self.start_time = 0

    def is_ready(self):
        return True # On fait semblant que la caméra est prête

    def start_csv_recording(self, filepath):
        self.is_recording = True
        # On crée un faux fichier vide pour que le code ne plante pas s'il vérifie
        with open(filepath, 'w') as f:
            f.write("timestamp,diameter\n")

    def stop_csv_recording(self):
        self.is_recording = False

# --- LES TESTS ---

def test_engine_configuration():
    """Vérifie que la configuration met bien à jour les paramètres internes."""
    fake_cam = MockCamera()
    engine = PLRTestEngine(fake_cam)
    
    # On configure avec des valeurs spécifiques
    engine.configure(flash_delay=1.0, flash_count=3,
                     flash_duration_ms=500, response_duration=2.0)

    assert engine.flash_delay == 1.0
    assert engine.flash_count == 3
    assert engine.flash_duration_s == 0.5 # 500ms / 1000
    assert engine.response_duration == 2.0

def test_engine_start_stop(tmp_path):
    """Vérifie que le moteur lance et arrête l'enregistrement de la caméra."""
    fake_cam = MockCamera()
    engine = PLRTestEngine(fake_cam)
    
    # On utilise un fichier temporaire pour l'enregistrement
    # Note : start_test lance un Thread, ce qui est dur à tester simplement.
    # Ici, on va tester manuellement la méthode interne _run_sequence si possible,
    # ou simplement vérifier que stop_test appelle bien la caméra.
    
    engine.is_running = True
    fake_cam.is_recording = True # Supposons qu'elle tourne
    
    engine.stop_test()
    
    # Verdict : Le moteur a-t-il bien dit à la caméra de s'arrêter ?
    assert fake_cam.is_recording is False

def test_run_sequence_logic():
    """Test direct de la séquence (sans thread) pour couverture."""
    fake_cam = MockCamera()
    engine = PLRTestEngine(fake_cam)
    
    # Config très courte pour que le test soit rapide
    engine.configure(flash_delay=0.1, flash_count=1,
                     flash_duration_ms=10, response_duration=0.1)
    
    engine.is_running = True
    
    # On appelle directement la méthode privée _run_sequence
    # Attention : cela bloque pendant ~0.7s (0.5s stab + durées)
    engine._run_sequence()
    
    assert fake_cam.is_recording is False # Doit être arrêté à la fin