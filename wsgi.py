"""
Fichier WSGI pour PythonAnywhere.
PythonAnywhere cherche automatiquement une variable nommée 'application'.
"""
import sys
import os

# Remplacer 'VOTRE_USERNAME' par votre nom d'utilisateur PythonAnywhere
# et 'pta_mairie' par le nom du dossier cloné
path = '/home/VOTRE_USERNAME/pta_mairie'
if path not in sys.path:
    sys.path.insert(0, path)

# Assure que le dossier instance/ existe pour la base de données
os.makedirs(os.path.join(path, 'instance'), exist_ok=True)

from app import create_app
application = create_app()