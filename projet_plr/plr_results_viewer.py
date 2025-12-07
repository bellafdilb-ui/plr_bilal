"""
plr_results_viewer.py
=====================
Module de visualisation avancée (Outils de Recherche).
Version: 2.4.0 (Fix: Conflit Zoom/Curseurs)

Fonctionnalités :
- Graphique interactif
- Curseurs intelligents
- Protection : Pas de curseur si Zoom/Pan actif
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCursor

import matplotlib
matplotlib.use('QtAgg')

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

class PLRGraphWidget(QWidget):
    """Widget graphique interactif avec curseurs de recherche."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Données actives
        self.current_df = None
        self.cursors = [] 
        self.is_erasing = False 
        
        # Figure setup
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.axes = self.fig.add_subplot(111)
        
        # Style
        self.fig.patch.set_facecolor('white')
        self.axes.set_facecolor('#f8f9fa')
        self.axes.grid(True, linestyle=':', alpha=0.6)
        
        # Toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Événements Souris
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_hover)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_click)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        
        # Annotation flottante (survol)
        self.hover_annot = self.axes.annotate(
            "", xy=(0,0), xytext=(15,15), textcoords="offset points",
            bbox=dict(boxstyle="round", fc="w", alpha=0.8),
            arrowprops=dict(arrowstyle="->")
        )
        self.hover_annot.set_visible(False)

    def plot_data(self, data_list: List[Dict], clear=True):
        """Trace les courbes."""
        if clear:
            self.axes.clear()
            self.axes.grid(True, linestyle=':', alpha=0.6)
            self.axes.set_xlabel("Temps (s)")
            self.axes.set_ylabel("Diamètre (mm)")
            self.cursors = [] 
            self.current_df = None

        for i, item in enumerate(data_list):
            df = item['df']
            label = item.get('label', 'Courbe')
            color = item.get('color', None)
            style = item.get('style', '-')
            
            if df is None or df.empty:
                continue

            if self.current_df is None and i == 0:
                self.current_df = df

            t = df['timestamp_s']
            y = df.get('diameter_smooth', df['diameter_mm'])
            
            self.axes.plot(t, y, label=label, color=color, linestyle=style, linewidth=2)
            
            metrics = item.get('metrics', {})
            if 'flash_timestamp' in metrics:
                ft = metrics['flash_timestamp']
                self.axes.axvline(x=ft, color='orange', linestyle='--', alpha=0.5, label='Flash')
        
        handles, labels = self.axes.get_legend_handles_labels()
        if labels:
            self.axes.legend(loc='upper right', fontsize='small')
        
        self.canvas.draw()

    def on_mouse_hover(self, event):
        """Gère le survol et la gomme."""
        if event.inaxes != self.axes:
            if self.hover_annot.get_visible():
                self.hover_annot.set_visible(False)
                self.canvas.draw_idle()
            return

        # Si un outil Zoom/Pan est actif, on ne fait rien (ni gomme, ni bulle)
        if self.toolbar.mode: 
            return

        if self.is_erasing:
            self.check_and_erase(event.xdata)
            self.hover_annot.set_visible(False)
            return

        # Logique Bulle Info (Hover)
        x, y = event.xdata, event.ydata
        self.hover_annot.xy = (x, y)
        self.hover_annot.set_text(f"t={x:.2f}s\nØ={y:.2f}mm")
        
        # Positionnement Intelligent 4 quadrants
        xlim = self.axes.get_xlim()
        ylim = self.axes.get_ylim()
        mid_x = (xlim[0] + xlim[1]) / 2
        mid_y = (ylim[0] + ylim[1]) / 2
        
        offset_x = -15 if x > mid_x else 15
        offset_y = -15 if y > mid_y else 15
        
        ha = 'right' if x > mid_x else 'left'
        va = 'top' if y > mid_y else 'bottom'
        
        self.hover_annot.set_position((offset_x, offset_y))
        self.hover_annot.set_horizontalalignment(ha)
        self.hover_annot.set_verticalalignment(va)
        
        self.hover_annot.set_visible(True)
        self.canvas.draw_idle()

    def on_mouse_click(self, event):
        # 1. Vérif standard
        if event.inaxes != self.axes: return
        
        # 2. VÉRIFICATION CRITIQUE : Est-ce qu'un outil (Zoom/Pan) est actif ?
        # self.toolbar.mode contient une chaine ("Zoom to rect", "Pan/Zoom") ou "" si inactif
        if self.toolbar.mode: 
            return # On laisse Matplotlib gérer le zoom/pan, on ne pose pas de curseur

        if event.button == 1: 
            self.add_persistent_cursor(event.xdata)
        elif event.button == 3:
            self.is_erasing = True
            self.setCursor(Qt.ForbiddenCursor)
            self.check_and_erase(event.xdata)

    def on_mouse_release(self, event):
        if event.button == 3:
            self.is_erasing = False
            self.setCursor(Qt.ArrowCursor)

    def check_and_erase(self, mouse_x):
        if not self.cursors or mouse_x is None: return
        xlim = self.axes.get_xlim()
        tolerance = (xlim[1] - xlim[0]) * 0.015
        
        cursor_to_remove = None
        for c in self.cursors:
            line, text, dot = c
            line_x = line.get_xdata()[0]
            if abs(line_x - mouse_x) < tolerance:
                cursor_to_remove = c
                break
        
        if cursor_to_remove:
            self.remove_specific_cursor(cursor_to_remove)

    def add_persistent_cursor(self, x_click):
        """Ajoute un curseur vertical fixe (Positionnement Intelligent)."""
        if self.current_df is None: return

        # Snapping
        t_col = self.current_df['timestamp_s']
        idx = (np.abs(t_col - x_click)).argmin()
        t_snap = t_col.iloc[idx]
        d_val = self.current_df.get('diameter_smooth', self.current_df['diameter_mm']).iloc[idx]

        # Dessin ligne
        line = self.axes.axvline(x=t_snap, color='#e74c3c', linestyle='-', linewidth=1)
        
        # Logique de positionnement
        xlim = self.axes.get_xlim()
        ylim = self.axes.get_ylim()
        mid_x = (xlim[0] + xlim[1]) / 2
        mid_y = (ylim[0] + ylim[1]) / 2
        
        # 1. Horizontal
        if t_snap > mid_x:
            ha = 'right'
            offset_x = -20
        else:
            ha = 'left'
            offset_x = 20

        # 2. Vertical
        if d_val > mid_y:
            va = 'top'
            offset_y = -20 
        else:
            va = 'bottom'
            offset_y = 20

        annot = self.axes.annotate(
            f" {t_snap:.2f}s \n {d_val:.2f}mm ",
            xy=(t_snap, d_val),
            xytext=(offset_x, offset_y),
            textcoords="offset points",
            color='white', fontsize=9, fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.3", fc="#e74c3c", ec="none", alpha=0.8),
            horizontalalignment=ha,
            verticalalignment=va,
            arrowprops=dict(arrowstyle="-", color='#e74c3c')
        )
        
        dot, = self.axes.plot(t_snap, d_val, 'o', color='#e74c3c', markersize=5)

        self.cursors.append((line, annot, dot))
        self.canvas.draw()

    def remove_specific_cursor(self, cursor_tuple):
        line, text, dot = cursor_tuple
        line.remove()
        text.remove()
        dot.remove()
        if cursor_tuple in self.cursors:
            self.cursors.remove(cursor_tuple)
        self.canvas.draw()
        
    def clear_all_cursors(self):
        for c in list(self.cursors):
            self.remove_specific_cursor(c)


