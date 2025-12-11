"""
tests/test_pdf.py
Test de la génération de rapport PDF.
"""
import os
import pytest
from matplotlib.figure import Figure
from pdf_generator import PDFGenerator

def test_pdf_creation(tmp_path):
    """Vérifie que le PDF est bien généré sur le disque."""
    
    # 1. Préparer un fichier de sortie temporaire
    # tmp_path est fourni par pytest, il est détruit à la fin du test
    output_file = tmp_path / "test_rapport.pdf"
    
    # 2. Préparer des données fictives
    clinic_info = {
        "name": "Clinique Test",
        "address": "10 Rue du Code",
        "doctor_name": "Dr. Robot"
    }
    
    patient_info = {
        "name": "Rex",
        "species": "Chien",
        "breed": "Labrador",
        "id": "12345ABC",
        "owner": "M. Dupont"
    }
    
    exam_info = {
        "date": "2023-10-27 10:00:00",
        "laterality": "OD"
    }
    
    metrics = {
        "baseline_mm": 5.5,
        "constriction_percent": 30
    }
    
    comments = "Ceci est un test automatisé."
    
    # Créer un faux graphique (Figure Matplotlib vide)
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    
    # 3. Lancer la génération
    gen = PDFGenerator(str(output_file))
    gen.generate(clinic_info, patient_info, exam_info, metrics, comments, fig)
    
    # 4. ASSERTION (Le Verdict)
    # Le fichier doit exister
    assert output_file.exists(), "Le fichier PDF n'a pas été créé"
    # Le fichier ne doit pas être vide (> 0 octets)
    assert output_file.stat().st_size > 0, "Le fichier PDF est vide"