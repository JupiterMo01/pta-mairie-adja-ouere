"""
extensions.py
Instances des extensions Flask partagées entre app.py et les blueprints.
Évite les imports circulaires.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialisé sans app ici ; app.init_app(limiter) dans create_app()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
