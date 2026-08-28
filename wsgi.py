"""
Fichier WSGI pour PythonAnywhere.
PythonAnywhere cherche automatiquement une variable nommée 'application'.

IMPORTANT : Ce fichier sert de référence documentaire.
Le vrai fichier exécuté par PythonAnywhere est :
  /var/www/jupi01_pythonanywhere_com_wsgi.py
(éditable depuis la console bash ou le Web tab)

Leçon apprise : la console bash utilise Python 3.13 mais le serveur WSGI
tourne en Python 3.10. Ne jamais coder en dur la version Python dans le chemin
— utiliser site.getusersitepackages() pour détecter automatiquement le bon dossier.

Packages à installer pour Python 3.10 (si manquants) :
  python3.10 -m pip install --user flask-limiter python-docx
"""
import sys
import os
import time
import site

# Dossier du projet
path = '/home/jupi01/pta_mairie'
if path not in sys.path:
    sys.path.insert(0, path)

# Packages utilisateur — chemin dynamique selon la version Python réelle du WSGI
# (PythonAnywhere WSGI tourne en Python 3.10, pas 3.13 comme la console bash)
user_packages = site.getusersitepackages()
if user_packages not in sys.path:
    sys.path.insert(1, user_packages)

# Assure que le dossier instance/ existe pour la base de données
os.makedirs(os.path.join(path, 'instance'), exist_ok=True)

# Fuseau horaire Bénin
os.environ['TZ'] = 'Africa/Porto-Novo'
time.tzset()

from app import create_app
application = create_app()
