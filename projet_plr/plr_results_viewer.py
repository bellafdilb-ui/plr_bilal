"""
plr_results_viewer.py
=====================
Module de visualisation des résultats PLR.
Version: 1.1.0 (Ajout visualisation Flash)

Responsabilités :
- Affichage graphique des courbes pupillométriques (Matplotlib)
- Présentation synthétique des métriques (Tableau)
- Export des graphiques (PNG/PDF)
"""

import sys
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import matplotlib
# Utilisation du backend Qt pour intégrer Matplotlib à PySide6
matplotlib.use('QtAgg')

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# Configuration logger
logger = logging.getLogger(__name__)


class MplCanvas(FigureCanvas):
    """Canvas Matplotlib personnalisé pour l'intégration Qt."""
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Configuration du style par défaut (Thème clair)
        self.fig.patch.set_facecolor('white')
        self.axes.set_facecolor('#f8f9fa')  # Gris très léger pour la zone de traçage


class PLRResultsViewer(QDialog):
    """
    Fenêtre de visualisation des résultats d'un test PLR.
    
    Affiche:
    - Graphique interactif (Diamètre vs Temps)
    - Tableau des métriques
    """
    
    def __init__(self, parent=None, data: pd.DataFrame = None, results: Dict[str, Any] = None):
        super().__init__(parent)
        self.setWindowTitle("Résultats d'Analyse PLR")
        self.setMinimumSize(1000, 700)
        
        # Données
        self.data = data
        self.results = results or {}
        
        # Interface
        self.setup_ui()
        self.apply_stylesheet()
        
        # Si données fournies à l'init, on affiche
        if self.data is not None and not self.data.empty:
            self.plot_results()
            self.fill_metrics_table()

    def setup_ui(self):
        """Construction de l'interface."""
        layout = QVBoxLayout(self)
        
        # === ZONE HAUTE : GRAPHIQUE ===
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        
        # Canvas Matplotlib
        self.canvas = MplCanvas(self, width=8, height=6, dpi=100)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        graph_layout.addWidget(self.toolbar)
        graph_layout.addWidget(self.canvas)
        
        layout.addWidget(graph_container, stretch=2)
        
        # === ZONE BASSE : MÉTRIQUES & ACTIONS ===
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        
        # 1. Tableau des métriques (à gauche)
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Métrique", "Valeur"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        
        bottom_layout.addWidget(self.table, stretch=1)
        
        # 2. Boutons d'action (à droite)
        actions_frame = QFrame()
        actions_layout = QVBoxLayout(actions_frame)
        
        self.btn_export_png = QPushButton("📸 Exporter Graphique")
        self.btn_export_png.clicked.connect(self.export_graph)
        
        self.btn_export_pdf = QPushButton("📄 Rapport PDF")
        self.btn_export_pdf.setEnabled(False)  # À implémenter plus tard
        self.btn_export_pdf.setToolTip("Génération de rapport PDF (Bientôt disponible)")
        
        self.btn_close = QPushButton("Fermer")
        self.btn_close.clicked.connect(self.accept)
        
        actions_layout.addWidget(QLabel("<b>Actions</b>"))
        actions_layout.addWidget(self.btn_export_png)
        actions_layout.addWidget(self.btn_export_pdf)
        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_close)
        
        bottom_layout.addWidget(actions_frame, stretch=0)
        
        layout.addWidget(bottom_container, stretch=1)

    def apply_stylesheet(self):
        """Applique le style (Thème Clair)."""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            QLabel {
                font-size: 11pt;
            }
            QTableWidget {
                border: 1px solid #cccccc;
                gridline-color: #eeeeee;
                font-size: 10pt;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 4px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
            QPushButton {
                background-color: #e2e6ea;
                border: 1px solid #ccc;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #dbe2ef;
            }
        """)

    def plot_results(self):
        """Trace les courbes sur le canvas Matplotlib."""
        if self.data is None:
            return
            
        ax = self.canvas.axes
        ax.clear()
        
        # Récupération des données
        t = self.data['timestamp_s']
        d_raw = self.data['diameter_mm']
        d_smooth = self.data.get('diameter_smooth', d_raw) # Fallback si pas de lissage
        
        # --- NOUVEAU : Dessin du Flash ---
        if 'flash_timestamp' in self.results and 'flash_duration_s' in self.results:
            t_flash = self.results['flash_timestamp']
            d_flash = self.results['flash_duration_s']
            
            # Zone jaune pour la durée du flash
            ax.axvspan(t_flash, t_flash + d_flash, color='#ffd700', alpha=0.3, label='Flash')
            # Ligne verticale orange pour le début exact
            ax.axvline(x=t_flash, color='#ffa500', linestyle='-', linewidth=1.5)
            
            # Annotation textuelle
            # On place le texte un peu au-dessus du min de la courbe pour qu'il soit visible
            y_pos = d_smooth.max()
            ax.text(t_flash, y_pos, " FLASH", color='#e67e22', fontsize=9, fontweight='bold', rotation=90, verticalalignment='top')

        # ---------------------------------
        
        # 1. Tracé des courbes
        ax.plot(t, d_raw, label='Brut', color='lightgray', linewidth=1, alpha=0.6)
        ax.plot(t, d_smooth, label='Lissé', color='#007bff', linewidth=2)
        
        # 2. Ajout des marqueurs si disponibles dans self.results
        if self.results:
            # Baseline
            if 'baseline_mm' in self.results:
                baseline = self.results['baseline_mm']
                ax.axhline(y=baseline, color='green', linestyle='--', alpha=0.5, label=f'Baseline ({baseline}mm)')
            
            # Min Diameter
            if 'min_diameter_mm' in self.results:
                min_d = self.results['min_diameter_mm']
                # Trouver le temps approximatif du min
                min_idx = self.data['diameter_smooth'].idxmin()
                min_t = self.data.loc[min_idx, 'timestamp_s']
                ax.plot(min_t, min_d, 'ro', label=f'Min ({min_d}mm)')
        
        # 3. Mise en forme
        ax.set_title("Réflexe Photomoteur (PLR)", fontsize=12, fontweight='bold')
        ax.set_xlabel("Temps (s)")
        ax.set_ylabel("Diamètre Pupille (mm)")
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.legend(loc='upper right', fontsize='small')
        
        # Rafraîchissement
        self.canvas.draw()

    def fill_metrics_table(self):
        """Remplit le tableau avec les résultats."""
        if not self.results:
            return
            
        # Mapping des clés techniques vers libellés lisibles
        labels = {
            "baseline_mm": "Diamètre Basal (mm)",
            "min_diameter_mm": "Diamètre Min (mm)",
            "amplitude_mm": "Amplitude (mm)",
            "constriction_percent": "Constriction (%)",
            "latency_s": "Latence (s)",
            "constriction_velocity_mm_s": "Vitesse Constriction (mm/s)",
            "constriction_duration_s": "Durée Constriction (s)"
        }
        
        self.table.setRowCount(len(labels))
        
        for i, (key, label) in enumerate(labels.items()):
            val = self.results.get(key, "--")
            
            # Item Libellé
            item_label = QTableWidgetItem(label)
            item_label.setFlags(Qt.ItemFlag.ItemIsEnabled) # Non éditable
            self.table.setItem(i, 0, item_label)
            
            # Item Valeur
            item_val = QTableWidgetItem(str(val))
            item_val.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_val.setFlags(Qt.ItemFlag.ItemIsEnabled)
            # Mettre en gras
            font = QFont()
            font.setBold(True)
            item_val.setFont(font)
            
            self.table.setItem(i, 1, item_val)

    def export_graph(self):
        """Exporte le graphique en image."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter Graphique", "graph_plr.png", "Images (*.png *.jpg)"
        )
        if filename:
            self.canvas.fig.savefig(filename)
            QMessageBox.information(self, "Export", f"Graphique sauvegardé : {filename}")


# ===========================
# TEST STANDALONE
# ===========================
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    
    # Données simulées pour le test
    t = np.linspace(0, 5, 100)
    d = 5.0 - 2.0 * np.exp(-((t - 1.0)**2) / 0.5) + np.random.normal(0, 0.05, 100)
    df = pd.DataFrame({'timestamp_s': t, 'diameter_mm': d, 'diameter_smooth': d})
    
    res = {
        "baseline_mm": 5.0,
        "min_diameter_mm": 3.0,
        "amplitude_mm": 2.0,
        "latency_s": 0.22,
        "flash_timestamp": 1.0,      # TEST FLASH
        "flash_duration_s": 0.2      # TEST FLASH
    }
    
    app = QApplication(sys.argv)
    viewer = PLRResultsViewer(data=df, results=res)
    viewer.exec()
    sys.exit()