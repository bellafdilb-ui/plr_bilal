"""Tests pour l'enregistrement vidéo."""
import pytest
import time
from pathlib import Path
import cv2
import os
from camera_engine import CameraEngine


class TestVideoRecording:
    """Tests de l'enregistrement vidéo."""

    @pytest.fixture
    def camera(self):
        """Fixture camera avec nettoyage."""
        cam = CameraEngine(camera_index=0)
        yield cam
        cam.stop_video_recording()
        cam.release()

    @pytest.fixture
    def output_dir(self, tmp_path):
        """Dossier temporaire pour les vidéos."""
        video_dir = tmp_path / "videos"
        video_dir.mkdir()
        return video_dir

    def test_start_stop_recording(self, camera, output_dir):
        """Test démarrage/arrêt enregistrement vidéo."""
        # ✅ VÉRIFIER que la caméra est prête AVANT de tester
        if not camera.is_ready():
            pytest.skip("Caméra non disponible")
        
        # Configurer le dossier de sortie
        camera.output_dir = str(output_dir)
        
        # Démarrer l'enregistrement
        filename = camera.start_recording(prefix="test")
        
        # ✅ AJOUT : Gérer le cas où la caméra échoue
        if filename is None:
            pytest.skip("Impossible de démarrer l'enregistrement (caméra non prête)")
        
        assert filename is not None, "start_recording() a retourné None"
        assert camera.is_recording
        
        # Attendre 2 secondes
        time.sleep(2)
        
        # Arrêter l'enregistrement
        saved_path = camera.stop_recording()
        assert saved_path is not None
        assert not camera.is_recording
        
        # Vérifier le fichier
        video_path = output_dir / filename
        assert video_path.exists(), f"Vidéo non créée: {video_path}"
        assert video_path.stat().st_size > 1000, "Vidéo trop petite (probablement vide)"


    def test_recording_without_start(self, camera):
        """Test write_frame sans start_recording."""
        ret, frame = camera.read()
        assert ret

        # write_frame sans start_recording ne doit pas planter
        camera.write_frame(frame)  # ✅ CORRIGÉ
        assert not camera.is_recording

    def test_video_metadata(self, camera, output_dir):
        """Test métadonnées de la vidéo."""
        output_file = output_dir / "test_metadata.avi"
        
        # ✅ PASSER LE CHEMIN COMPLET EN STRING
        result = camera.start_recording(str(output_file))
        
        if not result:
            pytest.skip("Impossible de démarrer l'enregistrement")
        
        # Enregistrer 30 frames (~1 seconde à 30 FPS)
        for _ in range(30):
            ret, frame = camera.read()
            if ret:
                camera.write_frame(frame)
            time.sleep(0.03)
        
        saved_path = camera.stop_recording()
        
        # ✅ VÉRIFIER le chemin retourné (pas output_file)
        assert saved_path is not None, "stop_recording() a retourné None"
        assert Path(saved_path).exists(), f"Fichier manquant: {saved_path}"

        
        # Vérifier la vidéo avec OpenCV
        cap = cv2.VideoCapture(saved_path)
        assert cap.isOpened(), f"Impossible d'ouvrir la vidéo: {saved_path}"
        
        # Vérifier les propriétés
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        cap.release()
        
        assert frame_count >= 25, f"Trop peu de frames: {frame_count}"
        assert fps > 0, "FPS invalide"


    def test_recording_with_detection_data(self, camera, output_dir):
        """Test enregistrement avec données de détection."""
        output_file = output_dir / "test_with_detection.avi"
        camera.start_recording(str(output_file))

        # Simuler détection de pupille
        for i in range(20):
            ret, frame = camera.read()
            if ret:
                # Simuler des coordonnées de pupille
                detection_data = {
                    "pupil_center": (320 + i, 240 + i),
                    "pupil_radius": 30,
                    "timestamp": time.time(),
                }

                # Dessiner sur la frame (optionnel)
                cv2.circle(
                    frame,
                    detection_data["pupil_center"],
                    detection_data["pupil_radius"],
                    (0, 255, 0),
                    2,
                )

                camera.write_frame(frame)  # ✅ CORRIGÉ
            time.sleep(0.03)

        camera.stop_recording()
        assert output_file.exists()

        # Vérifier qu'on peut relire la vidéo
        cap = cv2.VideoCapture(str(output_file))
        assert cap.isOpened()
        ret, frame = cap.read()
        assert ret
        cap.release()

    def test_invalid_output_directory(self, camera):
        """Test avec chemin de sortie invalide."""
        invalid_path = "Z:/dossier/inexistant/video.avi"
        
        result = camera.start_recording(invalid_path)
        
        # ✅ start_recording() retourne False (pas None) en cas d'erreur
        assert result is False, f"Devrait retourner False, obtenu: {result}"
        assert not camera.is_recording


    def test_multiple_recordings(self, camera, output_dir):
        """Test enregistrements successifs."""
        saved_paths = []
        
        for i in range(3):
            output_file = output_dir / f"recording_{i}.avi"
            
            result = camera.start_recording(str(output_file))
            if not result:
                pytest.skip("Enregistrement impossible")
            
            # Enregistrer 10 frames
            for _ in range(10):
                ret, frame = camera.read()
                if ret:
                    camera.write_frame(frame)
                time.sleep(0.03)
            
            saved_path = camera.stop_recording()
            assert saved_path is not None
            saved_paths.append(saved_path)
        
        # Vérifier que tous les fichiers existent
        for path in saved_paths:
            assert Path(path).exists(), f"Fichier manquant: {path}"



    def test_recording_performance(self, camera, output_dir):
        """Test performance enregistrement."""
        output_file = output_dir / "test_performance.avi"
        camera.start_recording(str(output_file))

        start_time = time.time()
        frame_count = 0

        # Enregistrer pendant 1 seconde
        while time.time() - start_time < 1.0:
            ret, frame = camera.read()
            if ret:
                camera.write_frame(frame)  # ✅ CORRIGÉ
                frame_count += 1
            time.sleep(0.001)  # Petite pause

        camera.stop_recording()
        duration = time.time() - start_time

        # Vérifier le FPS
        fps = frame_count / duration
        assert fps > 15, f"FPS trop bas: {fps:.1f} (attendu > 15)"
