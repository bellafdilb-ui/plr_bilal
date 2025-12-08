"""
db_manager.py
=============
Gestionnaire BDD V2 (Support Clinique & Macros).
"""

import sqlite3
import logging
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any

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
        
        # Tables existantes
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                exam_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                exam_type TEXT DEFAULT 'PLR_STANDARD',
                laterality TEXT,
                csv_path TEXT,
                video_path TEXT,
                results_json TEXT,
                comments TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
            )
        """)

        # --- NOUVELLES TABLES ---
        
        # 1. Infos Clinique (Une seule ligne prévue)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clinic_info (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                address TEXT,
                phone TEXT,
                email TEXT,
                doctor_name TEXT,
                logo_path TEXT
            )
        """)
        
        # 2. Macros (Commentaires prédéfinis)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS macros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT
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
        return hashlib.sha256(f"{unique_id}{salt}".encode()).hexdigest()

    # --- PATIENTS & EXAMS (Méthodes inchangées, je les résume pour gain de place) ---
    def add_patient(self, tattoo_id, name, species, breed="", gender="", birth_date="", owner_name="", notes=""):
        try:
            conn = self._get_connection(); cursor = conn.cursor()
            h = self._generate_hash(tattoo_id)
            cursor.execute("INSERT INTO patients (tattoo_id, name, species, breed, gender, birth_date, owner_name, notes, anonymized_hash) VALUES (?,?,?,?,?,?,?,?,?)", 
                           (tattoo_id, name.capitalize(), species, breed, gender, birth_date, owner_name, notes, h))
            pid = cursor.lastrowid; conn.commit(); conn.close(); return pid
        except: return -1

    def update_patient(self, pid, name, species, breed, gender, birth_date, notes):
        try:
            conn = self._get_connection(); cursor = conn.cursor()
            cursor.execute("UPDATE patients SET name=?, species=?, breed=?, gender=?, birth_date=?, notes=? WHERE id=?", 
                           (name, species, breed, gender, birth_date, notes, pid))
            conn.commit(); conn.close(); return True
        except: return False

    def delete_patient(self, pid):
        try:
            conn = self._get_connection(); cursor = conn.cursor()
            cursor.execute("DELETE FROM patients WHERE id=?", (pid,)); conn.commit(); conn.close(); return True
        except: return False

    def search_patients(self, query=""):
        conn = self._get_connection(); cursor = conn.cursor()
        sql = "SELECT * FROM patients WHERE name LIKE ? OR tattoo_id LIKE ? ORDER BY created_at DESC"
        cursor.execute(sql, (f"%{query}%", f"%{query}%")); res = [dict(r) for r in cursor.fetchall()]; conn.close(); return res

    def save_exam(self, pid, lat, csv, vid="", results=None, comments=""):
        try:
            conn = self._get_connection(); cursor = conn.cursor()
            js = json.dumps(results) if results else "{}"
            cursor.execute("INSERT INTO exams (patient_id, laterality, csv_path, video_path, results_json, comments) VALUES (?,?,?,?,?,?)", 
                           (pid, lat, str(csv), str(vid), js, comments))
            eid = cursor.lastrowid; conn.commit(); conn.close(); return eid
        except: return -1

    def get_patient_history(self, pid):
        conn = self._get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams WHERE patient_id=? ORDER BY exam_date DESC", (pid,))
        hist = []
        for r in cursor.fetchall():
            d = dict(r)
            try: d['results_data'] = json.loads(d['results_json'])
            except: d['results_data'] = {}
            hist.append(d)
        conn.close(); return hist

    def update_exam_comment(self, exam_id: int, new_comment: str) -> bool:
            """Met à jour le commentaire d'un examen existant."""
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE exams SET comments = ? WHERE id = ?", (new_comment, exam_id))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Erreur update comment: {e}")
                return False


    # --- GESTION CLINIQUE & MACROS ---

    def set_clinic_info(self, name, addr, phone, email, doc, logo):
        conn = self._get_connection(); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO clinic_info (id, name, address, phone, email, doctor_name, logo_path) VALUES (1, ?, ?, ?, ?, ?, ?)",
                       (name, addr, phone, email, doc, logo))
        conn.commit(); conn.close()

    def get_clinic_info(self):
        conn = self._get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM clinic_info WHERE id=1")
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {}

    def add_macro(self, title, content):
        conn = self._get_connection(); cursor = conn.cursor()
        cursor.execute("INSERT INTO macros (title, content) VALUES (?, ?)", (title, content))
        conn.commit(); conn.close()

    def delete_macro(self, mid):
        conn = self._get_connection(); cursor = conn.cursor()
        cursor.execute("DELETE FROM macros WHERE id=?", (mid,))
        conn.commit(); conn.close()

    def get_macros(self):
        conn = self._get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM macros")
        res = [dict(r) for r in cursor.fetchall()]
        conn.close(); return res