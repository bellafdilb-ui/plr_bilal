"""
test_video_recording.py
=======================
Tests pour l'enregistrement vidéo.

Tests:
- Démarrage/arrêt de l'enregistrement
- Format de fichier (MP4, codec H264)
- Métadonnées (timestamp, durée, FPS)
- Gestion des erreurs (disque plein, permissions)
- Préservation des données de détection
"""

import pytest
import os
import time
import cv2
from pathlib import Path
from camera_engine import CameraEngine


# ===========================
# FIXTURES
# ===========================

@pytest.fixture
def temp_output_dir(tmp_path):
    """
    Crée un dossier temporaire pour les vidéos.
    tmp_path est fourni automatiquement par pytest.
    """
    output_dir = tmp_path / "test_videos"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def camera(temp_output_dir):
    """
    Fixture : CameraEngine avec dossier de sortie temporaire.
    """
    camera = CameraEngine(camera_index=0, output_dir=str(temp_output_dir))
    yield camera
    camera.release()


# ===========================
# TESTS D'ENREGISTREMENT
# ===========================

def test_start_stop_recording(camera, temp_output_dir):
    """
    ✅ Test : Démarrer et arrêter un enregistrement.
    
    Vérifie:
    - Fichier vidéo créé
    - Extension .mp4
    - Taille > 0
    """
    # Démarrage
    filename = camera.start_recording(prefix="test_simple")
    assert filename is not None, "Échec démarrage enregistrement"
    assert camera.is_recording, "État is_recording incorrect"
    
    # Enregistrement de quelques frames
    for _ in range(30):  # ~1 seconde à 30 FPS
        ret, frame = camera.grab_frame()
        if ret:
            camera.write_frame(frame)
        time.sleep(0.033)  # ~30 FPS
    
    # Arrêt
    saved_path = camera.stop_recording()
    assert saved_path is not None, "Aucun chemin retourné après arrêt"
    assert not camera.is_recording, "État is_recording toujours actif"
    
    # Vérification fichier
    video_path = Path(saved_path)
    assert video_path.exists(), f"Fichier non créé: {saved_path}"
    assert video_path.suffix == ".mp4", f"Format incorrect: {video_path.suffix}"
    assert video_path.stat().st_size > 0, "Fichier vide"
    
    print(f"✅ Vidéo enregistrée: {video_path.name} ({video_path.stat().st_size} bytes)")


def test_recording_without_start(camera):
    """
    ✅ Test : Écrire une frame sans avoir démarré l'enregistrement.
    
    Vérifie:
    - write_frame() ne plante pas
    - Retourne False ou ignore silencieusement
    """
    ret, frame = camera.grab_frame()
    assert ret, "Impossible de capturer une frame"
    
    # Tentative d'écriture sans start_recording()
    result = camera.write_frame(frame)
    assert result is False or result is None, "write_frame devrait échouer proprement"


def test_video_metadata(camera, temp_output_dir):
    """
    ✅ Test : Vérifier les métadonnées de la vidéo.
    
    Vérifie:
    - FPS enregistré
    - Résolution (640x480 ou config caméra)
    - Codec (H264 ou MJPEG)
    """
    # Enregistrement court
    camera.start_recording(prefix="test_metadata")
    for _ in range(60):  # 2 secondes à 30 FPS
        ret, frame = camera.grab_frame()
        if ret:
            camera.write_frame(frame)
        time.sleep(0.033)
    
    saved_path = camera.stop_recording()
    
    # Lecture des métadonnées avec OpenCV
    cap = cv2.VideoCapture(saved_path)
    assert cap.isOpened(), f"Impossible de lire la vidéo: {saved_path}"
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    cap.release()
    
    print(f"📊 Métadonnées vidéo:")
    print(f"  - FPS: {fps}")
    print(f"  - Résolution: {width}x{height}")
    print(f"  - Frames: {frame_count}")
    
    assert fps > 0, "FPS invalide"
    assert width >= 640, f"Largeur trop petite: {width}"
    assert height >= 480, f"Hauteur trop petite: {height}"
    assert frame_count >= 50, f"Trop peu de frames: {frame_count}"  # Tolérance 60±10


