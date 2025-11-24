"""
parameter_controller.py
CONTRÔLEUR DE PARAMÈTRES - Interface Tkinter
Version 4.2 avec brightness/contrast
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
from datetime import datetime


class ParameterController:
    """Contrôleur interactif des paramètres de détection"""
    
    def __init__(self):
        """Initialisation du contrôleur"""
        
        # Chemins
        self.project_root = Path(__file__).parent
        self.config_file = self.project_root / "shared_params.json"
        self.calibration_file = self.project_root / "calibration_data.json"
        
        # Interface
        self.root = tk.Tk()
        self.root.title("🎛️ Parameter Controller v4.2")
        self.root.geometry("500x850")
        self.root.resizable(False, False)
        
        # Variables Tkinter
        self.vars = {
            'exposure': tk.DoubleVar(value=-6.0),
            'brightness': tk.IntVar(value=128),
            'contrast': tk.IntVar(value=32),
            'blur_kernel': tk.IntVar(value=5),
            'threshold_value': tk.IntVar(value=50),
            'morph_kernel': tk.IntVar(value=3),
            'morph_iterations': tk.IntVar(value=1),
            'min_area': tk.IntVar(value=300),
            'max_area': tk.IntVar(value=5000),
            'min_circularity': tk.DoubleVar(value=0.7),
            'roi_x': tk.IntVar(value=200),
            'roi_y': tk.IntVar(value=150),
            'roi_width': tk.IntVar(value=240),
            'roi_height': tk.IntVar(value=180),
            'view_mode': tk.IntVar(value=1),
            'recording': tk.BooleanVar(value=False),
        }
        
        # Charger paramètres existants
        self.load_parameters()
        
        # Créer interface
        self.create_ui()
        
        # Auto-save toutes les 500ms
        self.auto_save()
        
        print("✅ Parameter Controller initialisé")
    
    
    def load_parameters(self):
        """Charge les paramètres depuis JSON"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    params = data.get("params", {})
                    
                    for key, var in self.vars.items():
                        if key in params:
                            var.set(params[key])
                    
                    print("✅ Paramètres chargés")
        
        except Exception as e:
            print(f"⚠️ Erreur chargement : {e}")
    
    
    def save_parameters(self):
        """Sauvegarde les paramètres dans JSON"""
        try:
            params = {key: var.get() for key, var in self.vars.items()}
            params['shutdown'] = False
            params['ratio_mm_per_px'] = self.load_calibration_ratio()
            
            data = {
                "timestamp": datetime.now().isoformat(),
                "params": params
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            print(f"❌ Erreur sauvegarde : {e}")
    
    
    def load_calibration_ratio(self):
        """Charge le ratio de calibration actif"""
        try:
            if self.calibration_file.exists():
                with open(self.calibration_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("active_calibration")
        except:
            pass
        return None
    
    
    def auto_save(self):
        """Sauvegarde automatique"""
        self.save_parameters()
        self.root.after(500, self.auto_save)
    
    
    def create_ui(self):
        """Crée l'interface utilisateur"""
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Frame principal avec scrollbar
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas + Scrollbar
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # === SECTION CAMÉRA ===
        cam_frame = ttk.LabelFrame(scrollable_frame, text="📷 Paramètres Caméra", padding="10")
        cam_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.create_slider(cam_frame, "Exposition", self.vars['exposure'], -13, 0, 0.5, row=0)
        self.create_slider(cam_frame, "Luminosité", self.vars['brightness'], 0, 255, 1, row=1)
        self.create_slider(cam_frame, "Contraste", self.vars['contrast'], 0, 100, 1, row=2)
        
        # === SECTION PRÉTRAITEMENT ===
        pre_frame = ttk.LabelFrame(scrollable_frame, text="🔧 Prétraitement", padding="10")
        pre_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.create_slider(pre_frame, "Flou (kernel)", self.vars['blur_kernel'], 1, 15, 2, row=0)
        self.create_slider(pre_frame, "Seuil binaire", self.vars['threshold_value'], 0, 255, 1, row=1)
        
        # === SECTION MORPHOLOGIE ===
        morph_frame = ttk.LabelFrame(scrollable_frame, text="🧩 Morphologie", padding="10")
        morph_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.create_slider(morph_frame, "Kernel morpho", self.vars['morph_kernel'], 1, 11, 2, row=0)
        self.create_slider(morph_frame, "Itérations", self.vars['morph_iterations'], 1, 5, 1, row=1)
        
        # === SECTION DÉTECTION ===
        det_frame = ttk.LabelFrame(scrollable_frame, text="🎯 Détection Pupille", padding="10")
        det_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.create_slider(det_frame, "Aire min (px²)", self.vars['min_area'], 100, 2000, 50, row=0)
        self.create_slider(det_frame, "Aire max (px²)", self.vars['max_area'], 1000, 10000, 100, row=1)
        self.create_slider(det_frame, "Circularité min", self.vars['min_circularity'], 0.3, 1.0, 0.05, row=2)
        
        # === SECTION ROI ===
        roi_frame = ttk.LabelFrame(scrollable_frame, text="📐 Région d'Intérêt (ROI)", padding="10")
        roi_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.create_slider(roi_frame, "Position X", self.vars['roi_x'], 0, 640, 10, row=0)
        self.create_slider(roi_frame, "Position Y", self.vars['roi_y'], 0, 480, 10, row=1)
        self.create_slider(roi_frame, "Largeur", self.vars['roi_width'], 50, 640, 10, row=2)
        self.create_slider(roi_frame, "Hauteur", self.vars['roi_height'], 50, 480, 10, row=3)
        
        # === SECTION CONTRÔLES ===
        ctrl_frame = ttk.LabelFrame(scrollable_frame, text="🎮 Contrôles", padding="10")
        ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Mode affichage
        ttk.Label(ctrl_frame, text="Mode Affichage:").grid(row=0, column=0, sticky=tk.W, pady=5)
        view_frame = ttk.Frame(ctrl_frame)
        view_frame.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(view_frame, text="Full", variable=self.vars['view_mode'], value=1).pack(side=tk.LEFT)
        ttk.Radiobutton(view_frame, text="ROI", variable=self.vars['view_mode'], value=2).pack(side=tk.LEFT)
        ttk.Radiobutton(view_frame, text="Binary", variable=self.vars['view_mode'], value=3).pack(side=tk.LEFT)
        
        # Enregistrement
        ttk.Checkbutton(ctrl_frame, text="🔴 Enregistrement CSV", 
                       variable=self.vars['recording']).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # === SECTION ACTIONS ===
        action_frame = ttk.LabelFrame(scrollable_frame, text="⚡ Actions", padding="10")
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        btn_frame = ttk.Frame(action_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="💾 Sauvegarder", command=self.manual_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Recharger", command=self.load_parameters).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔧 Calibration", command=self.launch_calibration).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🛑 Arrêter Caméra", command=self.shutdown_camera).pack(side=tk.LEFT, padx=5)
        
        # === STATUS BAR ===
        self.status_label = ttk.Label(scrollable_frame, text="✅ Prêt", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, padx=5, pady=5)
    
    
    def create_slider(self, parent, label, variable, min_val, max_val, resolution, row):
        """Crée un slider avec label et valeur"""
        
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
        
        slider = ttk.Scale(parent, from_=min_val, to=max_val, variable=variable, 
                          orient=tk.HORIZONTAL, length=200)
        slider.grid(row=row, column=1, sticky=tk.EW, pady=5, padx=5)
        
        value_label = ttk.Label(parent, text=f"{variable.get():.2f}")
        value_label.grid(row=row, column=2, sticky=tk.W, pady=5)
        
        # Mise à jour du label
        def update_label(*args):
            value_label.config(text=f"{variable.get():.2f}")
        
        variable.trace_add('write', update_label)
        
        parent.columnconfigure(1, weight=1)
    
    
    def manual_save(self):
        """Sauvegarde manuelle"""
        self.save_parameters()
        self.status_label.config(text="💾 Paramètres sauvegardés")
        self.root.after(2000, lambda: self.status_label.config(text="✅ Prêt"))
    
    
    def launch_calibration(self):
        """Lance l'outil de calibration"""
        import subprocess
        try:
            subprocess.Popen(["python", str(self.project_root / "calibration.py")])
            self.status_label.config(text="🔧 Calibration lancée")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lancer calibration.py\n{e}")
    
    
    def shutdown_camera(self):
        """Arrête l'acquisition caméra"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                data['params']['shutdown'] = True
                
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
                self.status_label.config(text="🛑 Arrêt caméra demandé")
        
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'arrêter la caméra\n{e}")
    
    
    def run(self):
        """Lance la boucle principale"""
        self.root.mainloop()


if __name__ == "__main__":
    controller = ParameterController()
    controller.run()
