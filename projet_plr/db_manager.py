"""
db_manager.py
=============
Gestionnaire de Base de Données SQLite pour l'application PLR Vet.
Gère les patients, les examens, les informations cliniques et les macros.
"""

import sqlite3
import logging
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Classe façade pour toutes les interactions avec la base de données SQLite.
    """

    def __init__(self, db_path: str = "data/vet_data.db"):
        self.db_path = Path(db_path)
        self._ensure_db_exists()
        
    def _ensure_db_exists(self):
        """Crée les tables nécessaires si la base de données n'existe pas."""
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
        
        # --- MODIFICATION ICI : PLUS DE TITRE ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS macros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        """Génère un hash anonymisé pour l'export de données."""
        salt = "VET_APP_v1"
        return hashlib.sha256(f"{unique_id}{salt}".encode()).hexdigest()

    # --- PATIENTS & EXAMS ---
    def add_patient(self, tattoo_id: str, name: str, species: str, 
                    breed: str = "", gender: str = "", birth_date: str = "", 
                    owner_name: str = "", notes: str = "") -> int:
        """
        Ajoute un nouveau patient.

        Args:
            tattoo_id (str): Identifiant unique (Puce ou Tatouage).
            name (str): Nom de l'animal.
            species (str): Espèce (ex: 'Chien', 'Chat').
            breed (str, optional): Race. Defaults to "".
            gender (str, optional): Sexe ('M'/'F'). Defaults to "".
            birth_date (str, optional): Date YYYY-MM-DD. Defaults to "".
            owner_name (str, optional): Nom du propriétaire. Defaults to "".
            notes (str, optional): Observations. Defaults to "".

        Returns:
            int: L'ID du patient créé, ou -1 en cas d'erreur (ex: ID déjà existant).
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            h = self._generate_hash(tattoo_id)
            cursor.execute("INSERT INTO patients (tattoo_id, name, species, breed, gender, birth_date, owner_name, notes, anonymized_hash) VALUES (?,?,?,?,?,?,?,?,?)", 
                           (tattoo_id, name.capitalize(), species, breed, gender, birth_date, owner_name, notes, h))
            pid = cursor.lastrowid
            conn.commit()
            conn.close()
            return pid
        except Exception as e:
            logger.error(f"Erreur add_patient: {e}")
            return -1

    def update_patient(self, pid: int, name: str, species: str, breed: str, 
                       gender: str, birth_date: str, notes: str) -> bool:
        """Met à jour les informations d'un patient existant."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE patients SET name=?, species=?, breed=?, gender=?, birth_date=?, notes=? WHERE id=?", 
                           (name, species, breed, gender, birth_date, notes, pid))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Erreur update_patient: {e}")
            return False

    def delete_patient(self, pid: int) -> bool:
        """Supprime un patient et ses examens associés (CASCADE)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM patients WHERE id=?", (pid,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Erreur delete_patient: {e}")
            return False

    def search_patients(self, query: str = "") -> List[Dict[str, Any]]:
        """Recherche des patients par nom ou identifiant (tatouage/puce)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM patients WHERE name LIKE ? OR tattoo_id LIKE ? ORDER BY created_at DESC"
        cursor.execute(sql, (f"%{query}%", f"%{query}%"))
        res = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return res

    def save_exam(self, pid: int, lat: str, csv: str, vid: str = "", 
                  results: Optional[Dict] = None, comments: str = "") -> int:
        """
        Enregistre un nouvel examen PLR.

        Args:
            pid (int): ID du patient.
            lat (str): Latéralité ('OD' ou 'OG').
            csv (str): Chemin du fichier CSV brut.
            vid (str, optional): Chemin de la vidéo (si enregistrée).
            results (dict, optional): Dictionnaire des métriques calculées.
            comments (str, optional): Commentaires vétérinaires.

        Returns:
            int: ID de l'examen créé ou -1 si erreur.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            js = json.dumps(results) if results else "{}"
            cursor.execute("INSERT INTO exams (patient_id, laterality, csv_path, video_path, results_json, comments) VALUES (?,?,?,?,?,?)", 
                           (pid, lat, str(csv), str(vid), js, comments))
            eid = cursor.lastrowid
            conn.commit()
            conn.close()
            return eid
        except Exception as e:
            logger.error(f"Erreur save_exam: {e}")
            return -1
    
    def delete_exam(self, exam_id: int) -> bool:
        """Supprime un examen spécifique."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Erreur delete exam: {e}")
            return False

    def update_exam_comment(self, exam_id: int, new_comment: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE exams SET comments = ? WHERE id = ?", (new_comment, exam_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e: 
            logger.error(f"Err upd com: {e}")
            return False

    def get_patient_history(self, pid: int) -> List[Dict[str, Any]]:
        """Récupère l'historique complet des examens d'un patient."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams WHERE patient_id=? ORDER BY exam_date DESC", (pid,))
        hist = []
        for r in cursor.fetchall():
            d = dict(r)
            try: d['results_data'] = json.loads(d['results_json'])
            except: d['results_data'] = {}
            hist.append(d)
        conn.close()
        return hist

    # --- CLINIQUE ---
    def set_clinic_info(self, name: str, addr: str, phone: str, email: str, doc: str, logo: str):
        """Met à jour les informations de la clinique (ID=1 unique)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO clinic_info (id, name, address, phone, email, doctor_name, logo_path) VALUES (1, ?, ?, ?, ?, ?, ?)",
                       (name, addr, phone, email, doc, logo))
        conn.commit()
        conn.close()

    def get_clinic_info(self) -> Dict[str, str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clinic_info WHERE id=1")
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {}

    # --- MACROS SIMPLIFIÉES ---
    def add_macro(self, content: str):
        """Ajoute une macro sans titre."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # On insère uniquement le contenu
        cursor.execute("INSERT INTO macros (content) VALUES (?)", (content,))
        conn.commit()
        conn.close()

    def delete_macro(self, mid: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM macros WHERE id=?", (mid,))
        conn.commit()
        conn.close()

    def get_macros(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM macros")
        res = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return res