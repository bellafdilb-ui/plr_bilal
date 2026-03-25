"""
test_database.py
================
Tests CRUD du DatabaseManager (patients, examens, clinique, macros).
Utilise une BDD SQLite temporaire (fixture tmp_db de conftest.py).
"""
import pytest


# ─── Patients ────────────────────────────────────────────────────────

class TestPatients:
    def test_add_patient(self, tmp_db):
        pid = tmp_db.add_patient("CHIP001", "Rex", "Chien", breed="Berger")
        assert pid > 0

    def test_add_patient_duplicate_id_fails(self, tmp_db):
        tmp_db.add_patient("CHIP001", "Rex", "Chien")
        pid2 = tmp_db.add_patient("CHIP001", "Luna", "Chat")
        assert pid2 == -1

    def test_search_by_name(self, tmp_db):
        tmp_db.add_patient("CHIP002", "Luna", "Chat")
        results = tmp_db.search_patients("Luna")
        assert len(results) == 1
        assert results[0]['name'] == "Luna"

    def test_search_by_tattoo(self, tmp_db):
        tmp_db.add_patient("TAT-789", "Milo", "Chien")
        results = tmp_db.search_patients("TAT-789")
        assert len(results) == 1

    def test_search_empty_returns_nothing(self, tmp_db):
        results = tmp_db.search_patients("inexistant")
        assert len(results) == 0

    def test_update_patient(self, tmp_db):
        pid = tmp_db.add_patient("CHIP003", "Fifi", "Chat")
        ok = tmp_db.update_patient(pid, "Fifi", "Chat", "Siamois", "F", "2020-01-01", "Stérilisée")
        assert ok is True
        results = tmp_db.search_patients("Fifi")
        assert results[0]['breed'] == "Siamois"

    def test_delete_patient(self, tmp_db):
        pid = tmp_db.add_patient("DEL001", "Ghost", "Chien")
        ok = tmp_db.delete_patient(pid)
        assert ok is True
        results = tmp_db.search_patients("Ghost")
        assert len(results) == 0

    def test_name_is_capitalized(self, tmp_db):
        tmp_db.add_patient("CAP001", "luna", "Chat")
        results = tmp_db.search_patients("luna")
        assert results[0]['name'] == "Luna"

    def test_anonymized_hash_generated(self, tmp_db):
        pid = tmp_db.add_patient("HASH001", "Test", "Chien")
        results = tmp_db.search_patients("Test")
        assert results[0]['anonymized_hash'] is not None
        assert len(results[0]['anonymized_hash']) == 64  # SHA-256


# ─── Examens ─────────────────────────────────────────────────────────

class TestExams:
    def test_save_exam(self, tmp_db):
        pid = tmp_db.add_patient("EX001", "Rex", "Chien")
        eid = tmp_db.save_exam(pid, "OD", "data/test.csv", "data/test.avi")
        assert eid > 0

    def test_save_exam_with_results(self, tmp_db):
        pid = tmp_db.add_patient("EX002", "Luna", "Chat")
        results = {"constriction_pct": 45.2, "latency_ms": 220}
        eid = tmp_db.save_exam(pid, "OG", "test.csv", results=results)
        assert eid > 0

    def test_get_patient_history(self, tmp_db):
        pid = tmp_db.add_patient("HIST001", "Buddy", "Chien")
        tmp_db.save_exam(pid, "OD", "exam1.csv")
        tmp_db.save_exam(pid, "OG", "exam2.csv")
        history = tmp_db.get_patient_history(pid)
        assert len(history) == 2

    def test_history_contains_parsed_results(self, tmp_db):
        pid = tmp_db.add_patient("HIST002", "Milo", "Chien")
        results = {"latency_ms": 180}
        tmp_db.save_exam(pid, "OD", "test.csv", results=results)
        history = tmp_db.get_patient_history(pid)
        assert history[0]['results_data']['latency_ms'] == 180

    def test_delete_exam(self, tmp_db):
        pid = tmp_db.add_patient("DEL002", "Coco", "Chat")
        eid = tmp_db.save_exam(pid, "OD", "test.csv")
        ok = tmp_db.delete_exam(eid)
        assert ok is True
        history = tmp_db.get_patient_history(pid)
        assert len(history) == 0

    def test_update_exam_comment(self, tmp_db):
        pid = tmp_db.add_patient("COM001", "Max", "Chien")
        eid = tmp_db.save_exam(pid, "OD", "test.csv", comments="Initial")
        ok = tmp_db.update_exam_comment(eid, "Mise à jour commentaire")
        assert ok is True


# ─── Clinique ────────────────────────────────────────────────────────

class TestClinic:
    def test_set_and_get_clinic_info(self, tmp_db):
        tmp_db.set_clinic_info("Clinique Vet", "123 Rue", "0601020304",
                               "vet@mail.com", "Dr. Martin", "logo.png")
        info = tmp_db.get_clinic_info()
        assert info['name'] == "Clinique Vet"
        assert info['doctor_name'] == "Dr. Martin"

    def test_clinic_info_empty_by_default(self, tmp_db):
        info = tmp_db.get_clinic_info()
        assert info == {}

    def test_clinic_info_upsert(self, tmp_db):
        tmp_db.set_clinic_info("V1", "", "", "", "", "")
        tmp_db.set_clinic_info("V2", "", "", "", "", "")
        info = tmp_db.get_clinic_info()
        assert info['name'] == "V2"


# ─── Macros ──────────────────────────────────────────────────────────

class TestMacros:
    def test_add_and_get_macro(self, tmp_db):
        tmp_db.add_macro("PLR normal bilatéral")
        macros = tmp_db.get_macros()
        assert len(macros) == 1
        assert macros[0]['content'] == "PLR normal bilatéral"

    def test_delete_macro(self, tmp_db):
        tmp_db.add_macro("A supprimer")
        macros = tmp_db.get_macros()
        mid = macros[0]['id']
        tmp_db.delete_macro(mid)
        assert len(tmp_db.get_macros()) == 0

    def test_multiple_macros(self, tmp_db):
        tmp_db.add_macro("Macro 1")
        tmp_db.add_macro("Macro 2")
        tmp_db.add_macro("Macro 3")
        assert len(tmp_db.get_macros()) == 3
