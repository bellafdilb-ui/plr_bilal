"""
tests/test_excel.py
Test de l'export Excel (Feature ajoutée en V3.21).
"""
import os
import pytest
import pandas as pd
from main_application import MainWindow
# Note : Pour tester l'export Excel sans lancer toute l'interface, 
# on va simuler la logique d'export manuellement ou via une fonction extraite.

def test_excel_export_logic(tmp_path):
    """Vérifie que pandas arrive bien à créer le fichier Excel structuré."""
    
    # 1. Données fictives
    output_file = tmp_path / "test_data.xlsx"
    
    csv_data = pd.DataFrame({
        'timestamp': [0.0, 0.1, 0.2],
        'diameter': [8.0, 8.0, 7.9]
    })
    
    metrics = {'baseline': 8.0, 'constriction': 10}
    info = {'Patient': 'Test', 'Oeil': 'OD'}
    
    # 2. Simulation de la logique d'export (copiée de main_application)
    try:
        with pd.ExcelWriter(str(output_file)) as writer:
            # Onglet Résumé
            combined = {**info, **metrics}
            pd.DataFrame(list(combined.items()), columns=["Param", "Valeur"]).to_excel(writer, sheet_name="Résumé", index=False)
            # Onglet Data
            csv_data.to_excel(writer, sheet_name="Raw_Data", index=False)
    except Exception as e:
        pytest.fail(f"L'écriture Excel a échoué : {e}")

    # 3. Vérifications
    assert output_file.exists()
    assert output_file.stat().st_size > 0