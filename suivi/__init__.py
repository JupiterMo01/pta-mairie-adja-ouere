from flask import Blueprint

suivi_bp = Blueprint('suivi', __name__)

from suivi import routes  # noqa: E402, F401