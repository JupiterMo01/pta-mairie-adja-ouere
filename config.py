import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'pta-mairie-adja-ouere-2026-xK9mP')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///pta_mairie.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True