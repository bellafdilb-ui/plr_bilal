"""
tests/test_db_manager.py
========================
Test fonctionnel de la base de données (CRUD).
"""
import pytest
import os
from unittest.mock import patch
from db_manager import DatabaseManager

def test_database_lifecycle(tmp_path):
    # 1. Création d'une DB temporaire dans un dossier isolé
    db_file = tmp_path / "test_vet.db"
    db = DatabaseManager(str(db_file))
    
    # 2. Test Ajout Patient
    pid = db.add_patient("TEST001", "Médor", "Chien")
    assert pid != -1
    
    # 3. Test Recherche
    results = db.search_patients("Médor")
    assert len(results) == 1
    assert results[0]['tattoo_id'] == "TEST001"
    
    # 4. Test Ajout Examen
    eid = db.save_exam(pid, "OD", "dummy_path.csv", results={"amplitude": 2.5})
    assert eid != -1
    
    # 5. Test Historique
    history = db.get_patient_history(pid)
    assert len(history) == 1
    assert history[0]['laterality'] == "OD"
    
    # 6. Test Suppression
    assert db.delete_patient(pid) is True
    assert len(db.search_patients("Médor")) == 0

def test_extended_features(tmp_path):
    """Teste les fonctionnalités avancées (Macros, Clinique, Updates)."""
    db_file = tmp_path / "test_vet_ext.db"
    db = DatabaseManager(str(db_file))

    # 1. Infos Clinique
    db.set_clinic_info("Ma Clinique", "123 Rue", "0102030405", "email@test.com", "Dr. House", "logo.png")
    info = db.get_clinic_info()
    assert info['name'] == "Ma Clinique"
    assert info['doctor_name'] == "Dr. House"

    # 2. Macros
    db.add_macro("Phrase type 1")
    macros = db.get_macros()
    assert len(macros) == 1
    assert macros[0]['content'] == "Phrase type 1"
    db.delete_macro(macros[0]['id'])
    assert len(db.get_macros()) == 0

    # 3. Mise à jour Patient
    pid = db.add_patient("UPD001", "OldName", "Chat")
    assert db.update_patient(pid, "NewName", "Chat", "Siamois", "F", "2020-01-01", "Notes") is True
    p = db.search_patients("NewName")[0]
    assert p['name'] == "NewName"

def test_db_error_handling(tmp_path):
    """Vérifie que les méthodes retournent des erreurs proprement en cas de crash DB."""
    db_file = tmp_path / "error.db"
    db = DatabaseManager(str(db_file))
    
    # On simule une erreur fatale lors de la connexion/exécution
    with patch.object(db, '_get_connection', side_effect=Exception("DB Crash")):
        # Ces méthodes ont des blocs try/except qui doivent retourner -1 ou False
        assert db.add_patient("A", "B", "C") == -1
        assert db.update_patient(1, "A", "B", "", "", "", "") is False
        assert db.delete_patient(1) is False
        assert db.save_exam(1, "OD", "f.csv") == -1
        assert db.delete_exam(1) is False
