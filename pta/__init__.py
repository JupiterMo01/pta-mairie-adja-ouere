from flask import Blueprint

pta_bp = Blueprint('pta', __name__)

from pta import routes  # noqa: E402, F401