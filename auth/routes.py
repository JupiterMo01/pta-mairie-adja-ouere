from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models import User, Annee
from auth import auth_bp
from utils import log_audit


@auth_bp.route('/')
@login_required
def index():
    # Tous les rôles atterrissent sur le tableau de bord
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(login=login_val, actif=True).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            annee_active = Annee.query.filter_by(actif=True).first()
            if annee_active:
                session['annee_id'] = annee_active.id
                session['annee'] = annee_active.annee
            log_audit('connexion', f"Connexion réussie — {user.role_label}")
            flash(f'Bienvenue, {user.prenom} {user.nom} !', 'success')
            next_page = request.args.get('next')
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
        ancien = request.form.get('ancien_mdp', '').strip()
        nouveau = request.form.get('nouveau_mdp', '').strip()
        confirm = request.form.get('confirm_mdp', '').strip()

        if not current_user.check_password(ancien):
            flash('Mot de passe actuel incorrect.', 'danger')
        elif len(nouveau) < 6:
            flash('Le nouveau mot de passe doit contenir au moins 6 caractères.', 'danger')
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