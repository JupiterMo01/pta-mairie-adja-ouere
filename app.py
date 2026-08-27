import secrets
from flask import Flask, redirect, url_for, session, request, abort
from config import Config
from models import db
from flask_login import LoginManager
from extensions import limiter


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    limiter.init_app(app)

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
            return '{:.2f}'.format(float(v or 0)).replace('.', ',')
        except (TypeError, ValueError):
            return '0,00'

    @app.template_filter('pct_nat')
    def pct_nat_filter(v):
        try:
            s = '{:.2f}'.format(float(v or 0)).rstrip('0').rstrip('.')
            return s.replace('.', ',')
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

    @app.context_processor
    def inject_annees():
        """Injecte la liste de toutes les années et l'id de l'année active
        dans tous les templates — permet le sélecteur d'année admin."""
        from models import Annee as _Annee
        try:
            toutes = _Annee.query.order_by(_Annee.annee.desc()).all()
            active = next((a for a in toutes if a.actif), None)
            return dict(
                toutes_annees=toutes,
                annee_active_id=active.id if active else None,
            )
        except Exception:
            return dict(toutes_annees=[], annee_active_id=None)

    @app.before_request
    def check_csrf():
        if request.method == 'POST' and request.blueprint != 'auth':
            token = session.get('_csrf_token')
            # Accepte le token via formulaire HTML ou via header X-CSRF-Token (AJAX JSON)
            form_token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
            if not token or token != form_token:
                abort(403)

    # ── Route de déclenchement de la sauvegarde (appelée par cron-job.org) ──────
    @app.route('/api/backup')
    def api_backup():
        import os
        from flask import jsonify
        # Vérification du token secret
        token_recu  = request.args.get('token', '')
        config_path = os.path.expanduser('~/.pta_backup_config')
        token_attendu = ''
        if os.path.exists(config_path):
            with open(config_path, encoding='utf-8') as f:
                for ligne in f:
                    if ligne.startswith('BACKUP_TOKEN='):
                        token_attendu = ligne.split('=', 1)[1].strip()
        if not token_attendu or token_recu != token_attendu:
            abort(403)
        # Lancer la sauvegarde
        try:
            import importlib.util
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup_pta.py')
            spec = importlib.util.spec_from_file_location('backup_pta', script)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return jsonify({'status': 'ok', 'message': 'Sauvegarde effectuée'})
        except Exception as e:
            return jsonify({'status': 'erreur', 'message': str(e)}), 500

    from auth import auth_bp
    from admin import admin_bp
    from pta import pta_bp
    from biblio import biblio_bp
    from stats import stats_bp
    from dirpta import dirpta_bp
    from svcpta import svcpta_bp
    from exportation import exportation_bp
    from suivi import suivi_bp
    from dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(pta_bp, url_prefix='/pta')
    app.register_blueprint(biblio_bp, url_prefix='/biblio')
    app.register_blueprint(stats_bp, url_prefix='/stats')
    app.register_blueprint(dirpta_bp, url_prefix='/dirpta')
    app.register_blueprint(svcpta_bp, url_prefix='/svcpta')
    app.register_blueprint(exportation_bp, url_prefix='/exportation')
    app.register_blueprint(suivi_bp, url_prefix='/suivi')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    # Gestionnaire d'erreur 429 (trop de tentatives de connexion)
    from flask import render_template as _rt
    @app.errorhandler(429)
    def trop_de_requetes(e):
        return _rt('auth/login.html',
                   erreur_limite="Trop de tentatives de connexion. Veuillez patienter quelques minutes avant de réessayer."), 429

    return app


if __name__ == '__main__':
    import os as _os, secrets as _sec
    # En local (développement) : générer une clé temporaire si absente
    # Cette clé change à chaque redémarrage — normal en dev, jamais en prod
    if not _os.environ.get('SECRET_KEY'):
        _os.environ['SECRET_KEY'] = _sec.token_hex(32)
    app = create_app()
    with app.app_context():
        db.create_all()
    # host='0.0.0.0' rend l'app accessible sur le réseau WiFi local
    app.run(host='0.0.0.0', port=5000, debug=False)