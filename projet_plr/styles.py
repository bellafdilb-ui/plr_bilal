"""
styles.py
=========
Feuille de style V3 (Sliders Sobres & Simples).
"""

from PySide6.QtWidgets import QApplication

def apply_modern_theme(app):
    """Applique le thème global à l'application."""
    
    theme = """
    /* --- GLOBAL --- */
    QMainWindow, QDialog {
        background-color: #f4f6f9;
        color: #2c3e50;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 10pt;
    }

    /* --- GROUPBOX (Cadres) --- */
    QGroupBox {
        background-color: #ffffff;
        border: 1px solid #dcdfe6;
        border-radius: 8px;
        margin-top: 20px;
        padding-top: 15px;
        padding-bottom: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 15px;
        top: 0px;
        padding: 0 5px;
        color: #007bff;
        font-weight: bold;
        font-size: 11pt;
        background-color: #f4f6f9; 
    }

    /* --- BOUTONS --- */
    QPushButton {
        background-color: #eef2f7;
        border: 1px solid #ced4da;
        border-radius: 6px;
        padding: 6px 12px;
        min-height: 22px;
        color: #495057;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: #dbe2ef;
        border-color: #b0b8c1;
    }
    QPushButton:pressed {
        background-color: #cfd8e8;
    }

    /* --- ENTRÉES DE TEXTE & COMBOS --- */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QDateEdit {
        background-color: #ffffff;
        border: 1px solid #ced4da;
        border-radius: 4px;
        padding: 5px;
        min-height: 20px;
        selection-background-color: #007bff;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #007bff;
    }

    /* --- TABLEAUX --- */
    QTableWidget {
        background-color: #ffffff;
        gridline-color: #f0f0f0;
        border: 1px solid #dcdfe6;
        border-radius: 4px;
        selection-background-color: #e3f2fd;
        selection-color: #000000;
    }
    QHeaderView::section {
        background-color: #f8f9fa;
        padding: 6px;
        border: none;
        border-bottom: 2px solid #007bff;
        font-weight: bold;
        color: #495057;
        min-height: 25px;
    }

    /* --- SLIDERS (NOUVEAU STYLE SOBRE) --- */
    QSlider::groove:horizontal {
        border: 1px solid #bdc3c7; /* Gris neutre */
        background: #f0f0f0;      /* Fond gris clair */
        height: 6px;              /* Barre plus fine */
        border-radius: 3px;
    }

    QSlider::sub-page:horizontal {
        background: #3498db;      /* Bleu uni standard (pas de dégradé) */
        border: 1px solid #2980b9;
        height: 6px;
        border-radius: 3px;
    }

    QSlider::handle:horizontal {
        background: #ffffff;      /* Curseur blanc simple */
        border: 1px solid #7f8c8d; /* Bordure grise */
        width: 16px;              /* Taille standard */
        height: 16px;
        margin-top: -6px;         /* Centrage vertical */
        margin-bottom: -6px;
        border-radius: 8px;       /* Cercle parfait */
    }

    QSlider::handle:horizontal:hover {
        background: #ecf0f1;      /* Léger changement au survol */
        border-color: #3498db;
    }
    
    /* --- BARRE DE PROGRESSION --- */
    QProgressBar {
        border: 1px solid #ced4da;
        border-radius: 6px;
        text-align: center;
        background-color: #fff;
        min-height: 20px;
    }
    QProgressBar::chunk {
        background-color: #28a745;
        border-radius: 5px;
    }
    """
    
    if isinstance(app, QApplication):
        app.setStyleSheet(theme)