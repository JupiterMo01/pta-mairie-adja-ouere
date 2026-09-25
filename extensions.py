"""
extensions.py
Instances des extensions Flask partagées entre app.py et les blueprints.
Évite les imports circulaires.
"""
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def adresse_client():
    """IP réelle du visiteur : PythonAnywhere la transmet dans X-Real-IP (son proxy l'écrase)."""
    return (request.headers.get('X-Real-IP') or '').strip() or get_remote_address()


# Initialisé sans app ici ; app.init_app(limiter) dans create_app()
limiter = Limiter(key_func=adresse_client, default_limits=[])
