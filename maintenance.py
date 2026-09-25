"""
maintenance.py
Mode maintenance : un simple fichier JSON dans instance/.
Il reste sur le serveur même si la base de données est remplacée (travail en local
puis renvoi de la base), et n'a besoin d'aucune migration.
"""
import json
import os
from datetime import datetime

from flask import current_app


def _chemin():
    return current_app.config.get('MAINTENANCE_FICHIER') or \
        os.path.join(current_app.instance_path, 'maintenance.json')


def etat():
    """Retourne le dict d'état si la maintenance est active, sinon None."""
    try:
        with open(_chemin(), encoding='utf-8') as f:
            data = json.load(f)
        return data if data.get('actif') else None
    except (OSError, ValueError):
        return None


def activer(message='', retour='', par=''):
    os.makedirs(os.path.dirname(_chemin()), exist_ok=True)
    with open(_chemin(), 'w', encoding='utf-8') as f:
        json.dump({
            'actif': True,
            'message': message.strip()[:600],
            'retour': retour.strip()[:120],
            'depuis': datetime.now().strftime('%d/%m/%Y à %Hh%M'),
            'par': par,
        }, f, ensure_ascii=False)


def desactiver():
    try:
        os.remove(_chemin())
    except OSError:
        pass
