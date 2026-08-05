from flask import Blueprint
exportation_bp = Blueprint('exportation', __name__,
                            template_folder='../templates/exportation')
from exportation import routes  # noqa: E402, F401