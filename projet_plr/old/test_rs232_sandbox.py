import serial
import serial.tools.list_ports
import threading
import time
import sys

def listen_to_port(ser):
    """
    Thread secondaire : Écoute le port série en permanence 
    et affiche les données reçues dès qu'elles arrivent.
    """
    while True:
        try:
            if ser.in_waiting > 0:
                # Lecture de la ligne (décodage utf-8, ignore les erreurs de caractères)
                data = ser.readline().decode('utf-8', errors='ignore').strip()
                if data:
                    print(f"\n[MODULE] {data}")
        except OSError:
            # Port fermé ou déconnecté physiquement
            break 
        except Exception as e:
            print(f"\nErreur de lecture : {e}")
            break
        time.sleep(0.1)

def print_menu():
    print("\n--- MENU COMMANDES ---")
    print("1. Initialisation (depart)")
    print("2. Flash BLEU (200ms)")
    print("3. Flash ROUGE (1s)")
    print("4. Flash BLANC (50ms)")
    print("5. Arrêt Flash (arret_flash)")
    print("6. Lire Version")
    print("7. Lire Etat Bouton")
    print("0. Quitter")
    print("----------------------")
    print("Ou tapez une commande manuelle (ex: Type : commande, Commande :allume_ambiance)")

def send_sequence(ser, cmds):
    """Envoie une liste de commandes avec une petite pause."""
    if isinstance(cmds, str):
        cmds = [cmds]
    
    for cmd in cmds:
        print(f"Envoi > {cmd}")
        ser.write((cmd + "\n").encode('utf-8'))
        time.sleep(0.1)

def main():
    print("=== SANDBOX RS232 (Test Hardware) ===")
    
    # 1. Détection automatique du port
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ Aucun port COM détecté sur la machine.")
        return

    selected_port = None
    device_name = "Inconnu"

    # Stratégie : On cherche un port avec "USB" dans la description
    for p in ports:
        if "USB" in p.description.upper():
            selected_port = p.device
            device_name = p.description
            break
    
    # Fallback : Si aucun port USB explicite, on prend le premier
    if selected_port is None:
        selected_port = ports[0].device
        device_name = ports[0].description

    print(f"✅ L'appareil '{device_name}' est bien branché dans le port {selected_port}.")

    # 3. Connexion (Baudrate 115200, Timeout 1s)
    try:
        ser = serial.Serial(selected_port, 115200, timeout=1)
        print(f"✅ Connecté à {selected_port} (115200 bauds).") 
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return

    # 4. Démarrage de l'écoute en arrière-plan
    listener = threading.Thread(target=listen_to_port, args=(ser,), daemon=True)
    listener.start()

    print_menu()

    # 5. Boucle principale (Envoi)
    try:
        while True:
            user_input = input("\nChoix > ").strip()
            
            if user_input == "0":
                break
            elif user_input == "1":
                send_sequence(ser, "depart")
            elif user_input == "2":
                # Séquence Bleu 200ms
                cmds = [
                    "Type : commande, Commande :ecrire_couleur_flash , valeur: bleu",
                    "Type : commande, Commande :ecrire_duree_flash_us , valeur: 200000",
                    "Type : commande, Commande :depart_flash"
                ]
                send_sequence(ser, cmds)
            elif user_input == "3":
                # Séquence Rouge 1s
                cmds = [
                    "Type : commande, Commande :ecrire_couleur_flash , valeur: rouge",
                    "Type : commande, Commande :ecrire_duree_flash_us , valeur: 1000000",
                    "Type : commande, Commande :depart_flash"
                ]
                send_sequence(ser, cmds)
            elif user_input == "4":
                # Séquence Blanc 50ms
                cmds = [
                    "Type : commande, Commande :ecrire_couleur_flash , valeur: blanc",
                    "Type : commande, Commande :ecrire_duree_flash_us , valeur: 50000",
                    "Type : commande, Commande :depart_flash"
                ]
                send_sequence(ser, cmds)
            elif user_input == "5":
                send_sequence(ser, "Type : commande, Commande :arret_flash")
            elif user_input == "6":
                send_sequence(ser, "Type : commande, Commande :version")
            elif user_input == "7":
                send_sequence(ser, "Type : commande, Commande :lire_etat_bouton")
            else:
                # Commande manuelle
                if ser.is_open and user_input:
                    ser.write((user_input + "\n").encode('utf-8'))
            
    except KeyboardInterrupt:
        print("\nArrêt du script...")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print("Port fermé.")

if __name__ == "__main__":
    main()