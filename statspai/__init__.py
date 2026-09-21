from flask import Blueprint
statspai_bp = Blueprint('statspai', __name__, template_folder='../templates/statspai')
from . import routes
