from flask import Blueprint

suivi_bp = Blueprint('suivi', __name__, template_folder='../templates')

from suivi import routes  # noqa: F401,E402  – enregistrement des routes
from suivi import point   # noqa: F401,E402  – Point des activités
