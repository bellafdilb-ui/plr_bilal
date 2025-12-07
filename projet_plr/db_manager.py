"""
db_manager.py
=============
Gestionnaire de base de données SQLite (Version Vétérinaire + Latéralité).
"""

import sqlite3
import logging
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "data/vet_data.db"):
        self.db_path = Path(db_path)
        self._ensure_db_exists()
        
    def _ensure_db_exists(self):
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tattoo_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                species TEXT NOT NULL,
                breed TEXT,
                birth_date TEXT,
                gender TEXT,
                owner_name TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                anonymized_hash TEXT
            )
        """)
        
        # AJOUT COLONNE laterality
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                exam_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                exam_type TEXT DEFAULT 'PLR_STANDARD',
                laterality TEXT,  -- 'OD' (Droit) ou 'OG' (Gauche)
                csv_path TEXT,
                video_path TEXT,
                results_json TEXT,
                comments TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_hash(self, unique_id: str) -> str:
        salt = "VET_APP_v1"
        data = f"{unique_id}{salt}"
        return hashlib.sha256(data.encode()).hexdigest()

    # --- PATIENTS ---
    def add_patient(self, tattoo_id: str, name: str, species: str, 
                   breed: str = "", gender: str = "", birth_date: str = "", 
                   owner_name: str = "", notes: str = "") -> int:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            anon_hash = self._generate_hash(tattoo_id)
            cursor.execute("""
                INSERT INTO patients (tattoo_id, name, species, breed, gender, birth_date, owner_name, notes, anonymized_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tattoo_id, name.capitalize(), species, breed, gender, birth_date, owner_name, notes, anon_hash))
            pid = cursor.lastrowid
            conn.commit()
            return pid
        except Exception as e:
            logger.error(f"Erreur ajout: {e}")
            return -1
        finally:
            conn.close()

    def update_patient(self, patient_id: int, name: str, species: str, breed: str, 
                      gender: str, birth_date: str, notes: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE patients 
                SET name=?, species=?, breed=?, gender=?, birth_date=?, notes=?
                WHERE id=?
            """, (name, species, breed, gender, birth_date, notes, patient_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erreur update: {e}")
            return False
        finally:
            conn.close()

    def delete_patient(self, patient_id: int) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM patients WHERE id=?", (patient_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erreur delete: {e}")
            return False
        finally:
            conn.close()

    def search_patients(self, query: str = "") -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM patients WHERE name LIKE ? OR tattoo_id LIKE ? OR breed LIKE ? ORDER BY created_at DESC"
        wildcard = f"%{query}%"
        cursor.execute(sql, (wildcard, wildcard, wildcard))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    # --- EXAMENS ---
    # MISE À JOUR SIGNATURE : Ajout laterality
    def save_exam(self, patient_id: int, laterality: str, csv_path: str, video_path: str = "", results: Dict = None, comments: str = "") -> int:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            r_json = json.dumps(results) if results else "{}"
            cursor.execute("""
                INSERT INTO exams (patient_id, laterality, csv_path, video_path, results_json, comments)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (patient_id, laterality, str(csv_path), str(video_path), r_json, comments))
            eid = cursor.lastrowid
            conn.commit()
            return eid
        except Exception as e:
            logger.error(f"Erreur save exam: {e}")
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
                try: exam['results_data'] = json.loads(exam['results_json'])
                except: exam['results_data'] = {}
            history.append(exam)
        conn.close()
        return history