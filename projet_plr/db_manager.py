"""
db_manager.py
=============
Gestionnaire de base de données SQLite pour l'application PLR (Version Vétérinaire).

Responsabilités :
- Gestion des patients animaux (Création, Recherche, Historique)
- Stockage des examens
- Sécurité (Hashing)

Schéma relationnel :
- PATIENTS : Identité de l'animal (Nom, Tatouage, Espèce, Race...)
- EXAMS    : Métadonnées des tests réalisés
"""

import sqlite3
import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Gestionnaire centralisé de la base de données SQLite."""
    
    def __init__(self, db_path: str = "data/vet_data.db"):
        self.db_path = Path(db_path)
        self._ensure_db_exists()
        
    def _ensure_db_exists(self):
        """Crée l'arborescence et le schéma si inexistants."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Table PATIENTS (Adaptée Vétérinaire)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tattoo_id TEXT NOT NULL UNIQUE,    -- Identification (Tatouage/Puce)
                name TEXT NOT NULL,                -- Nom de l'animal
                species TEXT NOT NULL,             -- Espèce (Chien, Chat...)
                breed TEXT,                        -- Race
                birth_date TEXT,                   -- Format YYYY-MM-DD
                gender TEXT,                       -- M/F
                owner_name TEXT,                   -- Nom du propriétaire (optionnel)
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                anonymized_hash TEXT
            )
        """)
        
        # 2. Table EXAMS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                exam_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                exam_type TEXT DEFAULT 'PLR_STANDARD',
                csv_path TEXT,
                video_path TEXT,
                results_json TEXT,
                comments TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Base de données vétérinaire initialisée : {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_hash(self, unique_id: str) -> str:
        """Génère un hash SHA-256 pour l'anonymisation."""
        salt = "VET_APP_v1"
        data = f"{unique_id}{salt}"
        return hashlib.sha256(data.encode()).hexdigest()

    # ===========================
    # GESTION PATIENTS (ANIMAUX)
    # ===========================

    def add_patient(self, tattoo_id: str, name: str, species: str, 
                   breed: str = "", gender: str = "", birth_date: str = "", 
                   owner_name: str = "", notes: str = "") -> int:
        """Ajoute un nouveau patient animal."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            anon_hash = self._generate_hash(tattoo_id)
            
            cursor.execute("""
                INSERT INTO patients (tattoo_id, name, species, breed, gender, birth_date, owner_name, notes, anonymized_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tattoo_id, name.capitalize(), species, breed, gender, birth_date, owner_name, notes, anon_hash))
            
            patient_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Animal créé : {name} ({species}) - ID: {patient_id}")
            return patient_id
            
        except sqlite3.IntegrityError:
            logger.warning(f"Tatouage/Puce déjà existant : {tattoo_id}")
            return -1
        except Exception as e:
            logger.error(f"Erreur ajout patient : {e}")
            return -1
        finally:
            conn.close()

    def search_patients(self, query: str = "") -> List[Dict[str, Any]]:
        """Recherche par nom, tatouage ou race."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT * FROM patients 
            WHERE name LIKE ? OR tattoo_id LIKE ? OR breed LIKE ?
            ORDER BY created_at DESC
        """
        wildcard = f"%{query}%"
        cursor.execute(sql, (wildcard, wildcard, wildcard))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_patient(self, patient_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ===========================
    # GESTION EXAMENS
    # ===========================

    def save_exam(self, patient_id: int, csv_path: str, video_path: str = "", 
                 results: Dict = None, comments: str = "") -> int:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            results_json = json.dumps(results) if results else "{}"
            
            cursor.execute("""
                INSERT INTO exams (patient_id, csv_path, video_path, results_json, comments)
                VALUES (?, ?, ?, ?, ?)
            """, (patient_id, str(csv_path), str(video_path), results_json, comments))
            
            exam_id = cursor.lastrowid
            conn.commit()
            return exam_id
        except Exception as e:
            logger.error(f"Erreur sauvegarde examen : {e}")
            return -1
        finally:
            conn.close()

    def get_patient_history(self, patient_id: int) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams WHERE patient_id = ? ORDER BY exam_date DESC", (patient_id,))
        history = []
        for row in cursor.fetchall():
            exam = dict(row)
            if exam['results_json']:
                try:
                    exam['results_data'] = json.loads(exam['results_json'])
                except:
                    exam['results_data'] = {}
            history.append(exam)
        conn.close()
        return history