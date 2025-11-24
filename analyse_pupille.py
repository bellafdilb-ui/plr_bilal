"""
analyse_pupille_v4.py
Analyse pupillométrique avec sauvegarde organisée
✅ NOUVEAU : Dossier "Analyse" créé automatiquement
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from pathlib import Path
import glob

class PupilDataAnalyzer:
    """Analyseur avec organisation des fichiers de sortie"""
    
    def __init__(self, csv_path):
        self.csv_path = csv_path
        
        # ═════════════════════════════════════════════════════
        # 🔧 NOUVEAU : Création dossier "Analyse"
        # ═════════════════════════════════════════════════════
        self.output_dir = Path("Analyse")
        self.output_dir.mkdir(exist_ok=True)  # Crée si n'existe pas
        print(f"📁 Dossier de sortie : {self.output_dir.absolute()}")
        
        print(f"\n📂 Fichier à analyser : {csv_path}")
        
        # Chargement données
        self.data = pd.read_csv(
            csv_path,
            parse_dates=['timestamp'],
            date_format='ISO8601'
        )
        
        print(f"✅ Chargé {len(self.data)} mesures")
        print(f"📊 Colonnes : {list(self.data.columns)}")
        
        # Temps relatif
        self.data['time_sec'] = (
            self.data['timestamp'] - self.data['timestamp'].min()
        ).dt.total_seconds()
        
        print(f"✅ Colonne 'time_sec' ajoutée\n")
    
    def compute_statistics(self):
        """Calcul statistiques descriptives"""
        duration_timedelta = self.data['timestamp'].max() - self.data['timestamp'].min()
        duration_seconds = duration_timedelta.total_seconds()
        
        stats = {
            'Nombre total de mesures': len(self.data),
            'Durée (s)': duration_seconds,
            'Fréquence (Hz)': len(self.data) / duration_seconds if duration_seconds > 0 else 0,
            
            'Diamètre moyen (mm)': self.data['diameter_mm'].mean(),
            'Diamètre min (mm)': self.data['diameter_mm'].min(),
            'Diamètre max (mm)': self.data['diameter_mm'].max(),
            'Écart-type (mm)': self.data['diameter_mm'].std(),
            'CV (%)': (self.data['diameter_mm'].std() / self.data['diameter_mm'].mean()) * 100,
            
            'Score moyen': self.data['score'].mean(),
            'Score min': self.data['score'].min(),
            'Taux mesures fiables (score>0.7)': (self.data['score'] > 0.7).sum() / len(self.data) * 100
        }
        return stats
    
    def plot_timeline(self, output_filename):
        """
        Graphique timeline avec 3 sous-graphes
        ✅ Sauvegarde dans dossier "Analyse"
        """
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        fig.suptitle('📊 Analyse Temporelle Pupillométrique', fontsize=16, fontweight='bold')
        
        # ═════════════════════════════════════════════════════
        # Subplot 1 : Diamètre pupillaire
        # ═════════════════════════════════════════════════════
        axes[0].plot(self.data['time_sec'], self.data['diameter_mm'], 
                     color='#2E86AB', linewidth=1.5, alpha=0.8)
        axes[0].fill_between(self.data['time_sec'], self.data['diameter_mm'], 
                              alpha=0.3, color='#2E86AB')
        axes[0].set_ylabel('Diamètre (mm)', fontsize=12, fontweight='bold')
        axes[0].set_title('Évolution du Diamètre Pupillaire', fontsize=14)
        axes[0].grid(True, alpha=0.3, linestyle='--')
        axes[0].axhline(self.data['diameter_mm'].mean(), 
                        color='red', linestyle='--', label='Moyenne', alpha=0.7)
        axes[0].legend()
        
        # ═════════════════════════════════════════════════════
        # Subplot 2 : Score de confiance
        # ═════════════════════════════════════════════════════
        colors = ['green' if s > 0.7 else 'orange' if s > 0.5 else 'red' 
                  for s in self.data['score']]
        axes[1].scatter(self.data['time_sec'], self.data['score'], 
                        c=colors, alpha=0.6, s=20)
        axes[1].axhline(0.7, color='green', linestyle='--', 
                        label='Seuil fiable (0.7)', alpha=0.7)
        axes[1].set_ylabel('Score Confiance', fontsize=12, fontweight='bold')
        axes[1].set_title('Qualité de Détection', fontsize=14)
        axes[1].set_ylim([0, 1.05])
        axes[1].grid(True, alpha=0.3, linestyle='--')
        axes[1].legend()
        
        # ═════════════════════════════════════════════════════
        # Subplot 3 : Position centre pupille
        # ═════════════════════════════════════════════════════
        axes[2].plot(self.data['time_sec'], self.data['center_x'], 
                     label='X', color='#A23B72', alpha=0.7, linewidth=1.2)
        axes[2].plot(self.data['time_sec'], self.data['center_y'], 
                     label='Y', color='#F18F01', alpha=0.7, linewidth=1.2)
        axes[2].set_xlabel('Temps (s)', fontsize=12, fontweight='bold')
        axes[2].set_ylabel('Position (px)', fontsize=12, fontweight='bold')
        axes[2].set_title('Stabilité Position Pupille', fontsize=14)
        axes[2].grid(True, alpha=0.3, linestyle='--')
        axes[2].legend()
        
        plt.tight_layout()
        
        # ═════════════════════════════════════════════════════
        # 🔧 CORRECTION : Sauvegarde dans dossier "Analyse"
        # ═════════════════════════════════════════════════════
        output_path = self.output_dir / output_filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Graphique sauvegardé : {output_path}")
    
    def generate_report(self, output_filename):
        """
        Génération rapport texte détaillé
        ✅ Sauvegarde dans dossier "Analyse"
        """
        stats = self.compute_statistics()
        
        # Analyse qualitative automatique
        if stats['Score moyen'] > 0.8 and stats['CV (%)'] < 15:
            quality = "EXCELLENT (données très fiables)"
        elif stats['Score moyen'] > 0.6 and stats['CV (%)'] < 25:
            quality = "BON (données exploitables)"
        else:
            quality = "MOYEN (vérifier conditions d'acquisition)"
        
        report = f"""
