"""
plr_results_viewer.py
=====================
Module de visualisation avancée.
Version: 2.8.1 (Fix: Infobulle disparue après clear() + Labels Français).
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QCheckBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import matplotlib
matplotlib.use('QtAgg')

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

class PLRGraphWidget(QWidget):
    """Widget graphique interactif complet."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.current_data_list = [] 
        self.show_raw = False       
        self.current_df = None      
        self.cursors = [] 
        self.is_erasing = False 
        
        # Toolbar Container
        toolbar_container = QWidget()
        tb_layout = QHBoxLayout(toolbar_container)
        tb_layout.setContentsMargins(0, 0, 5, 0)
        
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.axes = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor('white')
        self.axes.set_facecolor('#f8f9fa')
        
        # Initialisation de l'annotation (sera recréée à chaque clear)
        self.hover_annot = None
        self._init_annotation()
        
        self.mpl_toolbar = NavigationToolbar(self.canvas, self)
        self.chk_raw = QCheckBox("Voir Bruit (Brut)")
        self.chk_raw.setStyleSheet("font-weight: bold; color: #555;")
        self.chk_raw.toggled.connect(self.set_show_raw)
        
        tb_layout.addWidget(self.mpl_toolbar)
        tb_layout.addStretch()
        tb_layout.addWidget(self.chk_raw)
        
        layout.addWidget(toolbar_container)
        layout.addWidget(self.canvas)
        
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_hover)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_click)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)

    def _init_annotation(self):
        """Crée l'objet annotation (Invisible par défaut)."""
        self.hover_annot = self.axes.annotate(
            "", xy=(0,0), xytext=(15,15), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#333", alpha=0.9),
            arrowprops=None
        )
        self.hover_annot.set_visible(False)

    def set_show_raw(self, enabled: bool):
        self.show_raw = enabled
        if self.current_data_list: self.refresh_plot(clear=True)

    def plot_data(self, data_list: List[Dict], clear=True):
        self.current_data_list = data_list
        self.refresh_plot(clear)

    def refresh_plot(self, clear=True):
        if clear:
            self.axes.clear()
            self.axes.grid(True, linestyle=':', alpha=0.6)
            self.axes.set_xlabel("Temps (s)"); self.axes.set_ylabel("Diamètre (mm)")
            self.cursors = []; self.current_df = None
            
            # --- CRITIQUE : On recrée l'annotation car clear() l'a supprimée ---
            self._init_annotation()
            # On supprime l'affichage des coordonnées dans la toolbar
            self.axes.format_coord = lambda x, y: "" 
            # -------------------------------------------------------------------

        for i, item in enumerate(self.current_data_list):
            df = item['df']
            if df is None or df.empty: continue
            if self.current_df is None and i == 0: self.current_df = df
            t = df['timestamp_s']
            
            if self.show_raw: self.axes.plot(t, df['diameter_mm'], color='#999999', linewidth=1, alpha=0.4, label='_nolegend_')
            self.axes.plot(t, df.get('diameter_smooth', df['diameter_mm']), label=item.get('label',''), color=item.get('color'), linestyle=item.get('style','-'), linewidth=2)
            
            metrics = item.get('metrics', {})
            ft = metrics.get('flash_timestamp', item.get('flash_timestamp'))
            if ft:
                self.axes.axvline(x=ft, color='#ff9800', linestyle='-', linewidth=1.5)
                dur = metrics.get('flash_duration_s', 0.2)
                self.axes.axvspan(ft, ft + dur, color='#ffeb3b', alpha=0.2, label='_nolegend_')
                if i==0: 
                    yl=self.axes.get_ylim(); self.axes.text(ft, yl[1]-(yl[1]-yl[0])*0.05, "FLASH", color='#e65100', fontsize=8, rotation=90, verticalalignment='top')

        handles, labels = self.axes.get_legend_handles_labels()
        if labels:
            unique = [(h, l) for i, (h, l) in enumerate(zip(handles, labels)) if l not in labels[:i]]
            self.axes.legend(*zip(*unique), loc='upper right', fontsize='small')
        self.canvas.draw()

    # --- SOURIS / CURSEUR LIVE ---
    def on_mouse_hover(self, event):
        if event.inaxes != self.axes or self.mpl_toolbar.mode:
            if self.hover_annot: self.hover_annot.set_visible(False)
            self.canvas.draw_idle()
            return

        if self.is_erasing:
            self.check_and_erase(event.xdata)
            if self.hover_annot: self.hover_annot.set_visible(False)
            self.canvas.draw_idle()
            return

        # LOGIQUE LIVE CURSOR (Sur la souris)
        if self.current_df is not None and self.hover_annot:
            # 1. Snapping sur la courbe
            t_col = self.current_df['timestamp_s']
            idx = (np.abs(t_col - event.xdata)).argmin()
            t_snap = t_col.iloc[idx]
            d_val = self.current_df.get('diameter_smooth', self.current_df['diameter_mm']).iloc[idx]
            
            # 2. Position : Sur la souris
            self.hover_annot.xy = (event.xdata, event.ydata)
            
            # 3. Texte Français
            self.hover_annot.set_text(f"Temps : {t_snap:.2f} s\nDiamètre : {d_val:.2f} mm")
            
            # 4. Positionnement intelligent
            xlim = self.axes.get_xlim()
            if event.xdata > (xlim[0] + xlim[1]) / 2:
                self.hover_annot.xytext = (-20, 20) # Gauche
                self.hover_annot.set_horizontalalignment('right')
            else:
                self.hover_annot.xytext = (20, 20) # Droite
                self.hover_annot.set_horizontalalignment('left')

            self.hover_annot.set_visible(True)
            self.canvas.draw_idle()

    def on_mouse_click(self, event):
        if event.inaxes != self.axes or self.mpl_toolbar.mode: return
        if event.button == 1: self.add_persistent_cursor(event.xdata)
        elif event.button == 3:
            self.is_erasing = True; self.setCursor(Qt.ForbiddenCursor); self.check_and_erase(event.xdata)

    def on_mouse_release(self, event):
        if event.button == 3: self.is_erasing=False; self.setCursor(Qt.ArrowCursor)

    def check_and_erase(self, mouse_x):
        if not self.cursors or mouse_x is None: return
        tol = (self.axes.get_xlim()[1] - self.axes.get_xlim()[0]) * 0.015
        to_del = None
        for c in self.cursors:
            if abs(c[0].get_xdata()[0] - mouse_x) < tol: to_del = c; break
        if to_del: self.remove_specific_cursor(to_del)

    def add_persistent_cursor(self, x_click):
        if self.current_df is None: return
        t_col = self.current_df['timestamp_s']
        idx = (np.abs(t_col - x_click)).argmin()
        t_snap = t_col.iloc[idx]
        d_val = self.current_df.get('diameter_smooth', self.current_df['diameter_mm']).iloc[idx]

        l = self.axes.axvline(x=t_snap, color='#e74c3c', linestyle='-', linewidth=1)
        
        xlim=self.axes.get_xlim(); ylim=self.axes.get_ylim()
        mid_x=(xlim[0]+xlim[1])/2; mid_y=(ylim[0]+ylim[1])/2
        ha='right' if t_snap>mid_x else 'left'; va='top' if d_val>mid_y else 'bottom'
        off_x=-20 if ha=='right' else 20; off_y=-20 if va=='top' else 20

        an = self.axes.annotate(f" {t_snap:.2f} s \n {d_val:.2f} mm ", xy=(t_snap,d_val), xytext=(off_x,off_y), textcoords="offset points", 
                                color='white', fontsize=9, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="#e74c3c", ec="none", alpha=0.8),
                                horizontalalignment=ha, verticalalignment=va, arrowprops=dict(arrowstyle="-", color='#e74c3c'))
        dt, = self.axes.plot(t_snap, d_val, 'o', color='#e74c3c', markersize=5)
        self.cursors.append((l, an, dt))
        self.canvas.draw()

    def remove_specific_cursor(self, c):
        for e in c: e.remove()
        if c in self.cursors: self.cursors.remove(c)
        self.canvas.draw()
    def clear_all_cursors(self):
        for c in list(self.cursors): self.remove_specific_cursor(c)

class PLRResultsDialog(QDialog):
    def __init__(self, parent=None, data=None, results=None, title="Détail Examen"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1100, 750)
        
        layout = QVBoxLayout(self)
        lbl_info = QLabel("<i>💡 Clic Gauche : Poser curseur | Maintenir Clic Droit : Gommer</i>")
        lbl_info.setStyleSheet("color: #666; margin-bottom: 5px;")
        layout.addWidget(lbl_info)
        
        self.graph = PLRGraphWidget()
        curve_data = {'label': 'Examen', 'df': data, 'metrics': results, 'color': '#007bff'}
        self.graph.plot_data([curve_data])
        layout.addWidget(self.graph, stretch=3)
        
        h_btn = QHBoxLayout()
        btn_clean = QPushButton("🗑️ Effacer curseurs")
        btn_clean.setFixedWidth(150)
        btn_clean.clicked.connect(self.graph.clear_all_cursors)
        h_btn.addWidget(btn_clean); h_btn.addStretch()
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