from flask import Blueprint

pai_bp = Blueprint('pai', __name__, template_folder='../templates')

from pai import routes  # noqa: F401,E402  – enregistrement des routes
