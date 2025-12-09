"""
tests/test_database.py
Test des opérations CRUD sur la BDD via un fichier temporaire.
"""
import pytest
from db_manager import DatabaseManager

@pytest.fixture
def db(tmp_path):
    """
    Crée une BDD temporaire dans un fichier physique géré par pytest.
    'tmp_path' est une fixture magique de pytest qui crée un dossier unique
    et le supprime à la fin.
    """
    # On définit un chemin de fichier dans le dossier temporaire
    db_file = tmp_path / "test_vet.db"
    
    # On initialise le manager avec ce chemin (converti en string)
    manager = DatabaseManager(db_path=str(db_file))
    return manager

def test_add_patient(db):
    """Peut-on ajouter un patient ?"""
    # On ajoute un patient
    pid = db.add_patient("TEST001", "Rex", "Chien")
    
    # Vérification 1 : L'ID doit être valide (pas -1)
    assert pid != -1, "L'ajout du patient a échoué (retourne -1)"
    
    # Vérification 2 : On doit pouvoir le retrouver
    history = db.search_patients("Rex")
    assert len(history) >= 1
    assert history[0]['name'] == "Rex"

def test_delete_patient(db):
    """Peut-on supprimer un patient ?"""
    # 1. On crée d'abord un patient pour pouvoir le supprimer
    pid = db.add_patient("DEL001", "Fifi", "Chat")
    assert pid != -1, "Impossible de créer le patient à supprimer"
    
    # 2. On le supprime
    success = db.delete_patient(pid)
    assert success is True, "La suppression a renvoyé False"
    
    # 3. Vérification : Il ne doit plus être dans la recherche
    res = db.search_patients("Fifi")
    assert len(res) == 0, "Le patient Fifi est toujours là après suppression"