"""
tests/test_gui.py
=================
Tests automatisés de l'interface graphique avec pytest-qt.
"""
import pytest
from PySide6.QtCore import Qt, QDate
from unittest.mock import MagicMock, patch

import welcome_screen

@pytest.fixture
def mock_db(monkeypatch):
    """
    Remplace le vrai DatabaseManager par une version simulée (Mock).
    Cela évite de créer/modifier le fichier vet_data.db pendant les tests.
    """
    mock_manager_class = MagicMock()
    mock_instance = MagicMock()
    
    # Comportement par défaut du mock
    mock_instance.search_patients.return_value = []
    mock_instance.get_patient_history.return_value = []
    mock_instance.add_patient.return_value = 1  # Simule un ID créé avec succès
    
    mock_manager_class.return_value = mock_instance
    
    # On remplace la classe DatabaseManager dans le module welcome_screen
    monkeypatch.setattr(welcome_screen, "DatabaseManager", mock_manager_class)
    return mock_instance

def test_welcome_screen_scenario(qtbot, mock_db):
    """
    Scénario : Ouvrir l'accueil, cliquer sur 'Nouveau Patient', remplir le formulaire et sauvegarder.
    """
    # 1. Initialisation du widget
    window = welcome_screen.WelcomeScreen()
    qtbot.addWidget(window) # Enregistre le widget pour gestion auto (fermeture propre)
    with qtbot.waitExposed(window):
        window.show()

    # 2. Vérification état initial
    assert window.windowTitle() == "PLR Vet - Accueil"
    assert window.btn_start.isEnabled() is False  # Bouton "Ouvrir Dossier" désactivé

    # 3. Interaction : Clic sur "CRÉER NOUVEAU PATIENT"
    qtbot.mouseClick(window.btn_new_patient, Qt.MouseButton.LeftButton)

    # Vérification visuelle que l'interface a changé
    assert "Nouveau Patient" in window.grp_identity.title()
    assert window.btn_save.text() == "💾 Créer Fiche"

    # 4. Interaction : Remplissage du formulaire (Clavier)
    qtbot.keyClicks(window.inp_name, "Rex")
    qtbot.keyClicks(window.inp_tattoo, "PUCE123")
    
    # Vérification que le champ est bien rempli
    assert window.inp_name.text() == "Rex"

    # 5. Interaction : Sauvegarde
    qtbot.mouseClick(window.btn_save, Qt.MouseButton.LeftButton)

    # 6. Validation Logique : On vérifie que la méthode add_patient a été appelée
    # add_patient(tattoo, name, species, ...)
    mock_db.add_patient.assert_called_once()
    args, _ = mock_db.add_patient.call_args
    assert args[0] == "PUCE123" # Premier argument : tattoo_id
    assert args[1] == "Rex"     # Deuxième argument : name

def test_search_and_edit_patient(qtbot, mock_db):
    """Vérifie la recherche et l'édition d'un patient."""
    window = welcome_screen.WelcomeScreen()
    qtbot.addWidget(window)
    with qtbot.waitExposed(window):
        window.show()
        
    # Mock search result
    p_data = {'id': 1, 'name': 'Rex', 'species': 'Chien', 'tattoo_id': '123', 
              'breed': 'Lab', 'gender': 'M', 'birth_date': '2020-01-01', 'notes': ''}
    mock_db.search_patients.return_value = [p_data]
    
    # 1. Search
    qtbot.keyClicks(window.search_bar, "Rex")
    assert window.table.rowCount() == 1
    
    # 2. Click Patient
    qtbot.mouseClick(window.table.viewport(), Qt.MouseButton.LeftButton, pos=window.table.visualItemRect(window.table.item(0,0)).center())
    
    assert window.inp_name.text() == "Rex"
    assert window.btn_save.text() == "💾 Mettre à jour"
    
    # 3. Edit
    window.inp_name.setText("Rex Updated")
    qtbot.mouseClick(window.btn_save, Qt.MouseButton.LeftButton)
    
    mock_db.update_patient.assert_called_once()
    
    # 4. Delete
    with patch("PySide6.QtWidgets.QMessageBox.question", return_value=16384): # Yes
        qtbot.mouseClick(window.btn_delete, Qt.MouseButton.LeftButton)
        mock_db.delete_patient.assert_called_with(1)

def test_welcome_screen_extras(qtbot, mock_db):
    """Teste les fonctions annexes (Age, Voir Examen)."""
    window = welcome_screen.WelcomeScreen()
    qtbot.addWidget(window)
    
    # 1. Calcul Age
    # Né il y a 1 an exactement
    dob = QDate.currentDate().addYears(-1)
    window.date_dob.setDate(dob)
    # Le texte doit contenir "1 ans" ou "12 mois" selon l'implémentation
    assert "1 ans" in window.lbl_age.text() or "12 mois" in window.lbl_age.text()
    
    # 2. Voir Examen
    # On mock pandas et le dialog pour ne pas ouvrir de fenêtre réelle
    exam = {'csv_path': 'dummy.csv', 'results_data': {}, 'laterality': 'OD', 'exam_date': '2023'}
    
    with patch("pandas.read_csv"), \
         patch("welcome_screen.PLRResultsDialog") as MockDlg:
        window.view_exam(exam)
        MockDlg.return_value.exec.assert_called()

def test_welcome_screen_validation(qtbot, mock_db):
    """Vérifie la validation des champs et l'annulation."""
    window = welcome_screen.WelcomeScreen()
    qtbot.addWidget(window)
    
    # 1. Sauvegarde avec champs vides
    window.mode_create_new()
    window.inp_name.clear()
    window.inp_tattoo.clear()
    
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        window.save_patient()
        mock_warn.assert_called() # Doit afficher une alerte
        assert mock_db.add_patient.called is False

    # 2. Annulation suppression
    window.current_patient_id = 1
    with patch("PySide6.QtWidgets.QMessageBox.question", return_value=65536): # 65536 = No
        window.delete_patient()
        mock_db.delete_patient.assert_not_called()