import secrets
from flask import Flask, redirect, url_for, session, request, abort
from config import Config
from models import db
from flask_login import LoginManager
from extensions import limiter


def create_app(test_config=None):
    """
    Fabrique de l'application Flask.
    test_config : dict optionnel pour surcharger la configuration en tests
                  (URI de DB, clé secrète, désactivation du rate-limiting…).
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # Surcharge éventuelle pour les tests (doit être appliquée AVANT db.init_app)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    limiter.init_app(app)

    # Table des archives : créée au démarrage si absente (évite une migration manuelle)
    with app.app_context():
        try:
            from models import Archive
            Archive.__table__.create(db.engine, checkfirst=True)
        except Exception:
            pass
        # Index déclarés dans models.py (index=True) : créés sur une base existante s'ils manquent
        for table in db.metadata.sorted_tables:
            for index in table.indexes:
                try:
                    index.create(db.engine, checkfirst=True)
                except Exception:
                    pass

    @app.before_request
    def garde_maintenance():
        """Pendant la maintenance, seul l'administrateur principal accède à la plateforme."""
        import maintenance
        from utils import est_admin_principal
        info = maintenance.etat()
        if not info or request.endpoint in ('static', 'api_backup'):
            return
        from flask_login import current_user as _cu
        from flask import jsonify, make_response, render_template
        if _cu.is_authenticated and est_admin_principal(_cu):
            return
        if request.endpoint == 'auth.login' and (request.method == 'POST' or request.args.get('admin')):
            return   # auth.login refuse ensuite tous les comptes sauf l'administrateur principal
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(ok=False, msg="La plateforme est en maintenance. Votre saisie n'a pas été "
                                         "enregistrée : réessayez après la maintenance."), 503
        resp = make_response(render_template('maintenance.html', info=info), 503)
        resp.headers['Retry-After'] = '120'
        return resp

    @app.context_processor
    def inject_maintenance():
        import maintenance
        from flask_login import current_user as _cu
        from utils import est_admin_principal
        return dict(maintenance_info=maintenance.etat(),
                    est_principal=_cu.is_authenticated and est_admin_principal(_cu))

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'warning'

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.template_filter('milliers')
    def milliers_filter(v):
        try:
            val = float(v or 0)
        except (TypeError, ValueError):
            val = 0.0
        return '{:,.0f}'.format(val).replace(',', ' ')

    @app.template_filter('fcfa')
    def fcfa_filter(v):
        """Format F CFA : séparateur milliers = espace, décimales exactes sans arrondi.
        Affiche le minimum de décimales nécessaires (0 à 3) pour représenter la valeur exacte."""
        try:
            val = float(v or 0)
            # Éliminer le bruit flottant en plafonnant à 3 décimales (précision max en milliers)
            val = round(val, 3)
            if val == int(val):
                return '{:,.0f}'.format(int(val)).replace(',', ' ')
            # Trouver le nombre minimal de décimales pour représenter la valeur exacte
            for d in (1, 2, 3):
                if round(val, d) == val:
                    return ('{:,.' + str(d) + 'f}').format(val).replace(',', ' ').replace('.', ',')
            return '{:,.3f}'.format(val).replace(',', ' ').replace('.', ',')
        except (TypeError, ValueError):
            return '0'

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

    @app.template_filter('loopsum')
    def loopsum_filter(iterable, attribute=None):
        """Sommation gauche-droite simple (boucle for depuis 0).
        Remplace |sum(attribute=...) pour les poids afin d'éviter les
        artefacts de la sommation par paires de Python 3.12+, qui donne
        des résultats légèrement différents d'une boucle for classique."""
        total = 0
        for obj in iterable:
            val = getattr(obj, attribute) if attribute else obj
            total += (val or 0)
        return total

    _MOIS_COURT = {
        'Janvier': 'Janv', 'Février': 'Fév', 'Mars': 'Mars', 'Avril': 'Avr',
        'Mai': 'Mai', 'Juin': 'Juin', 'Juillet': 'Juil', 'Août': 'Août',
        'Septembre': 'Sept', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Déc',
    }

    @app.template_filter('mois_court')
    def mois_court_filter(v):
        return _MOIS_COURT.get(str(v or '').strip(), str(v or ''))

    @app.url_defaults
    def version_fichiers_statiques(endpoint, values):
        # ?v=<date de modification> : force le navigateur à recharger CSS/JS après chaque mise à jour
        if endpoint == 'static' and 'filename' in values and 'v' not in values:
            import os as _os
            try:
                values['v'] = int(_os.stat(_os.path.join(app.static_folder, values['filename'])).st_mtime)
            except OSError:
                pass

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
                annee_active_val=active.annee if active else None,
            )
        except Exception:
            return dict(toutes_annees=[], annee_active_id=None)

    @app.after_request
    def secure_headers(response):
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "font-src 'self' cdnjs.cloudflare.com cdn.jsdelivr.net data:; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none';"
        )
        return response

    @app.before_request
    def sync_annee_session():
        """Synchronise l'année en session. Déconnecte immédiatement les comptes désactivés."""
        from flask_login import current_user as _cu, logout_user as _lo
        from models import Annee as _A
        from flask import flash as _flash
        if not _cu.is_authenticated:
            return
        # VUL-06 : invalider immédiatement tout compte désactivé par l'admin
        if not _cu.actif:
            _lo()
            session.clear()
            _flash('Votre compte a été désactivé. Contactez l\'administrateur.', 'warning')
            return redirect(url_for('auth.login'))
        if request.blueprint != 'auth':
            try:
                active = _A.query.filter_by(actif=True).first()
                if active and session.get('annee_id') != active.id:
                    old = session.get('annee')
                    session['annee_id'] = active.id
                    session['annee'] = active.annee
                    if old and old != active.annee:
                        _flash(
                            f"L'année PTA active a changé ({old} → {active.annee}). "
                            "Votre session a été mise à jour.",
                            'info'
                        )
            except Exception:
                pass

    @app.before_request
    def check_csrf():
        if request.method == 'POST' and request.blueprint != 'auth' and request.endpoint != 'api_backup':
            token = session.get('_csrf_token')
            # Accepte le token via formulaire HTML ou via header X-CSRF-Token (AJAX JSON)
            form_token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
            if not token or token != form_token:
                abort(403)

    # ── Route de déclenchement de la sauvegarde (appelée par cron-job.org) ──────
    # Méthode POST : token dans le corps (form: token=XXX ou JSON: {"token":"XXX"})
    # Configurer cron-job.org : méthode POST, body "token=VOTRE_TOKEN"
    @app.route('/api/backup', methods=['POST'])
    def api_backup():
        import os
        import hmac
        from flask import jsonify
        payload    = request.get_json(silent=True) or {}
        token_recu = request.form.get('token', '') or payload.get('token', '')
        config_path   = os.path.expanduser('~/.pta_backup_config')
        token_attendu = ''
        if os.path.exists(config_path):
            with open(config_path, encoding='utf-8') as f:
                for ligne in f:
                    if ligne.startswith('BACKUP_TOKEN='):
                        token_attendu = ligne.split('=', 1)[1].strip()
        if not token_attendu or not hmac.compare_digest(token_recu, token_attendu):
            abort(403)
        # Lancer la sauvegarde
        try:
            import importlib.util
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup_pta.py')
            spec = importlib.util.spec_from_file_location('backup_pta', script)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run()
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
    from pai import pai_bp
    from pei import pei_bp
    from budget import budget_bp
    from statspai import statspai_bp
    from pluriannuel import pluriannuel_bp

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
    app.register_blueprint(pai_bp, url_prefix='/pai')
    app.register_blueprint(pei_bp, url_prefix='/pei')
    app.register_blueprint(budget_bp, url_prefix='/budget')
    app.register_blueprint(statspai_bp, url_prefix='/statspai')
    app.register_blueprint(pluriannuel_bp, url_prefix='/pluriannuel')

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