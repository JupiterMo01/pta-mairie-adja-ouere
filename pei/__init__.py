from flask import Blueprint

pei_bp = Blueprint('pei', __name__, template_folder='../templates/pei')

from . import routes  # noqa: F401, E402
