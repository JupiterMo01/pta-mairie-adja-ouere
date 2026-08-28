"""
Fichier WSGI pour PythonAnywhere.
PythonAnywhere cherche automatiquement une variable nommée 'application'.
"""
import sys
import os
import site

# Dossier du projet
path = '/home/jupi01/pta_mairie'
if path not in sys.path:
    sys.path.insert(0, path)

# Packages installés avec pip (sans virtualenv) → ~/.local/lib/python3.x/site-packages
# Nécessaire quand PythonAnywhere n'utilise pas de virtualenv
site.addusersite()
user_packages = '/home/jupi01/.local/lib/python3.13/site-packages'
if user_packages not in sys.path:
    sys.path.insert(1, user_packages)

# Assure que le dossier instance/ existe pour la base de données
os.makedirs(os.path.join(path, 'instance'), exist_ok=True)

from app import create_app
application = create_app()