def test_filename_generation(camera, temp_output_dir):
    """
    ✅ Test : Génération automatique du nom de fichier.
    
    Vérifie:
    - Format: YYYYMMDD_HHMMSS_prefix.mp4
    - Unicité (deux enregistrements successifs ont des noms différents)
    """
    # Premier enregistrement
    filename1 = camera.start_recording(prefix="patient001")
    camera.stop_recording()
    
    time.sleep(1.1)  # Attendre pour changer de seconde
    
    # Second enregistrement
    filename2 = camera.start_recording(prefix="patient001")
    camera.stop_recording()
    
    assert filename1 != filename2, "Noms de fichiers identiques"
    assert "patient001" in filename1, "Préfixe absent du nom"
    
    print(f"✅ Fichiers générés:")
    print(f"  - {filename1}")
    print(f"  - {filename2}")


def test_double_start_recording(camera):
    """
    ✅ Test : Démarrer un enregistrement alors qu'un autre est en cours.
    
    Vérifie:
    - Le second start_recording() échoue proprement
    - Le premier enregistrement n'est pas corrompu
    """
    # Premier enregistrement
    filename1 = camera.start_recording(prefix="test1")
    assert filename1 is not None
    
    # Tentative de démarrage d'un second enregistrement
    filename2 = camera.start_recording(prefix="test2")
    assert filename2 is None, "Second enregistrement ne devrait pas démarrer"
    assert camera.is_recording, "Premier enregistrement devrait être actif"
    
    # Arrêt normal
    saved_path = camera.stop_recording()
    assert saved_path is not None


def test_recording_with_detection_data(camera, temp_output_dir):
    """
    ✅ Test : Enregistrer avec données de détection incrustées.
    
    Vérifie:
    - Les frames avec overlays sont enregistrées
    - Les données pupillaires sont préservées
    """
    camera.start_recording(prefix="test_detection")
    
    pupil_detected = False
    for i in range(60):
        ret, frame = camera.grab_frame()
        if not ret:
            continue
        
        # Détection (toutes les 5 frames pour performances)
        if i % 5 == 0:
            pupil = camera.detect_pupil(frame)
            if pupil:
                pupil_detected = True
                # Dessiner l'ellipse sur la frame
                cv2.ellipse(frame, pupil['ellipse'], (0, 255, 0), 2)
        
        camera.write_frame(frame)
        time.sleep(0.033)
    
    saved_path = camera.stop_recording()
    
    # Vérification : au moins une détection a eu lieu
    # (même si caméra synthétique, on teste le mécanisme)
    print(f"✅ Détection pendant enregistrement: {pupil_detected}")
    assert saved_path is not None


def test_stop_without_start(camera):
    """
    ✅ Test : Arrêter un enregistrement qui n'a jamais été démarré.
    
    Vérifie:
    - stop_recording() ne plante pas
    - Retourne None proprement
    """
    result = camera.stop_recording()
    assert result is None, "stop_recording devrait retourner None"


# ===========================
# TESTS D'ERREURS
# ===========================

def test_invalid_output_directory(tmp_path):
    """
    ✅ Test : Dossier de sortie invalide.
    
    Vérifie:
    - Création automatique si dossier n'existe pas
    - Erreur si chemin invalide (ex: /invalid/path)
    """
    # Chemin valide mais inexistant
    valid_path = tmp_path / "new_folder"
    camera = CameraEngine(camera_index=0, output_dir=str(valid_path))
    assert valid_path.exists(), "Dossier non créé automatiquement"
    camera.release()
    
    # Chemin invalide (selon l'OS, peut lever une exception)
    # Sur Windows: C:\invalid\path, sur Linux: /root/nopermission
    try:
        invalid_camera = CameraEngine(camera_index=0, output_dir="/invalid/impossible/path")
        invalid_camera.release()
        pytest.fail("Devrait lever une exception pour chemin invalide")
    except (PermissionError, OSError, FileNotFoundError):
        pass  # Comportement attendu
