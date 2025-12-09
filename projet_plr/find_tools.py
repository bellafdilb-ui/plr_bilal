import sys
from pathlib import Path

env = Path(sys.prefix)
print(f"Recherche dans : {env}")

# 1. Chercher LINGUIST (L'interface pour traduire)
linguist = next(env.rglob("linguist.exe"), None)
if linguist:
    print(f"\n--- COMMANDE 1 : TRADUIRE ---")
    print(f'& "{linguist}" translations/app_en.ts')
else:
    print("\n❌ linguist.exe introuvable.")

# 2. Chercher LRELEASE (Le compilateur)
lrelease = next(env.rglob("lrelease.exe"), None)
if lrelease:
    print(f"\n--- COMMANDE 2 : COMPILER ---")
    print(f'& "{lrelease}" translations/app_en.ts')
else:
    print("\n❌ lrelease.exe introuvable.")