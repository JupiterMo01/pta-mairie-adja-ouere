from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models import User, Annee
from auth import auth_bp
from utils import log_audit, valider_mdp
from extensions import limiter, adresse_client

_MSG_LIMITE = 'Trop de tentatives de connexion. Veuillez patienter quelques minutes.'


def _cle_identifiant():
    """Compteur propre à chaque identifiant : un agent qui se trompe ne bloque pas ses collègues du même réseau."""
    return f"{adresse_client()}|{(request.form.get('login') or '').strip().lower()}"


def _echec(response):
    # Une connexion réussie redirige (302) : seules les tentatives échouées sont comptées
    return response.status_code != 302


@auth_bp.route('/')
@login_required
def index():
    # Tous les rôles atterrissent sur le tableau de bord
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute; 20 per hour', key_func=_cle_identifiant, methods=['POST'],
               deduct_when=_echec, error_message=_MSG_LIMITE)
@limiter.limit('30 per minute; 100 per hour', methods=['POST'],
               deduct_when=_echec, error_message=_MSG_LIMITE)
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(login=login_val, actif=True).first()

        if user and user.check_password(password):
            import maintenance
            info = maintenance.etat()
            from utils import est_admin_principal
            if info and not est_admin_principal(user):
                from flask import make_response
                return make_response(render_template('maintenance.html', info=info), 503)
            login_user(user, remember=False)   # pas de cookie persistant — session expire à la fermeture
            session.permanent = True           # applique PERMANENT_SESSION_LIFETIME (8h)
            annee_active = Annee.query.filter_by(actif=True).first()
            if annee_active:
                session['annee_id'] = annee_active.id
                session['annee'] = annee_active.annee
            log_audit('connexion', f"Connexion réussie — {user.role_label}")
            flash(f'Bienvenue, {user.prenom} {user.nom} !', 'success')
            # Validation du paramètre next : accepter uniquement les URLs internes
            # (commençant par '/' mais pas '//' qui est un protocol-relative redirect)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/') or next_page.startswith('//'):
                next_page = None   # URL externe, vide ou suspecte → ignorée
            return redirect(next_page or url_for('auth.index'))
        else:
            log_audit('echec_connexion', f"Échec connexion pour l'identifiant : {login_val}")
            flash('Identifiant ou mot de passe incorrect.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_audit('deconnexion')
    logout_user()
    session.pop('annee_id', None)
    session.pop('annee', None)
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/mdp-oublie')
def mdp_oublie():
    return render_template('auth/mdp_oublie.html')


@auth_bp.route('/changer-mot-de-passe', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        # Vérification CSRF explicite (blueprint auth exclu du middleware global)
        tok = session.get('_csrf_token')
        form_tok = request.form.get('_csrf_token')
        if not tok or tok != form_tok:
            from flask import abort
            abort(403)
        ancien = request.form.get('ancien_mdp', '').strip()
        nouveau = request.form.get('nouveau_mdp', '').strip()
        confirm = request.form.get('confirm_mdp', '').strip()

        erreur_mdp = valider_mdp(nouveau)
        if not current_user.check_password(ancien):
            flash('Mot de passe actuel incorrect.', 'danger')
        elif erreur_mdp:
            flash(erreur_mdp, 'danger')
        elif nouveau != confirm:
            flash('Le nouveau mot de passe et la confirmation ne correspondent pas.', 'danger')
        else:
            from models import db
            current_user.set_password(nouveau)
            db.session.commit()
            log_audit('mdp_change', "Mot de passe modifié par l'utilisateur")
            flash('Mot de passe modifié avec succès !', 'success')
            return redirect(url_for('auth.index'))

    return render_template('auth/change_password.html')