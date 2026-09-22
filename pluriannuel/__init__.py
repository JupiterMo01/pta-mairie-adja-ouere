from flask import Blueprint
pluriannuel_bp = Blueprint('pluriannuel', __name__, template_folder='../templates/pluriannuel')
from . import routes
