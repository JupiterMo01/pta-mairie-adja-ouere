import os
from datetime import timedelta

class Config:
    # SECRET_KEY DOIT venir d'une variable d'environnement — aucune valeur
    # par défaut n'est fournie ici pour éviter tout secret codé en dur dans
    # un dépôt public. Si la variable n'est pas définie, l'app refuse de démarrer.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError(
            "La variable d'environnement SECRET_KEY doit être définie. "
            "Sur PythonAnywhere, ajoutez dans wsgi.py AVANT l'import de l'app :\n"
            "  import os; os.environ['SECRET_KEY'] = 'une-longue-chaine-aleatoire-unique'\n"
            "Générez-en une avec : python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    SQLALCHEMY_DATABASE_URI = 'sqlite:///pta_mairie.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True

    # Sessions expirées après 8 h d'inactivité (agents publics sur postes partagés)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True   # JS ne peut pas lire le cookie de session
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protection CSRF complémentaire
    # True en production (HTTPS PythonAnywhere), False en développement local (HTTP)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') != 'development'