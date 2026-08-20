from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../templates')

from dashboard import routes  # noqa: F401,E402  – enregistrement des routes
