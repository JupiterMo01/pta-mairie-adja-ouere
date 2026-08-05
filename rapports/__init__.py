from flask import Blueprint

rapports_bp = Blueprint('rapports', __name__)

from rapports import routes  # noqa: E402, F401