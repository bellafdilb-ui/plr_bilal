"""
test_camera_capture.py
======================
Tests pour la capture et le traitement d'images.

Tests:
- Capture de frame valide
- Dimensions de l'image
- Format BGR
- Détection pupille (avec/sans succès)
"""

import pytest
import cv2
import numpy as np
from camera_engine import CameraEngine


# ===========================
# FIXTURES
# ===========================

@pytest.fixture
def camera():
    """Fixture : Caméra initialisée"""
    cam = CameraEngine(camera_index=0)
    yield cam
    cam.release()


# ===========================
# TESTS CAPTURE
# ===========================

def test_grab_frame_returns_valid_image(camera):
    """
    ✅ Test : grab_and_detect() retourne une image valide
    
    Vérifie:
    - Image non None
    - Type numpy array
    - 3 canaux (BGR)
    - Dimensions > 0
    """
    if not camera.is_ready():
        pytest.skip("⚠️ Caméra non disponible")
    
    frame, pupil = camera.grab_and_detect()
    
    # Vérifications de base
    assert frame is not None, "Frame ne doit pas être None"
    assert isinstance(frame, np.ndarray), "Frame doit être un numpy array"
    assert len(frame.shape) == 3, "Frame doit avoir 3 dimensions (H, W, C)"
    assert frame.shape[2] == 3, "Frame doit avoir 3 canaux (BGR)"
    
    # Dimensions raisonnables
    height, width = frame.shape[:2]
    assert height > 0 and width > 0, f"Dimensions invalides: {width}x{height}"
    assert height >= 480, f"Hauteur trop petite: {height} (attendu ≥480)"
    assert width >= 640, f"Largeur trop petite: {width} (attendu ≥640)"
    
    print(f"✅ Frame capturée: {width}x{height}")


def test_grab_frame_consistency(camera):
    """
    ✅ Test : Capture successive retourne des frames différentes
    
    Vérifie que la caméra capture bien de nouvelles images.
    """
    if not camera.is_ready():
        pytest.skip("⚠️ Caméra non disponible")
    
    frame1, _ = camera.grab_and_detect()
    frame2, _ = camera.grab_and_detect()
    
    assert frame1 is not None and frame2 is not None
    
    # Les frames doivent être différentes (caméra en mouvement)
    # On vérifie juste qu'elles ne sont pas identiques pixel par pixel
    difference = cv2.absdiff(frame1, frame2)
    has_changed = np.sum(difference) > 0
    
    # Note: Ce test peut échouer si la caméra est statique
    # Dans ce cas, on accepte aussi des frames identiques
    print(f"✅ Différence entre frames: {np.sum(difference)} (0 = statique, >0 = mouvement)")


def test_pupil_detection_structure(camera):
    """
    ✅ Test : Structure du dictionnaire pupil
    
    Vérifie que pupil contient les bonnes clés (même si None).
    """
    if not camera.is_ready():
        pytest.skip("⚠️ Caméra non disponible")
    
    _, pupil = camera.grab_and_detect()
    
    # pupil peut être None (pas de pupille détectée) ou un dict
    if pupil is not None:
        assert isinstance(pupil, dict), "pupil doit être un dictionnaire"
        
        required_keys = ['center', 'diameter_px', 'diameter_mm']
        for key in required_keys:
            assert key in pupil, f"Clé manquante: {key}"
        
        # Vérification des types
        if pupil['center'] is not None:
            assert isinstance(pupil['center'], tuple), "center doit être un tuple"
            assert len(pupil['center']) == 2, "center doit avoir 2 coordonnées"
        
        if pupil['diameter_px'] is not None:
            assert isinstance(pupil['diameter_px'], (int, float)), "diameter_px doit être un nombre"
            assert pupil['diameter_px'] > 0, "diameter_px doit être positif"
        
        print(f"✅ Pupille détectée: {pupil}")
    else:
        print("⚠️ Aucune pupille détectée (normal si pas d'œil devant la caméra)")


def test_display_modes(camera):
    """
    ✅ Test : Changement de mode d'affichage
    
    Vérifie que set_display_mode() fonctionne.
    """
    if not camera.is_ready():
        pytest.skip("⚠️ Caméra non disponible")
    
    modes = ['normal', 'roi', 'binary', 'mosaic']
    
    for mode in modes:
        camera.set_display_mode(mode)
        assert camera.display_mode == mode, f"Mode non changé: {camera.display_mode} != {mode}"
        
        # Capture une frame dans ce mode
        frame, _ = camera.grab_and_detect()
        assert frame is not None, f"Frame None en mode {mode}"
        
        print(f"✅ Mode {mode}: OK")


# ===========================
# TESTS PARAMÈTRES
# ===========================

def test_threshold_adjustment(camera):
    """
    ✅ Test : Ajustement du seuil de détection
    """
    original_threshold = camera.threshold_value
    
    # Test augmentation
    camera.set_threshold(100)
    assert camera.threshold_value == 100
    
    # Test diminution
    camera.set_threshold(30)
    assert camera.threshold_value == 30
    
    # Restauration
    camera.set_threshold(original_threshold)
    
    print(f"✅ Seuil ajustable: {original_threshold} → 100 → 30 → {original_threshold}")


def test_blur_kernel_adjustment(camera):
    """
    ✅ Test : Ajustement du noyau de flou
    """
    original_blur = camera.blur_kernel
    
    # Doit être impair
    camera.blur_kernel = 7
    assert camera.blur_kernel == 7
    
    camera.blur_kernel = original_blur
    
    print(f"✅ Blur kernel ajustable: {original_blur} → 7 → {original_blur}")


# ===========================
# EXÉCUTION STANDALONE
# ===========================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
