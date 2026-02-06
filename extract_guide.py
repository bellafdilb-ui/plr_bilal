import re
import os

def extract_clean_html():
    source_file = "index.html"
    output_file = "guide_final_propre.html"

    if not os.path.exists(source_file):
        print(f"❌ Erreur : Le fichier {source_file} est introuvable.")
        return

    # 1. Lire le fichier conteneur
    with open(source_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 2. Chercher le contenu entre les accents graves (backticks) de la variable JS
    # On cherche : const USER_GUIDE_HTML = `...contenu...`;
    pattern = r"const USER_GUIDE_HTML = `(.*?)`;"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        clean_html = match.group(1)
        
        # 3. Sauvegarder le contenu pur dans un nouveau fichier
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(clean_html)
        
        print(f"✅ Extraction réussie !")
        print(f"📄 Nouveau fichier créé : {output_file}")
        print("👉 Vous pouvez maintenant ouvrir ce fichier et l'imprimer en PDF sans l'interface autour.")
    else:
        print("❌ Impossible de trouver la variable USER_GUIDE_HTML dans le fichier.")

if __name__ == "__main__":
    extract_clean_html()