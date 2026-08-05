from flask import Blueprint

svcpta_bp = Blueprint('svcpta', __name__, template_folder='../templates/svcpta')

from svcpta import routes  # noqa: E402, F401