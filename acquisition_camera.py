import cv2
import os
from datetime import datetime

def acquire_video(output_dir="output", camera_index=0, backend=cv2.CAP_MSMF, resolution=(640, 480), fps=30):
    """
    Enregistre une vidéo depuis une caméra avec OpenCV.

    Args:
        output_dir (str): Dossier de sortie.
        camera_index (int): Index de la caméra.
        backend (int): Backend OpenCV (ex: cv2.CAP_MSMF).
        resolution (tuple): Résolution (largeur, hauteur).
        fps (int): Frames par seconde.
    """
    # Crée le dossier de sortie s'il n'existe pas
    os.makedirs(output_dir, exist_ok=True)

    # Initialise la caméra
    cap = cv2.VideoCapture(camera_index, backend)
    if not cap.isOpened():
        print("❌ Impossible d'ouvrir la caméra.")
        return

    # Configure la résolution et le FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    cap.set(cv2.CAP_PROP_FPS, fps)

    # Génère un nom de fichier unique
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"video_{timestamp}.avi")

    # Définit le codec et crée le VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(output_file, fourcc, fps, resolution)

    print(f"🎥 Enregistrement démarré (Appuyez sur 'q' pour arrêter)...")
    print(f"   → Fichier: {output_file}")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Erreur de capture.")
            break

        # Affiche la vidéo en temps réel
        cv2.imshow("Acquisition", frame)
        out.write(frame)  # Enregistre la frame

        # Arrêt avec 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Libère les ressources
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("✅ Enregistrement terminé.")

if __name__ == "__main__":
    acquire_video()
