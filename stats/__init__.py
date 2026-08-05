from flask import Blueprint

stats_bp = Blueprint('stats', __name__)

from stats import routes  # noqa: E402, F401