╔═══════════════════════════════════════════════════════════════════╗
║              📊 RAPPORT D'ANALYSE PUPILLOMÉTRIQUE                 ║
╚═══════════════════════════════════════════════════════════════════╝

📂 Fichier source : {self.csv_path}
📅 Date analyse   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

─────────────────────────────────────────────────────────────────────
📈 STATISTIQUES GÉNÉRALES
─────────────────────────────────────────────────────────────────────
  • Nombre de mesures      : {stats['Nombre total de mesures']}
  • Durée enregistrement   : {stats['Durée (s)']:.2f} s
  • Fréquence acquisition  : {stats['Fréquence (Hz)']:.2f} Hz

─────────────────────────────────────────────────────────────────────
👁️  DIAMÈTRE PUPILLAIRE
─────────────────────────────────────────────────────────────────────
  • Moyenne                : {stats['Diamètre moyen (mm)']:.2f} mm
  • Min / Max              : {stats['Diamètre min (mm)']:.2f} / {stats['Diamètre max (mm)']:.2f} mm
  • Écart-type             : {stats['Écart-type (mm)']:.2f} mm
  • Coefficient variation  : {stats['CV (%)']:.1f} %

─────────────────────────────────────────────────────────────────────
✅ QUALITÉ DÉTECTION
─────────────────────────────────────────────────────────────────────
  • Score moyen            : {stats['Score moyen']:.3f}
  • Score minimum          : {stats['Score min']:.3f}
  • Mesures fiables (>0.7) : {stats['Taux mesures fiables (score>0.7)']:.1f} %

─────────────────────────────────────────────────────────────────────
🔍 ÉVALUATION GLOBALE
─────────────────────────────────────────────────────────────────────
  ➤ Qualité des données : {quality}

─────────────────────────────────────────────────────────────────────
💡 RECOMMANDATIONS
─────────────────────────────────────────────────────────────────────
"""
        
        # Recommandations conditionnelles
        if stats['CV (%)'] > 20:
            report += "  ⚠️  Variabilité élevée détectée\n"
            report += "      → Vérifier stabilité patient / éclairage\n\n"
        
        if stats['Taux mesures fiables (score>0.7)'] < 80:
            report += "  ⚠️  Taux détection faible\n"
            report += "      → Ajuster position caméra / focus\n\n"
        
        if stats['Fréquence (Hz)'] < 25:
            report += "  ⚠️  Fréquence acquisition basse\n"
            report += "      → Vérifier performances caméra\n\n"
        
        if all([stats['CV (%)'] <= 20, 
                stats['Taux mesures fiables (score>0.7)'] >= 80,
                stats['Fréquence (Hz)'] >= 25]):
            report += "  ✅ Aucune anomalie majeure détectée\n\n"
        
        report += "─────────────────────────────────────────────────────────────────────\n"
        
        # ═════════════════════════════════════════════════════
        # 🔧 CORRECTION : Sauvegarde dans dossier "Analyse"
        # ═════════════════════════════════════════════════════
        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(report)
        print(f"✅ Rapport sauvegardé : {output_path}")

def main():
    """Point d'entrée principal"""
    try:
        # Recherche automatique dernier CSV
        csv_files = sorted(glob.glob('pupil_data_*.csv'), reverse=True)
        
        if not csv_files:
            print("❌ Aucun fichier pupil_data_*.csv trouvé")
            return
        
        csv_path = csv_files[0]
        
        print(f"""
╔═══════════════════════════════════════════════════════╗
║  🔬 ANALYSEUR PUPILLOMÉTRIQUE v4.0                    ║
╚═══════════════════════════════════════════════════════╝
        """)
        
        analyzer = PupilDataAnalyzer(csv_path)
        
        # Génération outputs avec timestamp
        timestamp = datetime.now().strftime('%H%M%S')
        
        print("📈 Génération graphique timeline...")
        analyzer.plot_timeline(f"analyse_timeline_{timestamp}.png")
        
        print("\n📝 Génération rapport...")
        analyzer.generate_report(f"rapport_analyse_{timestamp}.txt")
        
        print(f"""
╔═══════════════════════════════════════════════════════╗
║  ✅ ANALYSE TERMINÉE                                  ║
╠═══════════════════════════════════════════════════════╣
║  📊 Analyse/analyse_timeline_{timestamp}.png         ║
║  📝 Analyse/rapport_analyse_{timestamp}.txt          ║
╚═══════════════════════════════════════════════════════╝
        """)
        
    except Exception as e:
        print(f"❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
