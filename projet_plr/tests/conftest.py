"""
conftest.py — Fixtures partagées pour toute la suite de tests.
"""
import sys
import os
import pytest

# Ajouter le répertoire racine du projet au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def tmp_config(tmp_path):
    """Retourne le chemin d'un fichier config temporaire."""
    return str(tmp_path / "config.json")


@pytest.fixture
def tmp_db(tmp_path):
    """Crée un DatabaseManager avec une BDD temporaire."""
    from db_manager import DatabaseManager
    return DatabaseManager(db_path=str(tmp_path / "test.db"))
