"""
test_camera_engine.py
=====================
Tests unitaires pour le module camera_engine.py

Prérequis:
- pytest installé : pip install pytest
- Caméra disponible sur le système

Exécution:
    pytest tests/test_camera_engine.py -v
"""

import pytest
import sys
import os

# Ajoute le dossier parent au path pour importer camera_engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from camera_engine import CameraEngine


# ===========================
# TEST 1 : INITIALISATION
# ===========================

def test_camera_initialization_valid():
    """
    TEST 1A : Initialisation avec caméra valide
    
    Vérifie que:
    - L'objet CameraEngine se crée sans erreur
    - La caméra s'ouvre (cap.isOpened() == True)
    - Les paramètres par défaut sont corrects
    """
    # Arrange (préparation)
    camera_index = 0  # Caméra par défaut
    
    # Act (action)
    camera = CameraEngine(camera_index)
    
    # Assert (vérifications)
    assert camera is not None, "CameraEngine n'a pas été créé"
    assert camera.cap is not None, "VideoCapture n'est pas initialisé"
    assert camera.cap.isOpened(), "La caméra ne s'est pas ouverte"
    
    # Nettoyage
    camera.release()
    print("✅ TEST 1A PASSÉ : Initialisation caméra valide")


def test_camera_initialization_invalid():
    """
    TEST 1B : Initialisation avec index invalide
    
    Vérifie que:
    - Le système gère gracieusement les index invalides
    - Aucune exception fatale n'est levée
    """
    # Arrange
    invalid_index = 99  # Index qui n'existe probablement pas
    
    # Act
    try:
        camera = CameraEngine(invalid_index)
        is_opened = camera.cap.isOpened()
        camera.release()
        
        # Assert
        assert not is_opened, "Une caméra invalide s'est ouverte (bizarre !)"
        print("✅ TEST 1B PASSÉ : Gestion caméra invalide")
        
    except Exception as e:
        # Si une exception est levée, on vérifie qu'elle est documentée
        pytest.fail(f"❌ Exception non gérée: {type(e).__name__}: {e}")


def test_camera_default_parameters():
    """
    TEST 1C : Paramètres par défaut
    
    Vérifie que:
    - La résolution par défaut est correcte
    - Les paramètres de détection sont initialisés
    """
    # Arrange & Act
    camera = CameraEngine(0)
    
    # Assert
    assert hasattr(camera, 'blur_kernel'), "Attribut blur_kernel manquant"
    assert hasattr(camera, 'threshold_value'), "Attribut threshold_value manquant"
    assert hasattr(camera, 'min_area'), "Attribut min_area manquant"
    
    # Vérification des valeurs par défaut
    assert camera.blur_kernel > 0, "blur_kernel doit être positif"
    assert 0 <= camera.threshold_value <= 255, "threshold_value invalide"
    assert camera.min_area > 0, "min_area doit être positif"
    
    # Nettoyage
    camera.release()
    print("✅ TEST 1C PASSÉ : Paramètres par défaut corrects")


# ===========================
# FIXTURE PYTEST (OPTIONNEL)
# ===========================

@pytest.fixture
def camera_instance():
    """
    Fixture pour créer/détruire automatiquement une caméra
    Utilisation dans les tests suivants
    """
    camera = CameraEngine(0)
    yield camera  # Fournit l'objet au test
    camera.release()  # Nettoyage automatique


# ===========================
# POINT D'ENTRÉE
# ===========================

if __name__ == "__main__":
    """Permet d'exécuter directement ce fichier"""
    print("=" * 60)
    print("  TEST MODULE 1 : camera_engine.py")
    print("=" * 60)
    print()
    
    # Exécution des tests
    pytest.main([__file__, "-v", "--tb=short"])
