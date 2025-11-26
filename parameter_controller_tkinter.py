#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interface Tkinter pour ajuster les paramètres de détection de pupille en temps réel
VERSION STANDALONE - Fonctionne indépendamment
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import json
from pathlib import Path
import logging


class ParameterController:
    """Interface Tkinter pour contrôler les paramètres en temps réel"""
    
    def __init__(self):
        """Initialise le contrôleur standalone"""
        self.logger = logging.getLogger(__name__)
        
        # Fichier de communication
        self.param_file = Path("camera_params.json")
        
        # Paramètres par défaut
        self.params = {
            'exposure': -6.0,
            'brightness': 128,
            'contrast': 32,
            'blur_kernel': 5,
            'threshold': 50,
            'min_area': 500,
            'max_area': 15000
        }
        
        # Charger les paramètres existants
        self._load_parameters()
        
        # Créer l'interface
        self.root = tk.Tk()
        self.root.title("🎛️ Contrôle Caméra IR - Temps Réel")
        self.root.geometry("450x600")
        self.root.resizable(False, False)
        
        # Variables Tkinter
        self.exposure_var = tk.DoubleVar(value=self.params['exposure'])
        self.brightness_var = tk.IntVar(value=self.params['brightness'])
        self.contrast_var = tk.IntVar(value=self.params['contrast'])
        self.blur_var = tk.IntVar(value=self.params['blur_kernel'])
        self.threshold_var = tk.IntVar(value=self.params['threshold'])
        self.min_area_var = tk.IntVar(value=self.params['min_area'])
        self.max_area_var = tk.IntVar(value=self.params['max_area'])
        
        # Thread de mise à jour automatique
        self.auto_update = True
        self.update_thread = None
        
        # Créer l'interface
        self._create_ui()
        
        # Démarrer le thread de mise à jour
        self._start_auto_update()
        
        # Gestion fermeture
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self.logger.info("✅ Interface standalone initialisée")
    
    def _create_ui(self):
        """Crée l'interface utilisateur"""
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titre
        title = tk.Label(
            main_frame,
            text="🎛️ Paramètres Caméra IR",
            font=('Arial', 14, 'bold'),
            fg='#2c3e50'
        )
        title.pack(pady=(0, 20))
        
        # ===== SECTION CAMÉRA =====
        camera_frame = ttk.LabelFrame(main_frame, text="📹 Paramètres Caméra", padding="10")
        camera_frame.pack(pady=10, fill=tk.X)
        
        self._create_slider(
            camera_frame,
            "Exposition",
            self.exposure_var,
            -13.0, 0.0,
            self._on_exposure_change,
            resolution=1.0
        )
        
        self._create_slider(
            camera_frame,
            "Luminosité",
            self.brightness_var,
            0, 255,
            self._on_brightness_change
        )
        
        self._create_slider(
            camera_frame,
            "Contraste",
            self.contrast_var,
            0, 95,
            self._on_contrast_change
        )
        
        # ===== SECTION DÉTECTION =====
        detection_frame = ttk.LabelFrame(main_frame, text="🔍 Paramètres Détection", padding="10")
        detection_frame.pack(pady=10, fill=tk.X)
        
        self._create_slider(
            detection_frame,
            "Flou Gaussien",
            self.blur_var,
            1, 21,
            self._on_blur_change,
            resolution=2
        )
        
        self._create_slider(
            detection_frame,
            "Seuil Binarisation",
            self.threshold_var,
            0, 255,
            self._on_threshold_change
        )
        
        self._create_slider(
            detection_frame,
            "Surface Min (px²)",
            self.min_area_var,
            100, 5000,
            self._on_min_area_change,
            resolution=100
        )
        
        self._create_slider(
            detection_frame,
            "Surface Max (px²)",
            self.max_area_var,
            5000, 50000,
            self._on_max_area_change,
            resolution=500
        )
        
        # Boutons d'action
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20, fill=tk.X)
        
        # Bouton Appliquer
        apply_btn = tk.Button(
            button_frame,
            text="✅ Appliquer Maintenant",
            command=self._apply_parameters,
            bg='#2ecc71',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=5,
            relief=tk.RAISED,
            cursor='hand2'
        )
        apply_btn.pack(pady=5, fill=tk.X)
        
        # Bouton Reset
        reset_btn = tk.Button(
            button_frame,
            text="🔄 Réinitialiser",
            command=self._reset_parameters,
            bg='#e74c3c',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=5,
            relief=tk.RAISED,
            cursor='hand2'
        )
        reset_btn.pack(pady=5, fill=tk.X)
        
        # Statut
        self.status_label = tk.Label(
            main_frame,
            text="🟢 En attente de acquisition_camera_IR.py...",
            font=('Arial', 9),
            fg='#27ae60',
            bg='#ecf0f1',
            padx=10,
            pady=5,
            relief=tk.SUNKEN
        )
        self.status_label.pack(pady=10, fill=tk.X)
        
        # Info
        info_text = (
            "💡 Mode d'emploi:\n"
            "1. Lancez cette interface\n"
            "2. Lancez acquisition_camera_IR.py\n"
            "3. Ajustez les paramètres en temps réel"
        )
        info_label = tk.Label(
            main_frame,
            text=info_text,
            font=('Arial', 8),
            fg='#7f8c8d',
            justify=tk.LEFT
        )
        info_label.pack(pady=5)
    
    def _create_slider(self, parent, label, variable, from_, to, command, resolution=1):
        """Crée un slider avec son label"""
        frame = ttk.Frame(parent)
        frame.pack(pady=5, fill=tk.X)
        
        # Label
        lbl = tk.Label(
            frame,
            text=f"{label}:",
            font=('Arial', 9),
            anchor=tk.W,
            width=18
        )
        lbl.pack(side=tk.LEFT, padx=(0, 10))
        
        # Valeur
        value_lbl = tk.Label(
            frame,
            textvariable=variable,
            font=('Arial', 9, 'bold'),
            fg='#e74c3c',
            width=8
        )
        value_lbl.pack(side=tk.RIGHT)
        
        # Slider
        slider = ttk.Scale(
            frame,
            from_=from_,
            to=to,
            variable=variable,
            orient=tk.HORIZONTAL,
            command=command
        )
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    def _on_exposure_change(self, value):
        """Callback changement exposition"""
        self.params['exposure'] = float(value)
        self.logger.debug(f"Exposition : {value}")
    
    def _on_brightness_change(self, value):
        """Callback changement luminosité"""
        self.params['brightness'] = int(float(value))
        self.logger.debug(f"Luminosité : {value}")
    
    def _on_contrast_change(self, value):
        """Callback changement contraste"""
        self.params['contrast'] = int(float(value))
        self.logger.debug(f"Contraste : {value}")
    
    def _on_blur_change(self, value):
        """Callback changement flou"""
        val = int(float(value))
        if val % 2 == 0:
            val += 1
        self.blur_var.set(val)
        self.params['blur_kernel'] = val
        self.logger.debug(f"Flou : {val}")
    
    def _on_threshold_change(self, value):
        """Callback changement seuil"""
        self.params['threshold'] = int(float(value))
        self.logger.debug(f"Seuil : {value}")
    
    def _on_min_area_change(self, value):
        """Callback changement surface min"""
        self.params['min_area'] = int(float(value))
        self.logger.debug(f"Surface min : {value}")
    
    def _on_max_area_change(self, value):
        """Callback changement surface max"""
        self.params['max_area'] = int(float(value))
        self.logger.debug(f"Surface max : {value}")
    
    def _start_auto_update(self):
        """Démarre le thread de mise à jour automatique"""
        self.update_thread = threading.Thread(target=self._auto_update_loop, daemon=True)
        self.update_thread.start()
        self.logger.info("✅ Thread de mise à jour automatique démarré")
    
    def _auto_update_loop(self):
        """Boucle de mise à jour automatique toutes les 500ms"""
        while self.auto_update:
            try:
                self._save_parameters()
                time.sleep(0.5)  # Mise à jour toutes les 500ms
            except Exception as e:
                self.logger.error(f"Erreur mise à jour auto : {e}")
                time.sleep(1.0)
    
    def _apply_parameters(self):
        """Applique immédiatement les paramètres"""
        self._save_parameters()
        self.status_label.config(
            text="✅ Paramètres appliqués !",
            fg='#27ae60'
        )
        self.root.after(2000, lambda: self.status_label.config(
            text="🟢 En attente de acquisition_camera_IR.py...",
            fg='#27ae60'
        ))
        self.logger.info("✅ Paramètres appliqués manuellement")
    
    def _reset_parameters(self):
        """Réinitialise aux valeurs par défaut"""
        defaults = {
            'exposure': -6.0,
            'brightness': 128,
            'contrast': 32,
            'blur_kernel': 5,
            'threshold': 50,
            'min_area': 500,
            'max_area': 15000
        }
        
        self.exposure_var.set(defaults['exposure'])
        self.brightness_var.set(defaults['brightness'])
        self.contrast_var.set(defaults['contrast'])
        self.blur_var.set(defaults['blur_kernel'])
        self.threshold_var.set(defaults['threshold'])
        self.min_area_var.set(defaults['min_area'])
        self.max_area_var.set(defaults['max_area'])
        
        self.params = defaults.copy()
        self._save_parameters()
        
        self.status_label.config(
            text="🔄 Paramètres réinitialisés",
            fg='#e67e22'
        )
        self.root.after(2000, lambda: self.status_label.config(
            text="🟢 En attente de acquisition_camera_IR.py...",
            fg='#27ae60'
        ))
        
        self.logger.info("🔄 Paramètres réinitialisés")
    
    def _save_parameters(self):
        """Sauvegarde les paramètres dans le fichier JSON"""
        try:
            with open(self.param_file, 'w') as f:
                json.dump(self.params, f, indent=4)
            self.logger.debug(f"💾 Paramètres sauvegardés : {self.params}")
        except Exception as e:
            self.logger.error(f"❌ Erreur sauvegarde : {e}")
    
    def _load_parameters(self):
        """Charge les paramètres depuis le fichier JSON"""
        if self.param_file.exists():
            try:
                with open(self.param_file, 'r') as f:
                    loaded = json.load(f)
                    self.params.update(loaded)
                self.logger.info(f"✅ Paramètres chargés : {self.params}")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur chargement paramètres : {e}")
    
    def _on_closing(self):
        """Gestion de la fermeture"""
        self.logger.info("🛑 Fermeture de l'interface...")
        self.auto_update = False
        
        # Attendre la fin du thread
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=1.0)
        
        # Sauvegarder une dernière fois
        self._save_parameters()
        
        # Fermer
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
    
    def run(self):
        """Lance la boucle principale Tkinter"""
        self.logger.info("🚀 Démarrage de l'interface standalone")
        self.root.mainloop()
        self.logger.info("✅ Interface fermée")


# ✅ LANCEMENT STANDALONE
if __name__ == "__main__":
    # Configuration logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("🎛️  INTERFACE DE CONTRÔLE CAMÉRA IR - STANDALONE")
    print("=" * 60)
    print()
    print("📋 Instructions:")
    print("  1. Cette fenêtre contrôle les paramètres")
    print("  2. Lancez acquisition_camera_IR.py dans un autre terminal")
    print("  3. Les modifications sont appliquées en temps réel")
    print()
    print("📁 Fichier de communication: camera_params.json")
    print()
    
    controller = ParameterController()
    controller.run()
