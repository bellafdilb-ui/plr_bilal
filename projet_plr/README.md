# 🏥 Application de Capture et Analyse Vidéo Biomédicale

## 📋 **Vue d'ensemble**

Application Python professionnelle destinée aux établissements de santé pour la **capture vidéo en temps réel**, l'**enregistrement sécurisé** et l'**analyse d'images médicales** via une interface graphique intuitive.

---

## 🎯 **Objectifs du Projet**

### **Fonctionnalités Principales**

1. **Capture Vidéo Temps Réel**
   - Gestion multi-sources (caméras USB, fichiers vidéo, flux RTSP)
   - Acquisition d'images médicales à haute fréquence (30-60 FPS)
   - Prévisualisation en direct pour le personnel médical

2. **Enregistrement Sécurisé**
   - Sauvegarde automatique des flux vidéo (format AVI/MP4)
   - Métadonnées enrichies (timestamp, résolution, FPS, codec)
   - Traçabilité complète pour conformité réglementaire (RGPD/HIPAA)

3. **Analyse d'Images**
   - Détection d'objets/événements d'intérêt médical
   - Annotation automatique des frames critiques
   - Export des données pour études cliniques

4. **Interface Professionnelle**
   - Contrôles intuitifs pour personnel non-technique
   - Gestion des sessions d'enregistrement
   - Visualisation des historiques vidéo

---

## 🛠️ **Stack Technique**

### **Langages et Versions**

| Composant | Version | Justification |
|-----------|---------|---------------|
| **Python** | `3.10+` | Compatibilité POO avancée, type hints natifs |
| **Git** | `2.40+` | Gestion de version multi-PC |

### **Frameworks et Librairies**

#### **Traitement Vidéo**
```python
opencv-python==4.9.0.80     # Capture caméra, encodage vidéo, traitement d'image
numpy==1.26.4               # Manipulation matricielle des frames (arrays)


PyQt6==6.6.1                # UI professionnelle cross-platform
pyqtgraph==0.13.3           # Visualisation temps réel (graphiques, histogrammes)
sqlite3                     # Base de données locale (métadonnées vidéos)
Pillow==10.2.0             # Génération de miniatures vidéo
pytest==8.0.0              # Framework de tests unitaires
pytest-cov==4.1.0          # Couverture de code
pytest-mock==3.12.0        # Mocking pour tests isolés
cryptography==42.0.0       # Chiffrement des données sensibles
hashlib (stdlib)           # Anonymisation des identifiants patients


FLUX de données
┌─────────────────────────────────────────────────────────────────┐
│                    CYCLE DE VIE D'UNE CAPTURE                    │
└─────────────────────────────────────────────────────────────────┘

1️⃣ ACQUISITION
   ┌──────────────┐
   │   Caméra USB │  ──┐
   │ Fichier vidéo│    │
   │   Flux RTSP  │  ──┤
   └──────────────┘    │
                       ▼
              ┌─────────────────┐
              │ CameraEngine    │
              │  - cv2.VideoCapture()
              │  - Frame buffer │
              └─────────────────┘
                       │
                       ▼
2️⃣ TRAITEMENT (optionnel)
              ┌─────────────────┐
              │ ObjectDetector  │
              │  - YOLO/Cascade │
              │  - Annotations  │
              └─────────────────┘
                       │
                       ▼
3️⃣ ENREGISTREMENT
              ┌─────────────────┐
              │ cv2.VideoWriter │
              │  - Codec: XVID  │
              │  - FPS: 30      │
              └─────────────────┘
                       │
                       ├──────────────────┐
                       ▼                  ▼
              ┌─────────────┐    ┌────────────────┐
              │ video.avi   │    │ metadata.json  │
              │ (frames)    │    │ - timestamp    │
              │             │    │ - resolution   │
              └─────────────┘    │ - duration     │
                                 │ - events       │
                                 └────────────────┘
                       │
                       ▼
4️⃣ STOCKAGE
              ┌─────────────────┐
              │   SQLite DB     │
              │ ┌─────────────┐ │
              │ │ id  | path  │ │
              │ │ date| codec │ │
              │ │ fps | meta  │ │
              │ └─────────────┘ │
              └─────────────────┘
                       │
                       ▼
5️⃣ VISUALISATION
              ┌─────────────────┐
              │   Interface UI  │
              │  - Liste vidéos │
              │  - Lecteur      │
              │  - Export       │
              └─────────────────┘
