#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════╗
║           TEST PLR (Pupillary Light Reflex)                   ║
║                                                                ║
║  Protocole :                                                   ║
║  1. Baseline (5s) → Pupille au repos                          ║
║  2. Stimulation (3s) → Flash LED                              ║
║  3. Récupération (10s) → Retour taille initiale               ║
║                                                                ║
║  Métriques calculées :                                         ║
║  - Latence de constriction                                     ║
║  - Amplitude maximale (%)                                      ║
║  - Temps de récupération 75%                                   ║
╚═══════════════════════════════════════════════════════════════╝
"""

import sys  # ✅ AJOUT CRUCIAL
import cv2
import numpy as np
import time
import csv
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from scipy.signal import find_peaks
from acquisition_camera_IR import PupilDetectorIR

class PLRTest:
    """Gestionnaire du test réflexe photomoteur"""

    def __init__(self, detector):
        """
        Args:
            detector (PupilDetectorIR): Instance du détecteur de pupille
        """
        self.detector = detector

        # Paramètres temporels (secondes)
        self.baseline_duration = 5.0
        self.stimulus_duration = 3.0
        self.recovery_duration = 10.0

        # Données enregistrées
        self.timestamps = []
        self.diameters = []
        self.confidences = []
        self.stimulus_active = []

        # Résultats analyse
        self.metrics = {}

        # Dossier sauvegarde
        self.output_dir = Path("data/plr_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Etat de calibration
        self.calibration_validated = False

    def run_test(self):
        """
        Lance le protocole PLR complet

        Returns:
            dict: Métriques calculées ou None si échec
        """
        print("""
