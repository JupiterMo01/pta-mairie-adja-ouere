from flask import Blueprint
biblio_bp = Blueprint('biblio', __name__)
from biblio import routes