# --- FENÊTRE DE CONSULTATION ---
class PLRResultsDialog(QDialog):
    def __init__(self, parent=None, data=None, results=None, title="Détail Examen"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1100, 750)
        
        layout = QVBoxLayout(self)
        
        lbl_info = QLabel("<i>💡 Clic Gauche : Poser curseur | Maintenir Clic Droit : Gommer curseur</i>")
        lbl_info.setStyleSheet("color: #666; margin-bottom: 5px;")
        layout.addWidget(lbl_info)
        
        self.graph = PLRGraphWidget()
        curve_data = {
            'label': 'Examen Actuel',
            'df': data,
            'metrics': results,
            'color': '#007bff'
        }
        self.graph.plot_data([curve_data])
        layout.addWidget(self.graph, stretch=3)
        
        h_btn = QHBoxLayout()
        btn_clean = QPushButton("🗑️ Effacer tous les curseurs")
        btn_clean.setFixedWidth(200)
        btn_clean.clicked.connect(self.graph.clear_all_cursors)
        h_btn.addWidget(btn_clean)
        h_btn.addStretch()
        layout.addLayout(h_btn)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Métrique", "Valeur"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, stretch=1)
        
        if results:
            self.table.setRowCount(len(results))
            for i, (k, v) in enumerate(results.items()):
                self.table.setItem(i, 0, QTableWidgetItem(str(k)))
                self.table.setItem(i, 1, QTableWidgetItem(str(v)))