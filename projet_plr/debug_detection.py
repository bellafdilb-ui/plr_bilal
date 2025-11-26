"""
Script de debug pour visualiser la détection.
"""

import cv2
import numpy as np
from camera_engine import CameraEngine


def create_synthetic_pupil(size=(640, 480), pupil_center=(320, 240), pupil_radius=50):
    """Crée une image test"""
    width, height = size
    img = np.ones((height, width, 3), dtype=np.uint8) * 180  # Fond gris clair
    cv2.circle(img, pupil_center, pupil_radius, (0, 0, 0), -1)  # Pupille noire
    return img


def debug_detection():
    """Teste la détection étape par étape"""
    camera = CameraEngine(camera_index=0)
    
    # Image synthétique
    img = create_synthetic_pupil()
    
    print("\n🔍 DEBUG DÉTECTION")
    print(f"Paramètres caméra:")
    print(f"  - threshold_value: {camera.threshold_value}")
    print(f"  - blur_kernel: {camera.blur_kernel}")
    print(f"  - min_area: {camera.min_area}")
    print(f"  - max_area: {camera.max_area}")
    print(f"  - min_circularity: {camera.min_circularity}")
    
    # Conversion en niveaux de gris
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"\n📊 Statistiques image:")
    print(f"  - Min gray: {gray.min()}")
    print(f"  - Max gray: {gray.max()}")
    print(f"  - Mean gray: {gray.mean():.1f}")
    
    # Flou
    blurred = cv2.GaussianBlur(gray, (camera.blur_kernel, camera.blur_kernel), 0)
    
    # Seuillage
    _, binary = cv2.threshold(blurred, camera.threshold_value, 255, cv2.THRESH_BINARY_INV)
    
    # Contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"\n🔎 Contours trouvés: {len(contours)}")
    
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0
        
        print(f"\nContour {i}:")
        print(f"  - Area: {area:.1f} (min={camera.min_area}, max={camera.max_area})")
        print(f"  - Circularity: {circularity:.3f} (min={camera.min_circularity})")
        
        if area >= camera.min_area and area <= camera.max_area and circularity >= camera.min_circularity:
            print(f"  ✅ VALIDE")
        else:
            print(f"  ❌ REJETÉ")
    
    # Détection complète
    pupil = camera._detect_pupil_internal(img)
    print(f"\n🎯 Résultat final: {'✅ DÉTECTÉ' if pupil else '❌ NON DÉTECTÉ'}")
    if pupil:
        print(f"  - Centre: {pupil['center']}")
        print(f"  - Diamètre: {pupil['diameter_px']:.1f}px")
    
    # Affichage visuel
    cv2.imshow("1. Original", img)
    cv2.imshow("2. Gray", gray)
    cv2.imshow("3. Blurred", blurred)
    cv2.imshow("4. Binary", binary)
    
    # Frame avec contours
    frame_contours = img.copy()
    cv2.drawContours(frame_contours, contours, -1, (0, 255, 0), 2)
    cv2.imshow("5. Contours", frame_contours)
    
    print("\n⌨️ Appuie sur une touche pour fermer...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    camera.release()


if __name__ == "__main__":
    debug_detection()
