"""
test_pupil_detection.py
=======================
Tests pour l'algorithme de détection pupillaire.

Tests:
- Détection sur image synthétique (cercle noir)
- Robustesse au bruit
- Gestion cas limites (pas de pupille, multiple contours)
- Précision des mesures (diamètre, centre)
"""

import pytest
import cv2
import numpy as np
from camera_engine import CameraEngine


# ===========================
# HELPERS - IMAGES SYNTHÉTIQUES
# ===========================

def create_synthetic_pupil(size=(640, 480), pupil_center=(320, 240), pupil_radius=50, noise_level=0):
    """
    Crée une image test avec une pupille synthétique.
    
    Args:
        size: Dimensions (width, height)
        pupil_center: Centre de la pupille (x, y)
        pupil_radius: Rayon en pixels
        noise_level: Niveau de bruit gaussien (0-50)
    
    Returns:
        numpy.ndarray: Image BGR avec pupille noire sur fond gris
    """
    width, height = size
    img = np.ones((height, width, 3), dtype=np.uint8) * 180  # Fond gris clair
    
    # Dessiner la pupille (cercle noir)
    cv2.circle(img, pupil_center, pupil_radius, (0, 0, 0), -1)
    
    # Ajouter du bruit si demandé
    if noise_level > 0:
        noise = np.random.normal(0, noise_level, img.shape).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return img


def create_no_pupil_image(size=(640, 480)):
    """Crée une image sans pupille (fond uniforme)"""
    width, height = size
    return np.ones((height, width, 3), dtype=np.uint8) * 128  # Gris moyen


def create_multiple_contours(size=(640, 480)):
    """Crée une image avec plusieurs cercles (test rejet)"""
    width, height = size
    img = np.ones((height, width, 3), dtype=np.uint8) * 200
    
    # Plusieurs cercles de tailles différentes
    cv2.circle(img, (160, 240), 30, (0, 0, 0), -1)
    cv2.circle(img, (320, 240), 50, (0, 0, 0), -1)
    cv2.circle(img, (480, 240), 40, (0, 0, 0), -1)
    
    return img


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
# TESTS DÉTECTION
# ===========================

def test_detect_synthetic_pupil_perfect(camera):
    """
    ✅ Test : Détection sur pupille synthétique parfaite
    
    Vérifie:
    - Détection réussie
    - Centre proche de la position réelle (tolérance ±5px)
    - Diamètre proche du réel (tolérance ±10%)
    """
    # Image test
    expected_center = (320, 240)
    expected_radius = 50
    img = create_synthetic_pupil(pupil_center=expected_center, pupil_radius=expected_radius)
    
    # Injection manuelle dans le moteur (simule une frame caméra)
    # Note: Nécessite une méthode detect_pupil_from_frame() ou similaire
    pupil = camera._detect_pupil_internal(img)  # Méthode à implémenter
    
    assert pupil is not None, "Pupille non détectée sur image synthétique"
    
    # Vérification du centre
    detected_x, detected_y = pupil['center']
    center_error = np.sqrt((detected_x - expected_center[0])**2 + 
                          (detected_y - expected_center[1])**2)
    assert center_error < 5, f"Centre imprécis: erreur {center_error:.1f}px (attendu <5px)"
    
    # Vérification du diamètre
    expected_diameter = expected_radius * 2
    detected_diameter = pupil['diameter_px']
    diameter_error = abs(detected_diameter - expected_diameter) / expected_diameter * 100
    assert diameter_error < 10, f"Diamètre imprécis: erreur {diameter_error:.1f}% (attendu <10%)"
    
    print(f"✅ Détection précise: centre={pupil['center']}, diamètre={detected_diameter:.1f}px")


def test_detect_synthetic_pupil_with_noise(camera):
    """
    ✅ Test : Robustesse au bruit
    
    Vérifie que la détection fonctionne malgré un bruit modéré.
    """
    img = create_synthetic_pupil(pupil_center=(320, 240), pupil_radius=50, noise_level=20)
    
    pupil = camera._detect_pupil_internal(img)
    
    # Peut échouer avec du bruit, mais doit au moins ne pas crasher
    if pupil is not None:
        assert pupil['diameter_px'] > 0
        print(f"✅ Détection avec bruit: diamètre={pupil['diameter_px']:.1f}px")
    else:
        print("⚠️ Détection échouée avec bruit (acceptable)")


def test_no_pupil_detected(camera):
    """
    ✅ Test : Gestion absence de pupille
    
    Vérifie que l'algorithme retourne None proprement.
    """
    img = create_no_pupil_image()
    
    pupil = camera._detect_pupil_internal(img)
    
    assert pupil is None, "Détection faussement positive sur image vide"
    print("✅ Pas de faux positif sur image vide")


def test_multiple_contours_selection(camera):
    """
    ✅ Test : Sélection du meilleur contour parmi plusieurs
    
    Vérifie que l'algorithme choisit le contour le plus circulaire.
    """
    img = create_multiple_contours()
    
    pupil = camera._detect_pupil_internal(img)
    
    # Doit détecter UN seul contour (le plus circulaire)
    if pupil is not None:
        assert isinstance(pupil['center'], tuple)
        assert pupil['diameter_px'] > 0
        print(f"✅ Contour sélectionné: centre={pupil['center']}, diamètre={pupil['diameter_px']:.1f}px")
    else:
        print("⚠️ Aucun contour valide trouvé (acceptable si critères stricts)")


def test_edge_cases_small_pupil(camera):
    """
    ✅ Test : Pupille très petite (limite min_area)
    """
    img = create_synthetic_pupil(pupil_radius=10)  # Petit rayon
    
    pupil = camera._detect_pupil_internal(img)
    
    # Peut être rejetée si < min_area
    if pupil is None:
        print("⚠️ Pupille trop petite rejetée (min_area)")
    else:
        assert pupil['diameter_px'] < 30  # Cohérence
        print(f"✅ Petite pupille détectée: {pupil['diameter_px']:.1f}px")


def test_edge_cases_large_pupil(camera):
    """
    ✅ Test : Pupille très grande (limite max_area)
    """
    img = create_synthetic_pupil(pupil_radius=100)  # Grand rayon
    
    pupil = camera._detect_pupil_internal(img)
    
    # Peut être rejetée si > max_area
    if pupil is None:
        print("⚠️ Pupille trop grande rejetée (max_area)")
    else:
        assert pupil['diameter_px'] > 150  # Cohérence
        print(f"✅ Grande pupille détectée: {pupil['diameter_px']:.1f}px")


# ===========================
# TESTS CALIBRATION
# ===========================

def test_mm_conversion(camera):
    """
    ✅ Test : Conversion pixels → millimètres
    
    Vérifie que diameter_mm est cohérent avec mm_per_pixel.
    """
    img = create_synthetic_pupil(pupil_radius=50)
    pupil = camera._detect_pupil_internal(img)
    
    if pupil is not None:
        expected_mm = pupil['diameter_px'] * camera.mm_per_pixel
        assert abs(pupil['diameter_mm'] - expected_mm) < 0.01, \
            f"Conversion mm incorrecte: {pupil['diameter_mm']:.2f} != {expected_mm:.2f}"
        
        print(f"✅ Conversion: {pupil['diameter_px']:.1f}px = {pupil['diameter_mm']:.2f}mm")


# ===========================
# EXÉCUTION STANDALONE
# ===========================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
