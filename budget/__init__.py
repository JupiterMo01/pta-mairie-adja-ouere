from flask import Blueprint
budget_bp = Blueprint('budget', __name__, template_folder='../templates/budget')
from . import routes  # noqa: F401, E402
