import secrets
from flask import Flask, redirect, url_for, session, request, abort
from config import Config
from models import db
from flask_login import LoginManager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'warning'

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.template_filter('milliers')
    def milliers_filter(v):
        try:
            val = float(v or 0)
        except (TypeError, ValueError):
            val = 0.0
        return '{:,.0f}'.format(val).replace(',', ' ')

    @app.template_filter('pct')
    def pct_filter(v):
        try:
            return '{:.2f}'.format(float(v or 0))
        except (TypeError, ValueError):
            return '0.00'

    @app.template_filter('pct_nat')
    def pct_nat_filter(v):
        try:
            return '{:.2f}'.format(float(v or 0)).rstrip('0').rstrip('.')
        except (TypeError, ValueError):
            return '0'

    _MOIS_COURT = {
        'Janvier': 'Janv', 'Février': 'Fév', 'Mars': 'Mars', 'Avril': 'Avr',
        'Mai': 'Mai', 'Juin': 'Juin', 'Juillet': 'Juil', 'Août': 'Août',
        'Septembre': 'Sept', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Déc',
    }

    @app.template_filter('mois_court')
    def mois_court_filter(v):
        return _MOIS_COURT.get(str(v or '').strip(), str(v or ''))

    @app.context_processor
    def inject_csrf():
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(24)
        return dict(csrf_token=session['_csrf_token'])

    @app.before_request
    def check_csrf():
        if request.method == 'POST' and request.blueprint != 'auth':
            token = session.get('_csrf_token')
            form_token = request.form.get('_csrf_token')
            if not token or token != form_token:
                abort(403)

    from auth import auth_bp
    from admin import admin_bp
    from pta import pta_bp
    from suivi import suivi_bp
    from rapports import rapports_bp
    from biblio import biblio_bp
    from stats import stats_bp
    from dirpta import dirpta_bp
    from svcpta import svcpta_bp
    from exportation import exportation_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(pta_bp, url_prefix='/pta')
    app.register_blueprint(suivi_bp, url_prefix='/suivi')
    app.register_blueprint(rapports_bp, url_prefix='/rapports')
    app.register_blueprint(biblio_bp, url_prefix='/biblio')
    app.register_blueprint(stats_bp, url_prefix='/stats')
    app.register_blueprint(dirpta_bp, url_prefix='/dirpta')
    app.register_blueprint(svcpta_bp, url_prefix='/svcpta')
    app.register_blueprint(exportation_bp, url_prefix='/exportation')

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    # host='0.0.0.0' rend l'app accessible sur le réseau WiFi local
    app.run(host='0.0.0.0', port=5000, debug=False)