╔═══════════════════════════════════════════════════════════════╗
║                    DÉMARRAGE TEST PLR                         ║
╠═══════════════════════════════════════════════════════════════╣
║  Protocole :                                                   ║
║  • Baseline     : 5 secondes (pupille repos)                  ║
║  • Stimulation  : 3 secondes (flash LED)                      ║
║  • Récupération : 10 secondes                                 ║
║                                                                ║
║  Appuyez sur ESPACE pour démarrer...                          ║
║  Appuyez sur Q pour annuler                                   ║
╚═══════════════════════════════════════════════════════════════╝
        """)

        # Attente démarrage utilisateur
        if not self._wait_for_start():
            print("❌ Test annulé")
            return None

        # Réinitialisation données
        self.timestamps = []
        self.diameters = []
        self.confidences = []
        self.stimulus_active = []

        test_start = time.time()

        # ═══════════════════════════════════════════════════════════
        # PHASE 1 : BASELINE
        # ═══════════════════════════════════════════════════════════
        print("\n📊 PHASE 1/3 : BASELINE (5s)")
        if not self._record_phase("BASELINE", self.baseline_duration, stimulus=False):
            return None

        # ═══════════════════════════════════════════════════════════
        # PHASE 2 : STIMULATION LUMINEUSE
        # ═══════════════════════════════════════════════════════════
        print("\n💡 PHASE 2/3 : STIMULATION (3s)")
        if not self._record_phase("STIMULUS", self.stimulus_duration, stimulus=True):
            return None

        # ═══════════════════════════════════════════════════════════
        # PHASE 3 : RÉCUPÉRATION
        # ═══════════════════════════════════════════════════════════
        print("\n🔄 PHASE 3/3 : RÉCUPÉRATION (10s)")
        if not self._record_phase("RECOVERY", self.recovery_duration, stimulus=False):
            return None

        test_duration = time.time() - test_start
        print(f"\n✅ Test terminé en {test_duration:.1f}s")
        print(f"📈 {len(self.timestamps)} mesures enregistrées")

        # ═══════════════════════════════════════════════════════════
        # ANALYSE ET SAUVEGARDE
        # ═══════════════════════════════════════════════════════════
        self._analyze_results()
        self._save_results()
        self._plot_results()

        return self.metrics

    def _wait_for_start(self):
        """Attend que l'utilisateur appuie sur ESPACE avec feedback visuel"""
        print("📹 Affichage de la caméra pour positionnement...")

        while True:
            ret, frame = self.detector.cap.read()
            if not ret:
                print("❌ Erreur lecture caméra")
                return False

            display_frame = frame.copy()

            # ✅ DÉTECTION EN TEMPS RÉEL POUR VALIDATION
            result = self.detector.detect_pupil(frame)

            if result[0] is not None:
                x, y, diameter, diameter_mm, confidence = result

                if confidence >= 60.0:
                    # Pupille détectée correctement
                    cv2.circle(display_frame, (int(x), int(y)), 
                               int(diameter/2), (0, 255, 0), 3)
                    cv2.circle(display_frame, (int(x), int(y)), 3, (0, 0, 255), -1)

                    status = f"PRET - D={diameter_mm:.2f}mm | Conf={confidence:.0f}%"
                    color = (0, 255, 0)
                else:
                    status = "Confidence faible - Ajustez la position"
                    color = (0, 165, 255)
            else:
                status = "Aucune detection - Positionnez la camera"
                color = (0, 0, 255)

            # Interface d'attente
            cv2.putText(display_frame, status, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            cv2.putText(display_frame, "Appuyez sur ESPACE pour demarrer", 
                        (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 
                        1.0, (255, 255, 255), 2)
            cv2.putText(display_frame, "Q pour annuler", 
                        (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.7, (0, 0, 255), 2)

            cv2.imshow("Test PLR", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                return True
            elif key == ord('q'):
                return False

    def _record_phase(self, phase_name, duration, stimulus=False):
        """
        Enregistre une phase du test

        Args:
            phase_name (str): Nom de la phase
            duration (float): Durée en secondes
            stimulus (bool): Si True, affiche un flash blanc

        Returns:
            bool: True si succès, False si annulation
        """
        phase_start = time.time()
        test_start_offset = 0.0

        # Calcul du décalage temporel selon la phase
        if phase_name == "STIMULUS":
            test_start_offset = self.baseline_duration
        elif phase_name == "RECOVERY":
            test_start_offset = self.baseline_duration + self.stimulus_duration

        frame_count = 0
        detection_count = 0

        while (time.time() - phase_start) < duration:
            ret, frame = self.detector.cap.read()
            if not ret:
                print("❌ Erreur lecture caméra")
                return False

            frame_count += 1
            display_frame = frame.copy()
            elapsed = time.time() - phase_start

            # ───────────────────────────────────────────────────────
            # DÉTECTION PUPILLE
            # ───────────────────────────────────────────────────────
            result = self.detector.detect_pupil(frame)

            detection_ok = False

            if result[0] is not None:
                x, y, diameter, diameter_mm, confidence = result

                # Filtre confidence
                if confidence >= 60.0:
                    detection_ok = True
                    detection_count += 1

                    # ✅ TIMESTAMP CORRIGÉ
                    absolute_time = test_start_offset + elapsed

                    # Enregistrement données
                    self.timestamps.append(absolute_time)
                    self.diameters.append(diameter_mm)
                    self.confidences.append(confidence)
                    self.stimulus_active.append(stimulus)

                    # ✅ AFFICHAGE VISUEL AMÉLIORÉ
                    # Cercle vert sur la pupille
                    cv2.circle(display_frame, (int(x), int(y)), 
                               int(diameter/2), (0, 255, 0), 3)

                    # Point central
                    cv2.circle(display_frame, (int(x), int(y)), 
                               3, (0, 0, 255), -1)

                    # Texte de détection
                    info = f"D={diameter_mm:.2f}mm | Conf={confidence:.0f}%"
                    cv2.putText(display_frame, info, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                else:
                    # Confidence trop faible
                    cv2.putText(display_frame, "Confidence faible", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
            else:
                # Pas de détection
                cv2.putText(display_frame, "Aucune detection", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            # ───────────────────────────────────────────────────────
            # STIMULATION VISUELLE (flash blanc)
            # ───────────────────────────────────────────────────────
            if stimulus:
                overlay = np.ones_like(display_frame) * 255
                display_frame = cv2.addWeighted(display_frame, 0.3, overlay, 0.7, 0)
                cv2.putText(display_frame, "!!! STIMULUS ACTIF !!!", (50, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

            # ───────────────────────────────────────────────────────
            # INTERFACE
            # ───────────────────────────────────────────────────────
            # Nom de la phase
            cv2.putText(display_frame, f"PHASE: {phase_name}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Timer
            remaining = duration - elapsed
            cv2.putText(display_frame, f"Temps restant: {remaining:.1f}s", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Compteur détections
            detection_rate = (detection_count / frame_count * 100) if frame_count > 0 else 0
            cv2.putText(display_frame, f"Detections: {detection_count}/{frame_count} ({detection_rate:.0f}%)", 
                        (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Barre de progression
            progress = int((elapsed / duration) * 100)
            bar_width = 600
            bar_height = 20
            bar_x = 10
            bar_y = 450

            # Fond barre
            cv2.rectangle(display_frame, (bar_x, bar_y), 
                          (bar_x + bar_width, bar_y + bar_height), 
                          (50, 50, 50), -1)

            # Barre de progression
            cv2.rectangle(display_frame, (bar_x, bar_y), 
                          (bar_x + int(progress * bar_width / 100), bar_y + bar_height), 
                          (0, 255, 0) if detection_ok else (0, 165, 255), -1)

            # Texte pourcentage
            cv2.putText(display_frame, f"{progress}%", 
                        (bar_x + bar_width + 10, bar_y + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.imshow("Test PLR", display_frame)

            # Gestion annulation
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n❌ Test annulé par l'utilisateur")
                return False

        print(f"  ✅ {detection_count}/{frame_count} détections valides ({detection_rate:.1f}%)")

        return True

    def calibrate_with_gui(self):
        """Lance l'interface Tkinter pour ajustement manuel"""
        from parameter_controller_tkinter import ParameterController

        print("🎛️  Interface de calibration lancée...")
        print("   → Ajustez les paramètres avec les curseurs")
        print("   → Cliquez sur 'LANCER TEST PLR' quand prêt")

        controller = ParameterController(self.detector)
        controller.set_plr_callback(callback=self._on_ready_to_test)
        controller.run()

        return self.calibration_validated

    def _on_ready_to_test(self):
        """Callback déclenché par le bouton PLR"""
        self.calibration_validated = True

    def _analyze_results(self):
        """Calcule les métriques PLR"""
        print("\n🔬 ANALYSE DES RÉSULTATS...")

        if len(self.diameters) < 10:
            print("❌ Données insuffisantes")
            return

        diameters = np.array(self.diameters)
        timestamps = np.array(self.timestamps)

        # ─── Diamètre baseline (moyenne 5 premières secondes) ───
        baseline_mask = timestamps < self.baseline_duration
        baseline_diameter = np.mean(diameters[baseline_mask])

        # ─── Diamètre minimal (constriction maximale) ───
        stimulus_start = self.baseline_duration
        stimulus_end = stimulus_start + self.stimulus_duration
        stimulus_mask = (timestamps >= stimulus_start) & (timestamps <= stimulus_end + 2)
        min_diameter = np.min(diameters[stimulus_mask])
        min_time = timestamps[stimulus_mask][np.argmin(diameters[stimulus_mask])]

        # ─── Amplitude de constriction (%) ───
        amplitude = ((baseline_diameter - min_diameter) / baseline_diameter) * 100

        # ─── Latence (temps avant constriction) ───
        latency = min_time - stimulus_start

        # ─── Temps de récupération 75% ───
        recovery_target = baseline_diameter * 0.75
        recovery_mask = timestamps > stimulus_end
        recovery_diameters = diameters[recovery_mask]
        recovery_times = timestamps[recovery_mask]

        recovery_75 = None
        for i, d in enumerate(recovery_diameters):
            if d >= recovery_target:
                recovery_75 = recovery_times[i] - stimulus_end
                break

        # Sauvegarde métriques
        self.metrics = {
            'baseline_diameter_mm': round(baseline_diameter, 2),
            'min_diameter_mm': round(min_diameter, 2),
            'amplitude_percent': round(amplitude, 1),
            'latency_ms': round(latency * 1000, 0),
            'recovery_75_s': round(recovery_75, 2) if recovery_75 else None,
            'total_measures': len(self.diameters),
            'mean_confidence': round(np.mean(self.confidences), 1)
        }

        # Affichage
        print("\n" + "═" * 60)
        print("📊 RÉSULTATS DU TEST PLR")
        print("═" * 60)
        print(f"  Diamètre baseline    : {self.metrics['baseline_diameter_mm']} mm")
        print(f"  Diamètre minimal     : {self.metrics['min_diameter_mm']} mm")
        print(f"  Amplitude            : {self.metrics['amplitude_percent']} %")
        print(f"  Latence              : {self.metrics['latency_ms']} ms")
        print(f"  Récupération 75%     : {self.metrics['recovery_75_s']} s")
        print(f"  Confidence moyenne   : {self.metrics['mean_confidence']} %")
        print("═" * 60)

    def _save_results(self):
        """Sauvegarde les données brutes et métriques en CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Fichier données brutes
        raw_file = self.output_dir / f"plr_{timestamp}_raw.csv"
        with open(raw_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp_s', 'diameter_mm', 'confidence', 'stimulus_active'])
            for i in range(len(self.timestamps)):
                writer.writerow([
                    f"{self.timestamps[i]:.3f}",
                    f"{self.diameters[i]:.2f}",
                    f"{self.confidences[i]:.1f}",
                    int(self.stimulus_active[i])
                ])

        # Fichier métriques
        metrics_file = self.output_dir / f"plr_{timestamp}_metrics.csv"
        with open(metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['metric', 'value'])
            for key, value in self.metrics.items():
                writer.writerow([key, value])

        print(f"\n💾 Données sauvegardées :")
        print(f"  • {raw_file}")
        print(f"  • {metrics_file}")

    def _plot_results(self):
        """Génère et sauvegarde le graphique PLR"""

        # ✅ VÉRIFICATION DONNÉES AVANT PLOT
        if len(self.timestamps) == 0:
            print("\n❌ Impossible de générer le graphique : aucune donnée enregistrée")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        fig, ax = plt.subplots(figsize=(14, 7))

        # Tracé diamètre pupille
        ax.plot(self.timestamps, self.diameters, 'b-', linewidth=2.5, 
                label='Diamètre pupille', marker='o', markersize=3, alpha=0.8)

        # ✅ CALCUL SÉCURISÉ DES LIMITES
        max_time = max(self.timestamps) if self.timestamps else 18.0

        # Zones colorées
        ax.axvspan(0, self.baseline_duration, alpha=0.2, color='green', label='Baseline')
        ax.axvspan(self.baseline_duration, 
                   self.baseline_duration + self.stimulus_duration, 
                   alpha=0.3, color='yellow', label='Stimulation')
        ax.axvspan(self.baseline_duration + self.stimulus_duration, 
                   max_time, 
                   alpha=0.2, color='blue', label='Récupération')

        # Annotations métriques clés
        if 'baseline_diameter_mm' in self.metrics:
            ax.axhline(y=self.metrics['baseline_diameter_mm'], color='g', 
                       linestyle='--', alpha=0.5, linewidth=2, label='Baseline')

        if 'min_diameter_mm' in self.metrics:
            ax.axhline(y=self.metrics['min_diameter_mm'], color='r', 
                       linestyle='--', alpha=0.5, linewidth=2, label='Min')

        # Labels et mise en forme
        ax.set_xlabel('Temps (s)', fontsize=13, fontweight='bold')
        ax.set_ylabel('Diamètre pupille (mm)', fontsize=13, fontweight='bold')
        ax.set_title(f'Test PLR - {timestamp}\nAmplitude: {self.metrics.get("amplitude_percent", "N/A")}% | Latence: {self.metrics.get("latency_ms", "N/A")}ms', 
                     fontsize=15, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3, linestyle='--')

        # Limites axes
        ax.set_xlim(0, max_time + 1)

        # Sauvegarde
        plot_file = self.output_dir / f"plr_{timestamp}.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"  📊 Graphique : {plot_file}")

        plt.show()

# ═══════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        print("🔧 Initialisation de la caméra...")
        detector = PupilDetectorIR(camera_id=0)

        print("🧪 Création du test PLR...")
        plr = PLRTest(detector)

        if not plr.calibrate_with_gui():
            print("❌ Calibration annulée")
            sys.exit(0)  # ✅ sys est maintenant importé

        metrics = plr.run_test()

        if metrics:
            print("\n✅ Test PLR terminé avec succès !")
        else:
            print("\n❌ Test PLR échoué")

        # Nettoyage
        detector.cap.release()
        cv2.destroyAllWindows()

    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()
