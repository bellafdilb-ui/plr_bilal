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
import cv2
import os
import glob

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QCheckBox, QSpacerItem, QSizePolicy, QSlider, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPixmap

import matplotlib
matplotlib.use('QtAgg')

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
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
        self.display_mode = 'smooth' # 'smooth' ou 'raw'
        self.current_df = None
        self.cursors = []
        self.is_erasing = False

        # Curseur de synchronisation frame/graphique
        self._sync_line = None

        # Navigation (zoom / pan)
        self._is_panning = False
        self._pan_start_px = None
        self._pan_start_xlim = None
        self._pan_start_ylim = None
        self._home_xlim = None
        self._home_ylim = None
        
        # Toolbar Container
        toolbar_container = QWidget()
        toolbar_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        tb_layout = QHBoxLayout(toolbar_container)
        tb_layout.setContentsMargins(0, 0, 5, 0)
        
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.fig.subplots_adjust(left=0.10, right=0.97, top=0.95, bottom=0.10)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.updateGeometry()
        self.axes = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor('white')
        self.axes.set_facecolor('#f8f9fa')
        
        # Initialisation de l'annotation (sera recréée à chaque clear)
        self.hover_annot = None
        self._init_annotation()
        
        # self.mpl_toolbar = NavigationToolbar(self.canvas, self)
        
        self.btn_mode = QPushButton("Mode: LISSÉ")
        self.btn_mode.setCheckable(True); self.btn_mode.setChecked(True)
        self.btn_mode.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px;")
        self.btn_mode.clicked.connect(self.toggle_mode)

        self.btn_reset_view = QPushButton("↺ Vue initiale")
        self.btn_reset_view.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 5px;")
        self.btn_reset_view.setToolTip("Remettre la vue à son état initial (Zoom / Position)")
        self.btn_reset_view.clicked.connect(self.reset_view)

        lbl_nav = QLabel("  Molette: Zoom  |  Clic molette + glisser: Déplacer")
        lbl_nav.setStyleSheet("color: #888; font-size: 10px;")

        # tb_layout.addWidget(self.mpl_toolbar)
        tb_layout.addWidget(lbl_nav)
        tb_layout.addStretch()
        tb_layout.addWidget(self.btn_reset_view)
        tb_layout.addWidget(self.btn_mode)
        
        layout.addWidget(toolbar_container)
        layout.addWidget(self.canvas)
        
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_hover)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_click)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)

    def _init_annotation(self):
        """Crée l'objet annotation (Invisible par défaut)."""
        self.hover_annot = self.axes.annotate(
            "", xy=(0,0), xytext=(15,15), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#333", alpha=0.9),
            arrowprops=None
        )
        self.hover_annot.set_visible(False)

    def toggle_mode(self):
        if self.btn_mode.isChecked():
            self.display_mode = 'smooth'
            self.btn_mode.setText("Mode: LISSÉ")
            self.btn_mode.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px;")
        else:
            self.display_mode = 'raw'
            self.btn_mode.setText("Mode: BRUT")
            self.btn_mode.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 5px;")
        self.refresh_plot(clear=True)

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
            
            # Choix de la colonne selon le mode
            col_name = 'diameter_smooth' if self.display_mode == 'smooth' else 'diameter_mm'
            y_data = df.get(col_name, df['diameter_mm'])
            
            # Style : Points plus visibles en mode brut
            marker_style = '.' if self.display_mode == 'raw' else None
            self.axes.plot(t, y_data, label=item.get('label',''), color=item.get('color'), linestyle=item.get('style','-'), linewidth=1.5, marker=marker_style, markersize=4)
            
            metrics = item.get('metrics', {})
            ft = metrics.get('flash_timestamp', item.get('flash_timestamp'))
            if ft:
                self.axes.axvline(x=ft, color='#ff9800', linestyle='-', linewidth=1.5)
                dur = metrics.get('flash_duration_s', 0.2)
                self.axes.axvspan(ft, ft + dur, color='#ffeb3b', alpha=0.2, label='_nolegend_')
                if i==0: 
                    yl=self.axes.get_ylim(); self.axes.text(ft, yl[1]-(yl[1]-yl[0])*0.05, "FLASH", color='#e65100', fontsize=8, rotation=90, verticalalignment='top')

        # --- ÉCHELLE : marges confortables pour lisibilité ---
        if self.current_data_list:
            all_t, all_y = [], []
            for item in self.current_data_list:
                df = item.get('df')
                if df is None or df.empty: continue
                all_t.extend(df['timestamp_s'].dropna().tolist())
                col = 'diameter_smooth' if self.display_mode == 'smooth' else 'diameter_mm'
                all_y.extend(df.get(col, df['diameter_mm']).dropna().tolist())
            if all_t and all_y:
                t_min, t_max = min(all_t), max(all_t)
                y_min, y_max = min(all_y), max(all_y)
                # Axe X : marge de 0.5s de chaque côté, ticks entiers
                self.axes.set_xlim(t_min - 0.5, t_max + 0.5)
                from matplotlib.ticker import MultipleLocator
                self.axes.xaxis.set_major_locator(MultipleLocator(1.0))
                self.axes.xaxis.set_minor_locator(MultipleLocator(0.5))
                # Axe Y : marge de 1mm au-dessus et en-dessous (atténue les micro-variations)
                self.axes.set_ylim(y_min - 1.0, y_max + 1.0)
                self.axes.yaxis.set_major_locator(MultipleLocator(1.0))
                self.axes.yaxis.set_minor_locator(MultipleLocator(0.5))

        handles, labels = self.axes.get_legend_handles_labels()
        if labels:
            unique = [(h, l) for i, (h, l) in enumerate(zip(handles, labels)) if l not in labels[:i]]
            self.axes.legend(*zip(*unique), loc='upper right', fontsize='small')
        self.canvas.draw()
        if clear:
            self._sync_line = None
            self._save_home_limits()

    # --- NAVIGATION (ZOOM / PAN / RESET) ---
    def on_scroll(self, event):
        """Zoom centré sur la position de la souris via la molette."""
        if event.inaxes != self.axes or event.xdata is None: return
        factor = 1.15 if event.button == 'up' else 1.0 / 1.15
        xdata, ydata = event.xdata, event.ydata
        xlim = self.axes.get_xlim()
        ylim = self.axes.get_ylim()
        self.axes.set_xlim([xdata - (xdata - xlim[0]) / factor, xdata + (xlim[1] - xdata) / factor])
        self.axes.set_ylim([ydata - (ydata - ylim[0]) / factor, ydata + (ylim[1] - ydata) / factor])
        self.canvas.draw_idle()

    def _save_home_limits(self):
        """Mémorise les limites actuelles comme vue de référence (reset)."""
        self._home_xlim = self.axes.get_xlim()
        self._home_ylim = self.axes.get_ylim()

    def reset_view(self):
        """Restaure la vue initiale du graphique."""
        if self._home_xlim and self._home_ylim:
            self.axes.set_xlim(self._home_xlim)
            self.axes.set_ylim(self._home_ylim)
            self.canvas.draw_idle()

    def set_sync_cursor(self, t: float):
        """Affiche un curseur bleu pointillé sur le graphique à la position t (synchronisation film)."""
        if self._sync_line is not None:
            try: self._sync_line.remove()
            except: pass
            self._sync_line = None
        if t is not None and self.current_df is not None:
            self._sync_line = self.axes.axvline(
                x=t, color='#1976d2', linestyle='--', linewidth=1.5, alpha=0.85)
        self.canvas.draw_idle()

    # --- SOURIS / CURSEUR LIVE ---
    def on_mouse_hover(self, event):
        # PAN : déplacement avec clic molette maintenu
        if self._is_panning:
            if event.x is None or self._pan_start_px is None: return
            bbox = self.axes.get_window_extent()
            if bbox.width == 0 or bbox.height == 0: return
            dx_px = event.x - self._pan_start_px[0]
            dy_px = event.y - self._pan_start_px[1]
            xlim = self._pan_start_xlim
            ylim = self._pan_start_ylim
            dx = -dx_px * (xlim[1] - xlim[0]) / bbox.width
            dy = -dy_px * (ylim[1] - ylim[0]) / bbox.height
            self.axes.set_xlim([xlim[0] + dx, xlim[1] + dx])
            self.axes.set_ylim([ylim[0] + dy, ylim[1] + dy])
            self.canvas.draw_idle()
            return

        if event.inaxes != self.axes: # or self.mpl_toolbar.mode:
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
            col_name = 'diameter_smooth' if self.display_mode == 'smooth' else 'diameter_mm'
            d_val = self.current_df.get(col_name, self.current_df['diameter_mm']).iloc[idx]
            
            # 2. Position : Sur la souris
            self.hover_annot.xy = (event.xdata, event.ydata)
            
            # 3. Texte Français
            self.hover_annot.set_text(f"Temps : {t_snap:.2f} s\nDiamètre : {d_val:.1f} mm")
            
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
        if event.inaxes != self.axes: return # or self.mpl_toolbar.mode: return
        if event.button == 2:  # Clic molette → début du pan
            self._is_panning = True
            self._pan_start_px = (event.x, event.y)
            self._pan_start_xlim = list(self.axes.get_xlim())
            self._pan_start_ylim = list(self.axes.get_ylim())
            self.setCursor(Qt.SizeAllCursor)
        elif event.button == 1:
            self.add_persistent_cursor(event.xdata)
        elif event.button == 3:
            self.is_erasing = True; self.setCursor(Qt.ForbiddenCursor); self.check_and_erase(event.xdata)

    def on_mouse_release(self, event):
        if event.button == 2:  # Fin du pan
            self._is_panning = False
            self._pan_start_px = None
            self.setCursor(Qt.ArrowCursor)
        elif event.button == 3:
            self.is_erasing = False; self.setCursor(Qt.ArrowCursor)

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
        col_name = 'diameter_smooth' if self.display_mode == 'smooth' else 'diameter_mm'
        d_val = self.current_df.get(col_name, self.current_df['diameter_mm']).iloc[idx]

        l = self.axes.axvline(x=t_snap, color='#e74c3c', linestyle='-', linewidth=1)
        
        xlim=self.axes.get_xlim(); ylim=self.axes.get_ylim()
        mid_x=(xlim[0]+xlim[1])/2; mid_y=(ylim[0]+ylim[1])/2
        ha='right' if t_snap>mid_x else 'left'; va='top' if d_val>mid_y else 'bottom'
        off_x=-20 if ha=='right' else 20; off_y=-20 if va=='top' else 20

        an = self.axes.annotate(f" {t_snap:.2f} s \n {d_val:.1f} mm ", xy=(t_snap,d_val), xytext=(off_x,off_y), textcoords="offset points", 
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

    def clear(self):
        """Nettoie complètement le graphique et réinitialise les données."""
        self.current_data_list = []
        self.refresh_plot(clear=True)

class VideoPlayerWidget(QWidget):
    """Lecteur frame par frame avec horodatage et detection de frame noire (flash IR)."""

    frame_changed = Signal(float)  # Emet le timestamp_s de la frame affichee

    def __init__(self, video_path, df=None):
        super().__init__()
        self.video_path = video_path
        self.df = df          # DataFrame CSV pour recuperer le timestamp de chaque frame
        self.mode = "unknown"
        self.image_files = []
        self.cap = None
        self.setFocusPolicy(Qt.StrongFocus)

        if os.path.isdir(video_path):
            self.mode = "images"
            self.image_files = sorted(glob.glob(os.path.join(video_path, "*.jpg")))
            self.total_frames = len(self.image_files)
        else:
            self.mode = "video"
            self.cap = cv2.VideoCapture(video_path)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.lbl_video = QLabel("Film non disponible")
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setMinimumSize(320, 240)
        self.lbl_video.setStyleSheet("background: black; border: 1px solid #555;")
        layout.addWidget(self.lbl_video)

        # Barre de navigation
        ctrl_layout = QHBoxLayout()
        btn_prev = QPushButton("◀"); btn_prev.setFixedWidth(30)
        btn_prev.clicked.connect(lambda: self.slider.setValue(self.slider.value() - 1))
        btn_next = QPushButton("▶"); btn_next.setFixedWidth(30)
        btn_next.clicked.connect(lambda: self.slider.setValue(self.slider.value() + 1))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, max(0, self.total_frames - 1))
        self.slider.valueChanged.connect(self.seek_frame)
        self.lbl_frame = QLabel("—")
        self.lbl_frame.setMinimumWidth(200)
        ctrl_layout.addWidget(btn_prev)
        ctrl_layout.addWidget(self.slider)
        ctrl_layout.addWidget(btn_next)
        ctrl_layout.addWidget(self.lbl_frame)
        layout.addLayout(ctrl_layout)

        # Barre de detection frame noire
        act_layout = QHBoxLayout()
        self.btn_black = QPushButton("Trouver frame noire (flash IR)")
        self.btn_black.setToolTip(
            "Recherche la premiere frame totalement sombre.\n"
            "Correspond au moment de coupure de l'eclairage IR (= instant du flash).")
        self.btn_black.setStyleSheet(
            "background:#e67e22; color:white; padding:4px; border-radius:3px; font-weight:bold;")
        self.btn_black.clicked.connect(self._find_black_frame)
        self.lbl_black_status = QLabel("")
        self.lbl_black_status.setStyleSheet("color:#e67e22; font-weight:bold;")
        act_layout.addWidget(self.btn_black)
        act_layout.addWidget(self.lbl_black_status)
        act_layout.addStretch()
        layout.addLayout(act_layout)

        lbl_tip = QLabel("Fleches gauche / droite du clavier : frame precedente / suivante")
        lbl_tip.setStyleSheet("color:#aaa; font-size:9px;")
        layout.addWidget(lbl_tip)

        if self.total_frames > 0:
            self.seek_frame(0)

    def seek_frame(self, frame_idx):
        frame = None
        if self.mode == "images":
            if 0 <= frame_idx < len(self.image_files):
                frame = cv2.imread(self.image_files[frame_idx])
        elif self.mode == "video":
            if self.cap and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, f = self.cap.read()
                if ret: frame = f

        if frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            self.lbl_video.setPixmap(
                QPixmap.fromImage(img).scaled(
                    self.lbl_video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Horodatage : frame N → ligne N du CSV
        timestamp = None
        if self.df is not None and not self.df.empty and frame_idx < len(self.df):
            timestamp = float(self.df['timestamp_s'].iat[frame_idx])

        ts_str = f"   t = {timestamp:.3f} s" if timestamp is not None else ""
        self.lbl_frame.setText(f"Frame {frame_idx + 1} / {self.total_frames}{ts_str}")

        if timestamp is not None:
            self.frame_changed.emit(timestamp)

    def _find_black_frame(self):
        """Recherche la premiere frame sombre : coupure IR = instant du flash."""
        if self.mode == "images" and self.image_files:
            for i, path in enumerate(self.image_files):
                gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if gray is not None and np.mean(gray) < 15:
                    self.lbl_black_status.setText(f"Frame noire : #{i + 1}")
                    self.slider.setValue(i)
                    return
        elif self.mode == "video" and self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            min_brightness = 999.0
            min_idx = -1
            for i in range(self.total_frames):
                ret, frame = self.cap.read()
                if not ret:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
                avg = np.mean(gray)
                if avg < min_brightness:
                    min_brightness = avg
                    min_idx = i
            print(f"[BLACK FRAME] Luminosité min = {min_brightness:.1f} à frame #{min_idx + 1}")
            if min_brightness < 40:
                self.lbl_black_status.setText(f"Frame noire : #{min_idx + 1} (lum={min_brightness:.0f})")
                self.slider.setValue(min_idx)
                return
        else:
            self.lbl_black_status.setText("Non disponible")
            return
        self.lbl_black_status.setText("Aucune frame noire trouvee")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.slider.setValue(max(0, self.slider.value() - 1))
        elif event.key() == Qt.Key_Right:
            self.slider.setValue(min(self.total_frames - 1, self.slider.value() + 1))
        else:
            super().keyPressEvent(event)

class PLRResultsDialog(QDialog):
    def __init__(self, parent=None, data=None, results=None, title="Détail Examen", video_path=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1200, 800)
        
        main_layout = QHBoxLayout(self)
        
        # COLONNE GAUCHE : Graphique + Tableau
        left_col = QWidget(); left_layout = QVBoxLayout(left_col)
        
        lbl_info = QLabel("<i>💡 Clic Gauche : Poser curseur | Maintenir Clic Droit : Gommer</i>")
        lbl_info.setStyleSheet("color: #666; margin-bottom: 5px;")
        left_layout.addWidget(lbl_info)
        
        self.graph = PLRGraphWidget()
        curve_data = {'label': 'Examen', 'df': data, 'metrics': results, 'color': '#007bff'}
        self.graph.plot_data([curve_data])
        left_layout.addWidget(self.graph, stretch=3)
        
        h_btn = QHBoxLayout()
        btn_clean = QPushButton("🗑️ Effacer curseurs")
        btn_clean.setFixedWidth(150)
        btn_clean.clicked.connect(self.graph.clear_all_cursors)
        h_btn.addWidget(btn_clean); h_btn.addStretch()
        left_layout.addLayout(h_btn)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Métrique", "Valeur"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        left_layout.addWidget(self.table, stretch=1)
        
        if results:
            self.table.setRowCount(len(results))
            for i, (k, v) in enumerate(results.items()):
                self.table.setItem(i, 0, QTableWidgetItem(str(k)))
                self.table.setItem(i, 1, QTableWidgetItem(str(v)))
        
        main_layout.addWidget(left_col, stretch=2)
        
        # COLONNE DROITE : Film frame par frame (si dispo)
        if video_path:
            right_col = QGroupBox("Film de l'examen (frame par frame)")
            right_layout = QVBoxLayout(right_col)
            self.player = VideoPlayerWidget(video_path, df=data)
            # Synchronisation : deplacement dans le film → curseur bleu sur le graphique
            self.player.frame_changed.connect(self.graph.set_sync_cursor)
            right_layout.addWidget(self.player)
            right_layout.addStretch()
            main_layout.addWidget(right_col, stretch=1)