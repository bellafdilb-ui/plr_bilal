"""
welcome_screen.py
=================
Interface d'accueil V6.2 (Validation Champs Obligatoires).
"""

import sys
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QFormLayout, QComboBox, QDateEdit,
    QTextEdit, QMessageBox, QSplitter, QRadioButton, QButtonGroup,
    QAbstractItemView, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QAction, QColor
from db_manager import DatabaseManager
from plr_results_viewer import PLRResultsDialog
from settings_dialog import SettingsDialog, ConfigManager

class WelcomeScreen(QMainWindow):
    patient_selected = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLR Vet - Accueil")
        self.resize(1200, 750)
        self.db = DatabaseManager()
        self.config_manager = ConfigManager()
        self.current_patient_id = None
        self.setup_ui()
        self._create_menu_bar()
        self.apply_stylesheet()
        self.load_patients()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)
        
        # GAUCHE (Liste)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        lbl_list = QLabel("📂 Base de Données")
        lbl_list.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔎 Rechercher...")
        self.search_bar.textChanged.connect(self.load_patients)
        search_layout.addWidget(self.search_bar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nom", "Espèce", "ID / Puce"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemClicked.connect(self.on_patient_clicked)
        
        self.btn_new_patient = QPushButton("➕ CRÉER NOUVEAU PATIENT")
        self.btn_new_patient.setFixedHeight(45)
        self.btn_new_patient.setCursor(Qt.PointingHandCursor)
        self.btn_new_patient.clicked.connect(self.mode_create_new)
        self.btn_new_patient.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
        
        left_layout.addWidget(lbl_list)
        left_layout.addLayout(search_layout)
        left_layout.addWidget(self.table)
        left_layout.addWidget(self.btn_new_patient)
        
        # DROITE (Détails)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        
        # 1. Identité
        self.grp_identity = QGroupBox("📄 Fiche Patient")
        form = QFormLayout()
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Nom de l'animal *") # Indication visuelle
        self.inp_tattoo = QLineEdit()
        self.inp_tattoo.setPlaceholderText("Puce / Tatouage *")
        
        h_species = QHBoxLayout()
        self.combo_species = QComboBox()
        self.combo_species.addItems(["Chien", "Chat", "Cheval", "NAC"])
        self.inp_breed = QLineEdit()
        self.inp_breed.setPlaceholderText("Race")
        h_species.addWidget(self.combo_species, 1)
        h_species.addWidget(self.inp_breed, 2)
        
        h_gender = QHBoxLayout()
        self.gender_group = QButtonGroup(right_content)
        self.rad_m = QRadioButton("Mâle")
        self.rad_f = QRadioButton("Femelle")
        self.rad_m.setChecked(True)
        self.gender_group.addButton(self.rad_m)
        self.gender_group.addButton(self.rad_f)
        h_gender.addWidget(self.rad_m)
        h_gender.addWidget(self.rad_f)
        h_gender.addStretch()
        
        self.date_dob = QDateEdit()
        self.date_dob.setCalendarPopup(True)
        self.date_dob.setDate(QDate.currentDate())
        self.date_dob.dateChanged.connect(self.calculate_age)
        self.lbl_age = QLabel("(Nouveau né)")
        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(50)
        
        form.addRow("Nom * :", self.inp_name)
        form.addRow("ID * :", self.inp_tattoo)
        form.addRow("Espèce:", h_species)
        form.addRow("Sexe:", h_gender)
        form.addRow("Né le:", self.date_dob)
        form.addRow("", self.lbl_age)
        form.addRow("Notes:", self.txt_notes)
        
        h_actions = QHBoxLayout()
        self.btn_save = QPushButton("💾 Enregistrer")
        self.btn_save.clicked.connect(self.save_patient)
        self.btn_delete = QPushButton("🗑️ Supprimer")
        self.btn_delete.setStyleSheet("background-color: #dc3545; color: white;")
        self.btn_delete.clicked.connect(self.delete_patient)
        self.btn_delete.setVisible(False)
        h_actions.addWidget(self.btn_save)
        h_actions.addWidget(self.btn_delete)
        form.addRow(h_actions)
        self.grp_identity.setLayout(form)
        
        # 2. Historique
        self.grp_history = QGroupBox("📊 Historique du Patient")
        v_hist = QVBoxLayout()
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(4)
        self.table_history.setHorizontalHeaderLabels(["Date", "Oeil", "Type", "Voir"])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_history.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_history.setMinimumHeight(200)
        v_hist.addWidget(self.table_history)
        self.grp_history.setLayout(v_hist)
        
        # 3. Action
        self.grp_start = QGroupBox("🚀 Action")
        v_start = QVBoxLayout()
        
        self.btn_start = QPushButton("OUVRIR DOSSIER D'EXAMEN")
        self.btn_start.setFixedHeight(50)
        self.btn_start.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; font-size: 14px;")
        self.btn_start.clicked.connect(self.start_exam_process)
        self.btn_start.setEnabled(False)
        
        v_start.addWidget(self.btn_start)
        self.grp_start.setLayout(v_start)
        
        right_layout.addWidget(self.grp_identity)
        right_layout.addWidget(self.grp_history)
        right_layout.addWidget(self.grp_start)
        right_layout.addStretch()
        scroll_area.setWidget(right_content)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(scroll_area)
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter)

    def _create_menu_bar(self):
        menu = self.menuBar()
        f_menu = menu.addMenu("Fichier")
        f_menu.addAction("Quitter", self.close, "Ctrl+Q")
        o_menu = menu.addMenu("Options")
        o_menu.addAction("Réglages...", lambda: SettingsDialog(self, self.config_manager).exec())
        h_menu = menu.addMenu("Aide")
        h_menu.addAction("À propos", lambda: QMessageBox.about(self, "About", "PLR Vet"))

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background: #f0f2f5; font-size: 10pt; }
            QGroupBox { background: white; border: 1px solid #ccc; font-weight: bold; margin-top: 10px; }
            QLineEdit, QComboBox, QDateEdit { padding: 5px; background: #fff; border: 1px solid #ccc; }
            QPushButton { padding: 6px; border-radius: 4px; border: 1px solid #ccc; background: #e2e6ea; }
            QPushButton:hover { background: #dbe2ef; }
        """)

    def load_patients(self):
        query = self.search_bar.text()
        patients = self.db.search_patients(query)
        self.table.setRowCount(0)
        for row, p in enumerate(patients):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(p['name']))
            self.table.setItem(row, 1, QTableWidgetItem(p['species']))
            self.table.setItem(row, 2, QTableWidgetItem(p['tattoo_id']))
            self.table.item(row, 0).setData(Qt.UserRole, p)

    def on_patient_clicked(self, item):
        p = self.table.item(item.row(), 0).data(Qt.UserRole)
        self.current_patient_id = p['id']
        self.inp_name.setText(p['name'])
        self.inp_tattoo.setText(p['tattoo_id'])
        self.combo_species.setCurrentText(p['species'])
        self.inp_breed.setText(p['breed'])
        self.txt_notes.setText(p['notes'])
        if p['gender']=='F': self.rad_f.setChecked(True)
        else: self.rad_m.setChecked(True)
        if p['birth_date']: self.date_dob.setDate(QDate.fromString(p['birth_date'], "yyyy-MM-dd"))
        
        self.grp_identity.setTitle(f"👤 Édition : {p['name']}")
        self.btn_save.setText("💾 Mettre à jour")
        self.btn_delete.setVisible(True)
        self.btn_start.setEnabled(True)
        self.load_history(p['id'])

    def mode_create_new(self):
        self.current_patient_id = None
        self.inp_name.clear()
        self.inp_tattoo.clear()
        self.inp_breed.clear()
        self.txt_notes.clear()
        self.table.clearSelection()
        self.grp_identity.setTitle("✨ Nouveau Patient")
        self.btn_save.setText("💾 Créer Fiche")
        self.btn_delete.setVisible(False)
        self.btn_start.setEnabled(False)
        self.table_history.setRowCount(0)

    def load_history(self, pid):
        exams = self.db.get_patient_history(pid)
        self.table_history.setRowCount(0)
        for row, ex in enumerate(exams):
            self.table_history.insertRow(row)
            d = ex['exam_date'].split(" ")[0]
            lat = ex.get('laterality', '??')
            
            item_lat = QTableWidgetItem(lat)
            if lat == 'OD': item_lat.setForeground(QColor('#d32f2f'))
            elif lat == 'OG': item_lat.setForeground(QColor('#1976d2'))
            item_lat.setTextAlignment(Qt.AlignCenter)
            
            self.table_history.setItem(row, 0, QTableWidgetItem(d))
            self.table_history.setItem(row, 1, item_lat)
            self.table_history.setItem(row, 2, QTableWidgetItem(ex.get('exam_type', 'PLR')))
            btn = QPushButton("👁️")
            btn.clicked.connect(lambda ch, e=ex: self.view_exam(e))
            self.table_history.setCellWidget(row, 3, btn)

    def save_patient(self):
        # 1. RÉCUPÉRATION
        name = self.inp_name.text().strip()
        tattoo = self.inp_tattoo.text().strip()
        
        # 2. VALIDATION (Message d'erreur)
        if not name or not tattoo:
            QMessageBox.warning(self, "Champs manquants", 
                                "Impossible d'enregistrer.\n\nVeuillez remplir obligatoirement :\n- Le Nom\n- L'Identifiant (Puce/Tatouage)")
            return

        gender = "M" if self.rad_m.isChecked() else "F"
        dob = self.date_dob.date().toString("yyyy-MM-dd")
        
        # 3. SAUVEGARDE
        if self.current_patient_id is None:
            pid = self.db.add_patient(tattoo, name, self.combo_species.currentText(),
                                    self.inp_breed.text(), gender, dob, notes=self.txt_notes.toPlainText())
            if pid != -1:
                QMessageBox.information(self, "Succès", "Patient créé avec succès.")
                self.load_patients()
                # On recharge pour activer le mode édition
                self.mode_create_new() 
            else:
                QMessageBox.critical(self, "Erreur", "Cet identifiant (Puce/Tatouage) existe déjà !")
        else:
            self.db.update_patient(self.current_patient_id, name, self.combo_species.currentText(),
                                  self.inp_breed.text(), gender, dob, self.txt_notes.toPlainText())
            self.load_patients()
            QMessageBox.information(self, "Succès", "Fiche mise à jour.")

    def delete_patient(self):
        if self.current_patient_id:
            if QMessageBox.question(self, "Sur ?", "Voulez-vous vraiment supprimer ce patient et tout son historique ?") == QMessageBox.Yes:
                self.db.delete_patient(self.current_patient_id)
                self.load_patients()
                self.mode_create_new()

    def view_exam(self, exam):
        try:
            df = pd.read_csv(exam['csv_path'])
            results = exam.get('results_data', {})
            title = f"Examen du {exam['exam_date']} - {exam.get('laterality', '')}"
            d = PLRResultsDialog(self, data=df, results=results, title=title)
            d.exec()
        except: pass

    def calculate_age(self):
        dob = self.date_dob.date().toPython()
        d = relativedelta(datetime.now().date(), dob)
        self.lbl_age.setText(f"({d.years} ans, {d.months} mois)")

    def start_exam_process(self):
        if not self.current_patient_id: return
        p_data = {
            'id': self.current_patient_id,
            'name': self.inp_name.text(),
            'tattoo_id': self.inp_tattoo.text(),
            'species': self.combo_species.currentText()
        }
        self.patient_selected.emit(p_data)
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = WelcomeScreen()
    w.show()
    sys.exit(app.exec())