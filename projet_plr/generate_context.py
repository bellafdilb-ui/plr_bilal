import os

# Liste des extensions à inclure
EXTENSIONS = {'.py', '.json', '.md', '.txt'}
# Dossiers à ignorer
IGNORE_DIRS = {'__pycache__', '.git', 'recordings', 'data', 'venv', 'env', 'biomed', '.pytest_cache'}
# Fichiers à ignorer
IGNORE_FILES = {'generate_context.py', 'vet_data.db'}

output_file = "FULL_PROJECT_CONTEXT.txt"

def is_ignored(path):
    parts = path.split(os.sep)
    for p in parts:
        if p in IGNORE_DIRS:
            return True
    return False

with open(output_file, 'w', encoding='utf-8') as outfile:
    # On écrit d'abord l'index (si vous avez créé un fichier PROJECT_INDEX.md, sinon optionnel)
    outfile.write("--- DEBUT DU CONTEXTE PROJET ---\n\n")
    
    for root, dirs, files in os.walk("."):
        # Filtrer les dossiers ignorés pour ne pas descendre dedans
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if file in IGNORE_FILES:
                continue
                
            _, ext = os.path.splitext(file)
            if ext in EXTENSIONS:
                file_path = os.path.join(root, file)
                if is_ignored(file_path):
                    continue
                
                outfile.write(f"\n{'='*50}\n")
                outfile.write(f"FICHIER : {file_path}\n")
                outfile.write(f"{'='*50}\n\n")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"# Erreur lecture fichier: {e}\n")
                
                outfile.write("\n")

print(f"✅ Terminé ! Tout le code est dans : {output_file}")