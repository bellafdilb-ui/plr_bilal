#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interface Tkinter pour ajuster les paramètres de détection de pupille en temps réel
Compatible avec acquisition_camera_IR.py (shared_params.json)
"""

import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
import logging
from datetime import datetime


class ParameterController:
    """Interface Tkinter pour contrôler les paramètres en temps réel"""
    
    def __init__(self):
        """Initialise le contrôleur standalone"""
        self.logger = logging.getLogger(__name__)
        
        # Fichier de communication (IMPORTANT : même nom que acquisition_camera_IR.py)
        self.param_file = Path("shared_params.json")
        
        # Paramètres par défaut (synchronisés avec acquisition_camera_IR.py)
        self.params = {
            'exposure': -6.0,
            'brightness': 128,
            'contrast': 32,
            'blur_kernel': 5,
            'threshold_value': 50,
            'morph_kernel': 3,
            'morph_iterations': 1,
            'min_area': 300,
            'max_area': 5000,
            'min_circularity': 0.7,
            'roi_x': 200,
            'roi_y': 150,
            'roi_width': 240,
            'roi_height': 180,
            'view_mode': 1,
            'recording': False,
            'shutdown': False
        }
        
        # Charger les paramètres existants
        self._load_parameters()
        
        # Créer l'interface
        self.root = tk.Tk()
        self.root.title("🎛️ Contrôle Caméra IR - Temps Réel")
        self.root.geometry("500x850")
        self.root.resizable(False, False)
        
        # Variables Tkinter
        self.exposure_var = tk.DoubleVar(value=self.params['exposure'])
        self.brightness_var = tk.IntVar(value=self.params['brightness'])
        self.contrast_var = tk.IntVar(value=self.params['contrast'])
        self.blur_var = tk.IntVar(value=self.params['blur_kernel'])
        self.threshold_var = tk.IntVar(value=self.params['threshold_value'])
        self.morph_kernel_var = tk.IntVar(value=self.params['morph_kernel'])
        self.morph_iter_var = tk.IntVar(value=self.params['morph_iterations'])
        self.min_area_var = tk.IntVar(value=self.params['min_area'])
        self.max_area_var = tk.IntVar(value=self.params['max_area'])
        self.min_circ_var = tk.DoubleVar(value=self.params['min_circularity'])
        self.roi_x_var = tk.IntVar(value=self.params['roi_x'])
        self.roi_y_var = tk.IntVar(value=self.params['roi_y'])
        self.roi_w_var = tk.IntVar(value=self.params['roi_width'])
        self.roi_h_var = tk.IntVar(value=self.params['roi_height'])
        self.view_mode_var = tk.IntVar(value=self.params['view_mode'])
        self.recording_var = tk.BooleanVar(value=self.params['recording'])
        
        # Dernière mise à jour
        self.last_update = datetime.now()
        
        # Créer l'interface
        self._create_ui()
        
        # Gestion fermeture
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self.logger.info("✅ Interface standalone initialisée")
    
    def _create_ui(self):
        """Crée l'interface utilisateur"""
        
        # ═══════════════════════════════════════════════════════════
        # TITRE
        # ═══════════════════════════════════════════════════════════
        title_frame = tk.Frame(self.root, bg="#2c3e50", pady=15)
        title_frame.pack(fill=tk.X)
        
        tk.Label(
            title_frame,
            text="🎛️ CONTRÔLE CAMÉRA IR",
            font=("Arial", 16, "bold"),
            bg="#2c3e50",
            fg="white"
        ).pack()
        
        tk.Label(
            title_frame,
            text="Ajustements en temps réel",
            font=("Arial", 10),
            bg="#2c3e50",
            fg="#ecf0f1"
        ).pack()
        
        # ═══════════════════════════════════════════════════════════
        # ZONE DE SCROLL
        # ═══════════════════════════════════════════════════════════
        main_canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # ═══════════════════════════════════════════════════════════
        # SECTION 1 : PARAMÈTRES CAMÉRA
        # ═══════════════════════════════════════════════════════════
        cam_frame = ttk.LabelFrame(scrollable_frame, text="📷 Paramètres Caméra", padding=10)
        cam_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self._create_slider(cam_frame, "Exposition", self.exposure_var, -13, -1, 0.5, 
                           tooltip="Temps d'exposition (valeurs négatives)")
        self._create_slider(cam_frame, "Luminosité", self.brightness_var, 0, 255, 1,
                           tooltip="Ajustement luminosité globale")
        self._create_slider(cam_frame, "Contraste", self.contrast_var, 0, 64, 1,
                           tooltip="Contraste de l'image")
        
        # ═══════════════════════════════════════════════════════════
        # SECTION 2 : PRÉTRAITEMENT
        # ═══════════════════════════════════════════════════════════
        preproc_frame = ttk.LabelFrame(scrollable_frame, text="🔧 Prétraitement", padding=10)
        preproc_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self._create_slider(preproc_frame, "Flou Gaussien", self.blur_var, 1, 15, 2,
                           tooltip="Kernel flou (impair uniquement)")
        self._create_slider(preproc_frame, "Seuillage", self.threshold_var, 0, 255, 1,
                           tooltip="Valeur seuil binarisation")
        self._create_slider(preproc_frame, "Morpho Kernel", self.morph_kernel_var, 1, 15, 2,
                           tooltip="Taille noyau morphologique")
        self._create_slider(preproc_frame, "Morpho Itérations", self.morph_iter_var, 1, 5, 1,
                           tooltip="Nombre d'itérations morphologiques")
        
        # ═══════════════════════════════════════════════════════════
        # SECTION 3 : FILTRES DÉTECTION
        # ═══════════════════════════════════════════════════════════
        detect_frame = ttk.LabelFrame(scrollable_frame, text="🎯 Filtres Détection", padding=10)
        detect_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self._create_slider(detect_frame, "Aire Min", self.min_area_var, 100, 2000, 50,
                           tooltip="Aire minimale pupille (px²)")
        self._create_slider(detect_frame, "Aire Max", self.max_area_var, 1000, 10000, 100,
                           tooltip="Aire maximale pupille (px²)")
        self._create_slider(detect_frame, "Circularité Min", self.min_circ_var, 0.5, 1.0, 0.05,
                           tooltip="Seuil circularité (1.0 = cercle parfait)")
        
        # ═══════════════════════════════════════════════════════════
        # SECTION 4 : RÉGION D'INTÉRÊT (ROI)
        # ═══════════════════════════════════════════════════════════
        roi_frame = ttk.LabelFrame(scrollable_frame, text="📐 Région d'Intérêt", padding=10)
        roi_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self._create_slider(roi_frame, "ROI X", self.roi_x_var, 0, 400, 10,
                           tooltip="Position horizontale ROI")
        self._create_slider(roi_frame, "ROI Y", self.roi_y_var, 0, 300, 10,
                           tooltip="Position verticale ROI")
        self._create_slider(roi_frame, "ROI Largeur", self.roi_w_var, 100, 400, 10,
                           tooltip="Largeur de la ROI")
        self._create_slider(roi_frame, "ROI Hauteur", self.roi_h_var, 100, 300, 10,
                           tooltip="Hauteur de la ROI")
        
        # ═══════════════════════════════════════════════════════════
        # SECTION 5 : MODES D'AFFICHAGE
        # ═══════════════════════════════════════════════════════════
        view_frame = ttk.LabelFrame(scrollable_frame, text="🎨 Mode d'Affichage", padding=10)
        view_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Radiobutton(
            view_frame, text="1️⃣ Full Frame", variable=self.view_mode_var,
            value=1, command=self._auto_save
        ).pack(anchor=tk.W, padx=5, pady=2)
        
        tk.Radiobutton(
            view_frame, text="2️⃣ ROI Only", variable=self.view_mode_var,
            value=2, command=self._auto_save
        ).pack(anchor=tk.W, padx=5, pady=2)
        
        tk.Radiobutton(
            view_frame, text="3️⃣ Binary", variable=self.view_mode_var,
            value=3, command=self._auto_save
        ).pack(anchor=tk.W, padx=5, pady=2)
        
        # ═══════════════════════════════════════════════════════════
        # SECTION 6 : ENREGISTREMENT
        # ═══════════════════════════════════════════════════════════
        rec_frame = ttk.LabelFrame(scrollable_frame, text="🔴 Enregistrement", padding=10)
        rec_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Checkbutton(
            rec_frame,
            text="▶️ Démarrer l'enregistrement CSV",
            variable=self.recording_var,
            command=self._toggle_recording,
            font=("Arial", 11, "bold")
        ).pack(anchor=tk.W, padx=5, pady=5)
        
        # ═══════════════════════════════════════════════════════════
        # SECTION 7 : ACTIONS
        # ═══════════════════════════════════════════════════════════
        actions_frame = ttk.Frame(scrollable_frame)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(
            actions_frame,
            text="💾 Appliquer",
            command=self._manual_save
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(
            actions_frame,
            text="🔄 Réinitialiser",
            command=self._reset_defaults
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(
            actions_frame,
            text="🛑 Arrêter Acquisition",
            command=self._shutdown_acquisition
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # ═══════════════════════════════════════════════════════════
        # FOOTER
        # ═══════════════════════════════════════════════════════════
        footer_frame = tk.Frame(self.root, bg="#34495e", pady=10)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = tk.Label(
            footer_frame,
            text=f"✅ Connecté | Fichier: {self.param_file.name}",
            bg="#34495e",
            fg="white",
            font=("Arial", 9)
        )
        self.status_label.pack()
    
    def _create_slider(self, parent, label, variable, from_, to, resolution, tooltip=""):
        """Crée un slider avec label et valeur"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=5)
        
        # Label + Tooltip
        label_text = f"{label}:"
        if tooltip:
            label_text += f" ℹ️"
        
        label_widget = tk.Label(frame, text=label_text, width=20, anchor=tk.W)
        label_widget.pack(side=tk.LEFT)
        
        # Bind tooltip
        if tooltip:
            self._create_tooltip(label_widget, tooltip)
        
        # Slider
        slider = tk.Scale(
            frame,
            from_=from_,
            to=to,
            resolution=resolution,
            orient=tk.HORIZONTAL,
            variable=variable,
            command=lambda _: self._auto_save()
        )
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Valeur affichée
        value_label = tk.Label(frame, text=f"{variable.get():.2f}", width=8)
        value_label.pack(side=tk.LEFT)
        
        # Mise à jour valeur
        def update_value(*args):
            value_label.config(text=f"{variable.get():.2f}")
        
        variable.trace_add("write", update_value)
    
    def _create_tooltip(self, widget, text):
        """Crée un tooltip au survol"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, bg="yellow", relief=tk.SOLID, borderwidth=1)
            label.pack()
            widget.tooltip = tooltip
        
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
        
        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)
    
    def _auto_save(self):
        """Sauvegarde automatique avec limitation (max 2 fois/sec)"""
        now = datetime.now()
        if (now - self.last_update).total_seconds() < 0.5:
            return
        
        self.last_update = now
        self._save_parameters()
    
    def _manual_save(self):
        """Sauvegarde manuelle forcée"""
        self._save_parameters()
        self.status_label.config(text="✅ Paramètres appliqués !")
        self.root.after(2000, lambda: self.status_label.config(
            text=f"✅ Connecté | Fichier: {self.param_file.name}"
        ))
    
    def _toggle_recording(self):
        """Active/désactive l'enregistrement"""
        self.params['recording'] = self.recording_var.get()
        self._save_parameters()
        
        if self.params['recording']:
            self.status_label.config(text="🔴 Enregistrement en cours...")
        else:
            self.status_label.config(text="⏹️ Enregistrement arrêté")
            self.root.after(2000, lambda: self.status_label.config(
                text=f"✅ Connecté | Fichier: {self.param_file.name}"
            ))
    
    def _reset_defaults(self):
        """Réinitialise aux valeurs par défaut"""
        self.exposure_var.set(-6.0)
        self.brightness_var.set(128)
        self.contrast_var.set(32)
        self.blur_var.set(5)
        self.threshold_var.set(50)
        self.morph_kernel_var.set(3)
        self.morph_iter_var.set(1)
        self.min_area_var.set(300)
        self.max_area_var.set(5000)
        self.min_circ_var.set(0.7)
        self.roi_x_var.set(200)
        self.roi_y_var.set(150)
        self.roi_w_var.set(240)
        self.roi_h_var.set(180)
        self.view_mode_var.set(1)
        self.recording_var.set(False)
        
        self._save_parameters()
        self.status_label.config(text="🔄 Paramètres réinitialisés")
        self.root.after(2000, lambda: self.status_label.config(
            text=f"✅ Connecté | Fichier: {self.param_file.name}"
        ))
    
    def _shutdown_acquisition(self):
        """Envoie signal d'arrêt à acquisition_camera_IR"""
        self.params['shutdown'] = True
        self._save_parameters()
        self.status_label.config(text="🛑 Signal d'arrêt envoyé")
    
    def _save_parameters(self):
        """Sauvegarde les paramètres dans JSON"""
        self.params.update({
            'exposure': self.exposure_var.get(),
            'brightness': self.brightness_var.get(),
            'contrast': self.contrast_var.get(),
            'blur_kernel': self.blur_var.get(),
            'threshold_value': self.threshold_var.get(),
            'morph_kernel': self.morph_kernel_var.get(),
            'morph_iterations': self.morph_iter_var.get(),
            'min_area': self.min_area_var.get(),
            'max_area': self.max_area_var.get(),
            'min_circularity': self.min_circ_var.get(),
            'roi_x': self.roi_x_var.get(),
            'roi_y': self.roi_y_var.get(),
            'roi_width': self.roi_w_var.get(),
            'roi_height': self.roi_h_var.get(),
            'view_mode': self.view_mode_var.get(),
            'recording': self.recording_var.get()
        })
        
        try:
            # Format compatible avec acquisition_camera_IR.py
            output = {
                "params": self.params,
                "last_update": datetime.now().isoformat()
            }
            
            with open(self.param_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=4)
            
            self.logger.info(f"✅ Paramètres sauvegardés")
        
        except Exception as e:
            self.logger.error(f"❌ Erreur sauvegarde : {e}")
    
    def _load_parameters(self):
        """Charge les paramètres depuis JSON"""
        try:
            if self.param_file.exists():
                with open(self.param_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded_params = data.get("params", {})
                    self.params.update(loaded_params)
                self.logger.info(f"✅ Paramètres chargés")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur chargement : {e}")
    
    def _on_closing(self):
        """Gestion de la fermeture"""
        self.logger.info("🛑 Fermeture de l'interface...")
        self._save_parameters()
        
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
    
    def run(self):
        """Lance la boucle principale"""
        self.logger.info("🚀 Démarrage de l'interface")
        self.root.mainloop()


# ✅ LANCEMENT STANDALONE
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("🎛️  INTERFACE DE CONTRÔLE CAMÉRA IR")
    print("=" * 60)
    print()
    print("📋 Instructions:")
    print("  1. Lancez acquisition_camera_IR.py dans un autre terminal")
    print("  2. Ajustez les paramètres ici en temps réel")
    print("  3. Les modifications sont automatiques")
    print()
    print("📁 Fichier de communication: shared_params.json")
    print()
    
    controller = ParameterController()
    controller.run()
