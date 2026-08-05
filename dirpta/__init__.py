from flask import Blueprint

dirpta_bp = Blueprint('dirpta', __name__, template_folder='../templates/dirpta')

from dirpta import routes  # noqa: E402, F401
