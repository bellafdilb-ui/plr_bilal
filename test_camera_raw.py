"""
test_camera_raw.py
TEST PERFORMANCES BRUTES CAMÉRA
"""

import cv2
import time

# Configuration caméra
camera_id = 0
target_fps = 60
width = 640
height = 480

print("🔍 Test performances caméra...")
print(f"   Résolution : {width}x{height}")
print(f"   FPS cible  : {target_fps}")
print("-" * 50)

# Test 1 : MJPEG
print("\n📹 TEST 1 : MJPEG")
cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap.set(cv2.CAP_PROP_FPS, target_fps)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

actual_fps = cap.get(cv2.CAP_PROP_FPS)
actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"   Résolution réelle : {actual_w}x{actual_h}")
print(f"   FPS réel          : {actual_fps}")

frame_count = 0
start = time.perf_counter()
duration = 5  # 5 secondes de test

print(f"\n⏱️ Acquisition pendant {duration}s...")

while time.perf_counter() - start < duration:
    ret, frame = cap.read()
    if not ret:
        print("❌ Erreur lecture frame")
        break
    
    frame_count += 1
    
    # Affichage toutes les 60 frames
    if frame_count % 60 == 0:
        elapsed = time.perf_counter() - start
        current_fps = frame_count / elapsed
        print(f"   Frame {frame_count} | FPS instantané : {current_fps:.1f}")
        
        # Affiche l'image
        cv2.imshow("Test MJPEG", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()

elapsed = time.perf_counter() - start
avg_fps = frame_count / elapsed

print("\n" + "="*50)
print(f"📊 RÉSULTATS MJPEG")
print(f"   Frames capturées : {frame_count}")
print(f"   Durée            : {elapsed:.2f}s")
print(f"   FPS moyen        : {avg_fps:.1f}")
print("="*50)

# Test 2 : YUYV (si MJPEG échoue)
print("\n📹 TEST 2 : YUYV")
cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap.set(cv2.CAP_PROP_FPS, target_fps)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','U','Y','V'))
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

actual_fps = cap.get(cv2.CAP_PROP_FPS)
print(f"   FPS réel : {actual_fps}")

frame_count = 0
start = time.perf_counter()

while time.perf_counter() - start < duration:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame_count += 1
    
    if frame_count % 60 == 0:
        elapsed = time.perf_counter() - start
        current_fps = frame_count / elapsed
        print(f"   Frame {frame_count} | FPS : {current_fps:.1f}")
        
        cv2.imshow("Test YUYV", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()

elapsed = time.perf_counter() - start
avg_fps = frame_count / elapsed

print("\n" + "="*50)
print(f"📊 RÉSULTATS YUYV")
print(f"   Frames capturées : {frame_count}")
print(f"   Durée            : {elapsed:.2f}s")
print(f"   FPS moyen        : {avg_fps:.1f}")
print("="*50)

# Test 3 : Sans codec spécifique
print("\n📹 TEST 3 : AUTO")
cap = cv2.VideoCapture(camera_id)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap.set(cv2.CAP_PROP_FPS, target_fps)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

actual_fps = cap.get(cv2.CAP_PROP_FPS)
print(f"   FPS réel : {actual_fps}")

frame_count = 0
start = time.perf_counter()

while time.perf_counter() - start < duration:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame_count += 1
    
    if frame_count % 60 == 0:
        elapsed = time.perf_counter() - start
        current_fps = frame_count / elapsed
        print(f"   Frame {frame_count} | FPS : {current_fps:.1f}")
        
        cv2.imshow("Test AUTO", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()

elapsed = time.perf_counter() - start
avg_fps = frame_count / elapsed

print("\n" + "="*50)
print(f"📊 RÉSULTATS AUTO")
print(f"   Frames capturées : {frame_count}")
print(f"   Durée            : {elapsed:.2f}s")
print(f"   FPS moyen        : {avg_fps:.1f}")
print("="*50)

print("\n✅ Tests terminés")
print("💡 Utilise le codec avec le MEILLEUR FPS moyen")
