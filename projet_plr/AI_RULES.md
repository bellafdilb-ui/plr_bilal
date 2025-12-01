🤖 AI_RULES.md - Guide de Contexte pour IA
# 🎯 AI_RULES.md - Contexte Projet Biomédical

## 📋 **INSTRUCTIONS POUR L'IA ASSISTANT**

> **Ce fichier contient les règles, conventions et contraintes du projet.**  
> **Respecte STRICTEMENT ces directives pour maintenir la cohérence du code.**

---

## 🔒 **RÈGLES ABSOLUES (Non Négociables)**

### **1. Sécurité et Conformité**

```python
# ✅ TOUJOURS
- Anonymiser les données patients (hachage SHA-256)
- Logger toutes les actions sensibles (enregistrement, export)
- Valider les entrées utilisateur (injection, overflow)

# ❌ JAMAIS
- Stocker des identifiants patients en clair
- Utiliser print() en production (seulement logging.info/debug)
- Exposer des chemins absolus dans les logs
Exemple conforme :
import hashlib
import logging

def anonymize_patient_id(patient_id: str) -> str:
    """Anonymise l'ID patient selon RGPD."""
    return hashlib.sha256(patient_id.encode()).hexdigest()[:16]

logging.info(f"Recording started for patient {anonymize_patient_id('P12345')}")

2. Gestion des Ressources
# ✅ OBLIGATOIRE
- Toujours libérer les ressources (caméra, fichiers, connexions DB)
- Utiliser des context managers (with statement)
- Implémenter __enter__/__exit__ pour les classes principales

# ❌ INTERDIT
- Laisser des VideoCapture/VideoWriter ouverts
- Ignorer les exceptions silencieusement (except: pass)
Exemple conforme :
class CameraEngine:
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False  # Propage les exceptions

# Usage
with CameraEngine(camera_id=0) as camera:
    ret, frame = camera.get_frame()
# Libération automatique garantie

3. Tests et Qualité
# ✅ EXIGENCES
- Couverture minimale: 80% par module
- Tests unitaires pour chaque fonction publique
- Tests d'intégration pour les workflows critiques
- Mock les ressources externes (caméra, base de données)

# ❌ INTERDICTIONS
- Modifier le code de production pour "faire passer les tests"
- Tests dépendant de l'ordre d'exécution
- Hard-coding de chemins absolus dans les tests

📐 CONVENTIONS DE CODE
Nomenclature



Élément
Convention
Exemple



Variables
snake_case
frame_count, video_path


Fonctions
snake_case
get_frame(), start_recording()


Classes
PascalCase
CameraEngine, VideoRecorder


Constantes
UPPER_SNAKE_CASE
MAX_FPS, DEFAULT_CODEC


Privées
_prefixe
_validate_camera()


Fichiers
snake_case.py
camera_engine.py, db_manager.py



Structure des Fichiers
"""
Module docstring (obligatoire).

Description détaillée du module, cas d'usage, dépendances.
"""

# 1. Imports standard library
import logging
import time
from datetime import datetime
from pathlib import Path

# 2. Imports third-party
import cv2
import numpy as np

# 3. Imports locaux
from .exceptions import CameraNotFoundError
from .utils import validate_path

# 4. Constantes
DEFAULT_FPS = 30
MAX_RECORDING_DURATION = 3600  # 1 heure

# 5. Classes/Fonctions
class CameraEngine:
    """Docstring de classe."""
    pass

# 6. Point d'entrée (si applicable)
if __name__ == "__main__":
    pass

Docstrings (Style Google)
def start_recording(self, output_path: str, codec: str = "XVID") -> bool:
    """
    Démarre l'enregistrement vidéo.

    Args:
        output_path: Chemin complet du fichier de sortie (ex: "output/video.avi")
        codec: Code à 4 caractères du codec (défaut: "XVID")

    Returns:
        True si l'enregistrement a démarré avec succès, False sinon

    Raises:
        ValueError: Si output_path est vide ou codec invalide
        RuntimeError: Si la caméra n'est pas initialisée
        OSError: Si le dossier de sortie n'existe pas

    Example:
        >>> camera = CameraEngine(camera_id=0)
        >>> camera.start_recording("output/session_001.avi")
        True
        >>> camera.stop_recording()
        {'duration': 12.5, 'frames': 375, ...}

    Note:
        Le codec XVID est recommandé pour compatibilité maximale.
        Le dossier parent doit exister avant l'appel.
    """
    pass

Type Hints (Obligatoires)
from typing import Optional, Tuple, Dict, Any, List
import numpy as np

# ✅ CORRECT
def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
    """Retourne (succès, frame) ou (False, None)."""
    pass

def get_metadata(self) -> Dict[str, Any]:
    """Retourne un dictionnaire de métadonnées."""
    pass

# ❌ INCORRECT (sans types)
def get_frame(self):
    pass

Gestion des Erreurs
# ✅ STRATÉGIE RECOMMANDÉE

# 1. Exceptions personnalisées
class CameraError(Exception):
    """Exception de base pour le module caméra."""
    pass

class CameraNotFoundError(CameraError):
    """Aucune caméra détectée."""
    pass

# 2. Logging systématique
import logging

logger = logging.getLogger(__name__)

def open_camera(camera_id: int) -> cv2.VideoCapture:
    try:
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise CameraNotFoundError(f"Caméra {camera_id} non accessible")
        logger.info(f"Caméra {camera_id} ouverte avec succès")
        return cap
    except Exception as e:
        logger.error(f"Erreur ouverture caméra {camera_id}: {e}")
        raise

# 3. Ressources garanties (finally)
def safe_recording():
    writer = None
    try:
        writer = cv2.VideoWriter(...)
        # enregistrement
    except Exception as e:
        logger.error(f"Erreur enregistrement: {e}")
    finally:
        if writer is not None:
            writer.release()

🎨 PATTERNS DE CONCEPTION À UTILISER
1. Singleton (Caméra unique)
class CameraEngine:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

2. Factory (Création d'objets complexes)
class VideoWriterFactory:
    @staticmethod
    def create_writer(output_path: str, fps: int, resolution: Tuple[int, int], 
                      codec: str = "XVID") -> cv2.VideoWriter:
        """
        Crée un VideoWriter avec validation des paramètres.
        
        Returns:
            VideoWriter configuré et prêt à écrire
        
        Raises:
            ValueError: Si paramètres invalides
        """
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(output_path, fourcc, fps, resolution)
        
        if not writer.isOpened():
            raise RuntimeError(f"Impossible de créer VideoWriter pour {output_path}")
        
        return writer

3. Observer (Notifications UI)
from typing import Callable, List

class CameraEngine:
    def __init__(self):
        self._observers: List[Callable] = []
    
    def attach(self, callback: Callable) -> None:
        """Enregistre un observateur."""
        self._observers.append(callback)
    
    def _notify(self, event: str, data: Any) -> None:
        """Notifie tous les observateurs."""
        for callback in self._observers:
            callback(event, data)
    
    def start_recording(self, output_path: str) -> bool:
        # Logique d'enregistrement
        self._notify("recording_started", {"path": output_path})
        return True

# Usage dans l'UI
def on_recording_event(event: str, data: dict):
    if event == "recording_started":
        print(f"Enregistrement démarré: {data['path']}")

camera = CameraEngine()
camera.attach(on_recording_event)

📊 ÉTAT DU PROJET
✅ MODULES TERMINÉS (Production-Ready)
1. camera_engine.py
# Fonctionnalités
✅ Capture frame unique (get_frame)
✅ Enregistrement vidéo (start/stop_recording)
✅ Gestion multi-sources (USB, fichier, test)
✅ Métadonnées JSON automatiques
✅ Libération ressources garantie

# Tests
✅ 14/14 tests unitaires passés
✅ Couverture: 85%
✅ Scénarios de régression validés

# Performance
✅ 30 FPS stables en capture
✅ <50ms de latence par frame
✅ Gestion correcte de 1000+ frames

🚧 MODULES EN COURS
2. Interface UI (PyQt6) - Priorité 0
# À implémenter
☐ main_window.py (fenêtre principale)
   ├─ Boutons Start/Stop Recording
   ├─ Affichage temps réel (QLabel pour frames)
   ├─ Barre de progression enregistrement
   └─ Liste des vidéos enregistrées

☐ video_player.py (lecteur intégré)
   ├─ Playback avec contrôles (play/pause/seek)
   ├─ Affichage métadonnées
   └─ Export frame unique

☐ settings_dialog.py (configuration)
   ├─ Sélection caméra (dropdown)
   ├─ Résolution (640x480, 1280x720, 1920x1080)
   ├─ FPS (15, 30, 60)
   └─ Codec (XVID, H264)

# Structure fichier
ui/
├── __init__.py
├── main_window.py        # QMainWindow
├── widgets/
│   ├── video_widget.py   # QWidget custom pour affichage
│   └── control_panel.py  # Panneau de contrôle
└── resources/
    ├── icons/            # Boutons play/stop
    └── styles.qss        # Feuille de style Qt
Exemple de code attendu :
from PyQt6.QtWidgets import QMainWindow, QPushButton, QLabel
from PyQt6.QtCore import QThread, pyqtSignal

class CameraThread(QThread):
    frame_ready = pyqtSignal(object)  # np.ndarray
    
    def run(self):
        camera = CameraEngine(camera_id=0)
        while self.isRunning():
            ret, frame = camera.get_frame()
            if ret:
                self.frame_ready.emit(frame)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.camera_thread = CameraThread()
        self.camera_thread.frame_ready.connect(self.update_frame)
        self.camera_thread.start()

3. Base de Données (SQLite) - Priorité 1
-- Schema attendu (database/schema.sql)

CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    filepath TEXT NOT NULL,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_seconds REAL,
    frame_count INTEGER,
    fps INTEGER,
    resolution TEXT,  -- "1280x720"
    codec TEXT,
    filesize_bytes INTEGER,
    patient_id_hash TEXT,  -- Anonymisé
    session_notes TEXT
);

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER,
    timestamp_ms INTEGER,  -- Position dans la vidéo
    event_type TEXT,  -- "object_detected", "anomaly", etc.
    description TEXT,
    metadata JSON,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE INDEX idx_videos_date ON videos(recorded_at);
CREATE INDEX idx_events_video ON events(video_id);
Manager attendu :
# database/db_manager.py

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any

class DatabaseManager:
    def __init__(self, db_path: str = "data/biomedical.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_schema()
    
    def add_video(self, metadata: Dict[str, Any]) -> int:
        """
        Ajoute une vidéo à la base.
        
        Args:
            metadata: Dictionnaire de métadonnées (filename, duration, etc.)
        
        Returns:
            ID de la vidéo insérée
        """
        pass
    
    def get_videos(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère les N dernières vidéos."""
        pass
    
    def search_videos(self, patient_id_hash: Optional[str] = None,
                      date_from: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recherche avancée."""
        pass

📝 TODO LIST (Prochaines Étapes)
Phase 1: Interface Utilisateur (2 semaines)
☐ Créer main_window.py avec layout de base
   ├─ QVBoxLayout principal
   ├─ QLabel pour affichage vidéo
   └─ QHBoxLayout pour boutons

☐ Implémenter CameraThread (QThread)
   ├─ Signal frame_ready pour MAJ UI
   └─ Gestion démarrage/arrêt propre

☐ Ajouter contrôles enregistrement
   ├─ QPushButton "Start Recording" (vert)
   ├─ QPushButton "Stop Recording" (rouge)
   └─ QLabel pour timer (00:00:00)

☐ Implémenter lecteur vidéo basique
   └─ Charger .avi depuis output/

☐ Tests d'intégration UI
   └─ pytest-qt pour tester les widgets
Phase 2: Persistance Données (1 semaine)
☐ Créer schema.sql (tables videos + events)
☐ Implémenter DatabaseManager
   ├─ add_video()
   ├─ get_videos()
   └─ search_videos()
☐ Intégrer sauvegarde automatique post-enregistrement
☐ Tests unitaires pour CRUD
Phase 3: Détection Objets (3 semaines)
☐ Installer YOLOv8 (ultralytics)
☐ Créer ObjectDetector
   ├─ load_model()
   ├─ detect_objects(frame)
   └─ annotate_frame()
☐ Intégrer détection temps réel dans CameraThread
☐ Logger événements dans table events
☐ Tests avec vidéos de référence

⚠️ DETTE TECHNIQUE CONNUE
1. Gestion de la mémoire (CameraEngine)
# ⚠️ PROBLÈME ACTUEL
# La vidéo de test charge tout en mémoire (self.test_frames)
# Impact: ~500MB pour une vidéo de 10 secondes à 1080p

# ✅ SOLUTION PRÉVUE (Phase 2)
# Utiliser un générateur lazy-loading
def _load_test_frames_lazy(video_path: str):
    cap = cv2.VideoCapture(video_path)
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop
            continue
        yield frame

2. Thread-safety (VideoWriter)
# ⚠️ RISQUE
# Écriture simultanée depuis UI + caméra thread
# Symptôme: Corruption fichier vidéo ou crash

# ✅ SOLUTION TEMPORAIRE
# Verrou simple (déjà implémenté)
self._recording_lock = threading.Lock()

# ✅ SOLUTION FINALE (Phase 3)
# Queue de frames + worker thread dédié
from queue import Queue

self.frame_queue = Queue(maxsize=100)
self.writer_thread = WriterThread(self.frame_queue)

3. Gestion des erreurs (caméra déconnectée)
# ⚠️ COMPORTEMENT ACTUEL
# Si caméra débranchée pendant enregistrement → Exception non gérée

# ✅ CORRECTIF PRÉVU (Phase 1)
def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
    try:
        ret, frame = self.cap.read()
        if not ret:
            logger.warning("Perte signal caméra, tentative reconnexion...")
            self._reconnect_camera()
        return ret, frame
    except Exception as e:
        logger.error(f"Erreur critique caméra: {e}")
        return False, None

4. Codec H.264 (export MP4)
# ⚠️ LIMITATION
# Windows nécessite codec pack externe pour H.264
# XVID fonctionne partout mais fichiers plus volumineux

# ✅ WORKAROUND ACTUEL
# Utiliser XVID par défaut

# ✅ SOLUTION FUTURE (Phase 2)
# Post-processing avec FFmpeg
import subprocess

def convert_to_mp4(avi_path: str) -> str:
    """Convertit AVI en MP4 avec FFmpeg."""
    mp4_path = avi_path.replace(".avi", ".mp4")
    subprocess.run([
        "ffmpeg", "-i", avi_path,
        "-c:v", "libx264", "-preset", "fast",
        "-crf", "23", mp4_path
    ])
    return mp4_path

🔍 DIRECTIVES POUR GÉNÉRATION DE CODE
Quand tu génères du code, applique :
1. Structure de fonction complète
def function_name(arg1: Type1, arg2: Type2 = default) -> ReturnType:
    """
    [Docstring Google Style - OBLIGATOIRE]
    """
    # 1. Validation des entrées
    if not isinstance(arg1, Type1):
        raise TypeError(f"arg1 doit être {Type1}, reçu {type(arg1)}")
    
    # 2. Logging (si fonction critique)
    logger.debug(f"Appel function_name avec arg1={arg1}, arg2={arg2}")
    
    # 3. Logique métier
    try:
        result = process(arg1, arg2)
    except Exception as e:
        logger.error(f"Erreur dans function_name: {e}")
        raise
    
    # 4. Retour + validation
    assert isinstance(result, ReturnType), "Type retour invalide"
    return result

2. Template de classe
class ClassName:
    """
    Docstring de classe.
    
    Attributes:
        attr1: Description
        attr2: Description
    
    Example:
        >>> obj = ClassName(param=value)
        >>> obj.method()
    """
    
    def __init__(self, param: Type):
        """Initialise la classe."""
        self.param = param
        self._private_attr = None
        logger.info(f"ClassName initialisée avec param={param}")
    
    def public_method(self) -> ReturnType:
        """Méthode publique."""
        pass
    
    def _private_method(self) -> None:
        """Méthode privée (usage interne uniquement)."""
        pass
    
    def __enter__(self):
        """Context manager: entrée."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: sortie."""
        self.cleanup()
        return False
    
    def __repr__(self) -> str:
        """Représentation développeur."""
        return f"ClassName(param={self.param!r})"

3. Template de test
import pytest
from unittest.mock import Mock, patch
from module import ClassName

class TestClassName:
    """Tests pour ClassName."""
    
    @pytest.fixture
    def instance(self):
        """Fixture: instance réutilisable."""
        return ClassName(param="test")
    
    def test_init_success(self, instance):
        """Test initialisation normale."""
        assert instance.param == "test"
        assert instance._private_attr is None
    
    def test_init_invalid_type(self):
        """Test initialisation avec type invalide."""
        with pytest.raises(TypeError):
            ClassName(param=123)  # Attendu: str
    
    @patch('module.external_dependency')
    def test_method_with_mock(self, mock_external, instance):
        """Test avec dépendance mockée."""
        mock_external.return_value = "mocked_value"
        result = instance.public_method()
        assert result == "expected"
        mock_external.assert_called_once()
    
    def test_context_manager(self):
        """Test utilisation avec 'with'."""
        with ClassName(param="test") as obj:
            assert obj.param == "test"
        # Vérifier cleanup appelé

🚨 ERREURS COURANTES À ÉVITER
1. Oublier la libération des ressources
# ❌ MAUVAIS
def capture_video():
    cap = cv2.VideoCapture(0)
    frame = cap.read()
    return frame
    # cap jamais libéré → fuite mémoire

# ✅ BON
def capture_video():
    cap = cv2.VideoCapture(0)
    try:
        frame = cap.read()
        return frame
    finally:
        cap.release()

2. Modifier des variables mutables par défaut
# ❌ MAUVAIS
def add_metadata(data, metadata={}):
    metadata['timestamp'] = time.time()
    return metadata
# Le dict est partagé entre tous les appels !

# ✅ BON
def add_metadata(data, metadata=None):
    if metadata is None:
        metadata = {}
    metadata['timestamp'] = time.time()
    return metadata

3. Ignorer les exceptions silencieusement
# ❌ MAUVAIS
try:
    risky_operation()
except:
    pass  # Erreur masquée

# ✅ BON
try:
    risky_operation()
except SpecificException as e:
    logger.error(f"Erreur attendue: {e}")
    # Gestion appropriée
except Exception as e:
    logger.critical(f"Erreur inattendue: {e}")
    raise  # Re-lever pour investigation

4. Hardcoder des chemins absolus
# ❌ MAUVAIS
VIDEO_PATH = "C:\\Users\\John\\Desktop\\video.avi"

# ✅ BON
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"
VIDEO_PATH = OUTPUT_DIR / "video.avi"

📚 RESSOURCES DE RÉFÉRENCE
Documentation Externe



Sujet
Source
Usage



OpenCV
https://docs.opencv.org/4.x/
API caméra, codecs, traitement


PyQt6
https://doc.qt.io/qtforpython-6/
Widgets, threads, signals


YOLO
https://docs.ultralytics.com/
Détection objets temps réel


SQLite
https://www.sqlite.org/docs.html
Requêtes SQL, index


pytest
https://docs.pytest.org/en/stable/
Fixtures, mocking, paramétrage



Code de Référence (Patterns)
# Disponible dans le dépôt sous examples/

examples/
├── camera_basic.py          # Capture simple
├── recording_with_ui.py     # Intégration PyQt6
├── yolo_detection.py        # Détection objets
└── database_crud.py         # Opérations SQLite

🎯 CHECKLIST DE VALIDATION AVANT COMMIT
# 1. Tests passent
pytest tests/ -v

# 2. Couverture acceptable
pytest --cov=. --cov-report=term-missing
# Vérifier: Couverture >= 80%

# 3. Linting (à implémenter)
# flake8 .
# black --check .

# 4. Type checking (à implémenter)
# mypy .

# 5. Pas de secrets/données sensibles
git diff | grep -i "password\|api_key\|secret"

# 6. Documentation à jour
# README.md reflète les nouvelles fonctionnalités ?

🔄 WORKFLOW DE DÉVELOPPEMENT
Pour une nouvelle fonctionnalité :
# 1. Créer une branche
git checkout -b feature/nom-fonctionnalite

# 2. Écrire les tests AVANT le code (TDD)
# Créer tests/test_nouvelle_fonctionnalite.py

# 3. Implémenter la fonctionnalité
# Créer module.py

# 4. Vérifier que les tests passent
pytest tests/test_nouvelle_fonctionnalite.py -v

# 5. Vérifier l'intégration
pytest tests/ -v

# 6. Documenter
# Mettre à jour README.md et AI_RULES.md

# 7. Commit atomique
git add .
git commit -m "feat: Ajoute détection YOLO avec modèle YOLOv8n

- Classe ObjectDetector avec load_model() et detect()
- Tests avec 3 vidéos de référence
- Documentation API dans docs/detection.md

Closes #42"

# 8. Push
git push origin feature/nom-fonctionnalite

🆘 AIDE-MÉMOIRE COMMANDES
Tests
# Tous les tests
pytest tests/ -v

# Test spécifique
pytest tests/test_camera_engine.py::TestCameraEngine::test_get_frame -v

# Avec couverture
pytest --cov=camera_engine --cov-report=html

# Mode watch (relance auto)
pytest-watch tests/
Git
# Statut détaillé
git status
git log --oneline --graph --all

# Annuler dernier commit (garder les changements)
git reset --soft HEAD~1

# Synchroniser avec main
git checkout main
git pull origin main
git checkout feature/ma-branche
git rebase main
Environnement
# Réinstaller dépendances
pip install -r requirements.txt --upgrade

# Nettoyer cache Python
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

📞 CONTACT ET SUPPORT
Pour l'IA Assistant :

Si ambiguïté dans le code à générer :

Demander clarification sur le cas d'usage précis
Proposer 2-3 alternatives avec pros/cons
Inclure des exemples d'utilisation



Si fonctionnalité manquante dans ce guide :

Signaler l'omission
Proposer un ajout à AI_RULES.md
Documenter la décision dans le commit



🔐 SÉCURITÉ
Données Sensibles Interdites dans le Dépôt
# Déjà dans .gitignore, mais rappel :

# Données patients
*.dcm              # Fichiers DICOM
patient_data/      # Dossier données réelles
*.csv              # Exports Excel avec données

# Credentials
.env
config.ini
secrets.json

# Logs en production
logs/*.log
*.log

# Vidéos/images réelles
output/*.avi
output/*.mp4
data/*.avi

VERSION: 1.0.0DERNIÈRE MISE À JOUR: 2025-01-XXMAINTENEUR: [Nom du développeur]

🎯 UTILISATION PAR L'IA
Exemple de prompt optimisé :
CONTEXTE:
[Coller le contenu de AI_RULES.md - Sections "Règles Absolues" + "Conventions de Code"]

ÉTAT ACTUEL:
[Coller section "État du Projet"]

DEMANDE:
Crée la classe MainWindow (PyQt6) avec :
- QLabel pour affichage vidéo temps réel
- Boutons Start/Stop Recording
- Timer d'enregistrement (QLabel au format HH:MM:SS)

Respecte:
- Docstrings Google Style
- Type hints obligatoires
- Tests pytest avec pytest-qt
- Gestion thread-safe (QThread pour caméra)
Résultat attendu :

Code production-ready avec docstrings complètes
Tests unitaires inclus
Gestion des erreurs robuste
Respect des conventions du projet



---

# 🎯 **FICHIER CONTEXT.md (Version Simplifiée)**

> **Alternative : Version courte pour IA avec contexte limité**

```markdown
# CONTEXT.md - Résumé Projet Biomédical

