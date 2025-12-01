"""
welcome_screen.py
=================
Interface d'accueil vétérinaire.
Permet de rechercher un animal ou d'en créer un nouveau avant l'examen.
"""

import sys
from datetime import datetime
from dateutil.relativedelta import relativedelta # pip install python-dateutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QFormLayout, QComboBox, QDateEdit,
    QTextEdit, QMessageBox, QSplitter, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QIcon, QFont

from db_manager import DatabaseManager

class WelcomeScreen(QMainWindow):
    """Fenêtre de gestion des patients (Animaux)."""
    
    # Signal émis quand un patient est sélectionné pour l'examen
    patient_selected = Signal(dict) # Envoie le dictionnaire du patient

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLR Vet - Accueil")
        self.resize(1100, 700)
        
        self.db = DatabaseManager()
        self.setup_ui()
        self.apply_stylesheet()
        self.load_patients()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter pour séparer Liste (Gauche) et Formulaire (Droite)
        splitter = QSplitter(Qt.Horizontal)
        
        # === GAUCHE : LISTE DES PATIENTS ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # Recherche
        search_group = QGroupBox("Recherche Patient")
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Nom, Tatouage ou Race...")
        self.search_bar.textChanged.connect(self.load_patients)
        search_layout.addWidget(QLabel("🔍"))
        search_layout.addWidget(self.search_bar)
        search_group.setLayout(search_layout)
        
        # Tableau
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nom", "Espèce", "Tatouage", "Date Ajout"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.on_table_double_click)
        
        left_layout.addWidget(search_group)
        left_layout.addWidget(self.table)
        
        # === DROITE : FICHE ANIMAL ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        form_group = QGroupBox("Fiche Animal")
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        # Champs
        self.input_name = QLineEdit()
        self.input_tattoo = QLineEdit()
        self.input_tattoo.setPlaceholderText("ID Unique (Puce/Tatouage)")
        
        # Espèce / Race sur la même ligne
        species_layout = QHBoxLayout()
        self.combo_species = QComboBox()
        self.combo_species.addItems(["Chien", "Chat", "Cheval", "NAC", "Autre"])
        self.input_breed = QLineEdit()
        self.input_breed.setPlaceholderText("Race")
        species_layout.addWidget(self.combo_species, 1)
        species_layout.addWidget(self.input_breed, 2)
        
        # Sexe
        gender_layout = QHBoxLayout()
        self.gender_group = QButtonGroup(self)
        self.radio_m = QRadioButton("Mâle")
        self.radio_f = QRadioButton("Femelle")
        self.radio_m.setChecked(True)
        self.gender_group.addButton(self.radio_m)
        self.gender_group.addButton(self.radio_f)
        gender_layout.addWidget(self.radio_m)
        gender_layout.addWidget(self.radio_f)
        gender_layout.addStretch()
        
        # Date Naissance & Age
        dob_layout = QHBoxLayout()
        self.date_dob = QDateEdit()
        self.date_dob.setDisplayFormat("dd/MM/yyyy")
        self.date_dob.setCalendarPopup(True)
        self.date_dob.setDate(QDate.currentDate().addYears(-1)) # Par défaut 1 an
        self.date_dob.dateChanged.connect(self.calculate_age)
        
        self.lbl_age = QLabel("1 an")
        self.lbl_age.setStyleSheet("font-weight: bold; color: #007bff;")
        
        dob_layout.addWidget(self.date_dob)
        dob_layout.addWidget(QLabel("  Âge calculé :"))
        dob_layout.addWidget(self.lbl_age)
        
        # Infos Sup
        self.input_notes = QTextEdit()
        self.input_notes.setPlaceholderText("Antécédents oculaires, traitement en cours...")
        self.input_notes.setMaximumHeight(80)
        
        # Ajout au formulaire
        form_layout.addRow("Nom :", self.input_name)
        form_layout.addRow("Tatouage/ID :", self.input_tattoo)
        form_layout.addRow("Espèce / Race :", species_layout)
        form_layout.addRow("Sexe :", gender_layout)
        form_layout.addRow("Né(e) le :", dob_layout)
        form_layout.addRow("Notes :", self.input_notes)
        
        form_group.setLayout(form_layout)
        
        # Boutons Actions
        btn_layout = QHBoxLayout()
        
        self.btn_new = QPushButton("✨ Nouveau")
        self.btn_new.clicked.connect(self.clear_form)
        
        self.btn_save = QPushButton("💾 Enregistrer")
        self.btn_save.clicked.connect(self.save_patient)
        self.btn_save.setStyleSheet("background-color: #e0e0e0; color: black;")
        
        self.btn_start = QPushButton("🚀 LANCER EXAMEN")
        self.btn_start.setFixedHeight(50)
        self.btn_start.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; font-size: 14px;")
        self.btn_start.clicked.connect(self.start_exam)
        
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_save)
        
        right_layout.addWidget(form_group)
        right_layout.addLayout(btn_layout)
        right_layout.addSpacing(20)
        right_layout.addWidget(self.btn_start)
        right_layout.addStretch()
        
        # Assemblage
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 600]) # Ratio initial
        
        main_layout.addWidget(splitter)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; font-family: 'Segoe UI', Arial; }
            QGroupBox { background-color: white; border: 1px solid #ccc; border-radius: 5px; margin-top: 10px; padding-top: 15px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #333; }
            QLineEdit, QDateEdit, QComboBox, QTextEdit { padding: 8px; border: 1px solid #ccc; border-radius: 4px; background: #fafafa; }
            QLineEdit:focus { border: 1px solid #007bff; background: white; }
            QTableWidget { border: 1px solid #ccc; background: white; selection-background-color: #007bff; }
            QPushButton { padding: 8px 15px; border-radius: 4px; font-weight: bold; border: 1px solid #ccc; background: white; }
            QPushButton:hover { background-color: #e9ecef; }
        """)

    def calculate_age(self):
        """Calcule l'âge automatiquement."""
        dob = self.date_dob.date().toPython()
        today = datetime.now().date()
        
        delta = relativedelta(today, dob)
        
        age_str = ""
        if delta.years > 0:
            age_str += f"{delta.years} an{'s' if delta.years > 1 else ''}"
        if delta.months > 0:
            if age_str: age_str += " "
            age_str += f"{delta.months} mois"
            
        if not age_str: # Moins d'un mois
            age_str = f"{delta.days} jours"
            
        self.lbl_age.setText(age_str)

    def load_patients(self):
        """Charge la liste depuis la DB."""
        query = self.search_bar.text()
        patients = self.db.search_patients(query)
        
        self.table.setRowCount(0)
        for row, p in enumerate(patients):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(p['name']))
            self.table.setItem(row, 1, QTableWidgetItem(p['species']))
            self.table.setItem(row, 2, QTableWidgetItem(p['tattoo_id']))
            
            date_str = p['created_at'].split(" ")[0] # Juste la date
            self.table.setItem(row, 3, QTableWidgetItem(date_str))
            
            # On stocke l'ID complet dans l'item caché pour récupération
            self.table.item(row, 0).setData(Qt.UserRole, p)

    def on_table_double_click(self, item):
        """Remplit le formulaire au clic."""
        # Récupérer les données stockées dans la colonne 0
        data = self.table.item(item.row(), 0).data(Qt.UserRole)
        if data:
            self.input_name.setText(data['name'])
            self.input_tattoo.setText(data['tattoo_id'])
            self.combo_species.setCurrentText(data['species'])
            self.input_breed.setText(data['breed'])
            self.input_notes.setText(data['notes'])
            
            if data['gender'] == 'M': self.radio_m.setChecked(True)
            else: self.radio_f.setChecked(True)
            
            if data['birth_date']:
                qdate = QDate.fromString(data['birth_date'], "yyyy-MM-dd")
                self.date_dob.setDate(qdate)

    def clear_form(self):
        self.input_name.clear()
        self.input_tattoo.clear()
        self.input_breed.clear()
        self.input_notes.clear()
        self.date_dob.setDate(QDate.currentDate())
        self.table.clearSelection()

    def save_patient(self):
        name = self.input_name.text().strip()
        tattoo = self.input_tattoo.text().strip()
        
        if not name or not tattoo:
            QMessageBox.warning(self, "Erreur", "Le nom et le tatouage/ID sont obligatoires.")
            return

        gender = "M" if self.radio_m.isChecked() else "F"
        dob = self.date_dob.date().toString("yyyy-MM-dd")
        
        pid = self.db.add_patient(
            tattoo_id=tattoo,
            name=name,
            species=self.combo_species.currentText(),
            breed=self.input_breed.text(),
            gender=gender,
            birth_date=dob,
            notes=self.input_notes.toPlainText()
        )
        
        if pid != -1:
            self.load_patients()
            QMessageBox.information(self, "Succès", "Animal enregistré !")
        else:
            QMessageBox.warning(self, "Erreur", "Erreur lors de l'enregistrement (ID existant ?).")

    def start_exam(self):
        """Lance l'examen pour le patient affiché."""
        name = self.input_name.text().strip()
        tattoo = self.input_tattoo.text().strip()
        
        if not name or not tattoo:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner ou créer un patient d'abord.")
            return
            
        # Si le patient n'est pas encore en base, on le crée à la volée
        # On vérifie s'il existe déjà via le tatouage
        existing = self.db.search_patients(tattoo)
        patient_data = None
        
        # On cherche correspondance exacte
        for p in existing:
            if p['tattoo_id'] == tattoo:
                patient_data = p
                break
        
        if not patient_data:
            # Création automatique
            self.save_patient()
            # Récupération après sauvegarde
            existing = self.db.search_patients(tattoo)
            if existing: patient_data = existing[0]
        
        if patient_data:
            self.patient_selected.emit(patient_data)
            self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WelcomeScreen()
    window.show()
    sys.exit(app.exec())