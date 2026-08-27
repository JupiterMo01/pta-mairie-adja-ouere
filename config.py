import os
from datetime import timedelta

class Config:
    # ⚠️  Définir la variable d'environnement SECRET_KEY sur le serveur.
    # Sur PythonAnywhere : ajouter dans le fichier wsgi.py, AVANT l'import de l'app :
    #   import os; os.environ['SECRET_KEY'] = 'une-longue-chaine-aleatoire-unique'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'pta-mairie-adja-ouere-2026-xK9mP')

    SQLALCHEMY_DATABASE_URI = 'sqlite:///pta_mairie.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True

    # Sessions expirées après 8 h d'inactivité (agents publics sur postes partagés)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True   # JS ne peut pas lire le cookie de session
    SESSION_COOKIE_SAMESITE = 'Lax' # Protection CSRF complémentaire