## 🎯 Projet
Application Python de capture/analyse vidéo médicale

## 📐 Conventions Code
- Variables: `snake_case`
- Classes: `PascalCase`
- Type hints obligatoires
- Docstrings Google Style
- Tests pytest (couverture 80%+)

## ✅ Terminé
- `camera_engine.py`: Capture + Enregistrement (14/14 tests)

## 🚧 En Cours
1. Interface PyQt6 (main_window.py)
2. Base SQLite (db_manager.py)
3. Détection YOLO (object_detector.py)

## ⚠️ Dette Technique
- Mémoire: Vidéo test charge tout (→ lazy loading)
- Thread: VideoWriter non thread-safe (→ Queue)
- Codec: H.264 nécessite FFmpeg (→ post-processing)

## 🚨 Interdictions
- ❌ print() en production (utiliser logging)
- ❌ Chemins absolus hardcodés
- ❌ Données patients non anonymisées
- ❌ Exceptions silencieuses (except: pass)

## 📋 Template Fonction
```python
def func(arg: Type) -> ReturnType:
    """Docstring Google Style."""
    # 1. Validation
    # 2. Logging
    # 3. Logique
    # 4. Retour
    pass
Version: 1.0.0

---

## 🚀 **PROCHAINES ÉTAPES**

**Ces deux fichiers sont prêts à être intégrés au dépôt :**

```bash
# Créer les fichiers
echo "[CONTENU AI_RULES.md]" > AI_RULES.md
echo "[CONTENU CONTEXT.md]" > CONTEXT.md

# Ajouter au dépôt
git add AI_RULES.md CONTEXT.md
git commit -m "docs: Ajoute règles IA et contexte projet

- AI_RULES.md: Guide complet pour assistant IA (conventions, dette technique, templates)
- CONTEXT.md: Version résumée pour prompt rapides
- Facilite collaboration multi-développeurs + IA"

git push origin main