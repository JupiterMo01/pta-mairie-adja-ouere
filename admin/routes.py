from functools import wraps
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
import json
from models import db, User, Direction, Service, Annee, StructureExterne, PTABackup, Programme, Projet, Activite, Tache
from admin import admin_bp


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ('admin_editeur', 'admin_lecteur'):
            flash('Accès refusé.', 'danger')
            return redirect(url_for('pta.global_pta'))
        return f(*args, **kwargs)
    return decorated


def editeur_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin_editeur':
            flash('Accès refusé. Réservé aux éditeurs.', 'danger')
            return redirect(url_for('pta.global_pta'))
        return f(*args, **kwargs)
    return decorated


# ─── Tableau de bord ────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def index():
    stats = {
        'users': User.query.count(),
        'directions': Direction.query.count(),
        'services': Service.query.count(),
        'annees': Annee.query.count(),
    }
    return render_template('admin/index.html', stats=stats)


# ─── Utilisateurs ───────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    users = User.query.order_by(User.nom).all()
    directions = Direction.query.order_by(Direction.nom).all()
    services = Service.query.order_by(Service.nom).all()
    return render_template('admin/users.html', users=users,
                           directions=directions, services=services)


@admin_bp.route('/users/add', methods=['POST'])
@editeur_required
def user_add():
    nom = request.form.get('nom', '').strip()
    prenom = request.form.get('prenom', '').strip()
    login_val = request.form.get('login', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', '').strip()
    direction_id = request.form.get('direction_id') or None
    service_id = request.form.get('service_id') or None

    if not all([nom, prenom, login_val, password, role]):
        flash('Veuillez remplir tous les champs obligatoires.', 'danger')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(login=login_val).first():
        flash(f"L'identifiant « {login_val} » est déjà utilisé.", 'danger')
        return redirect(url_for('admin.users'))

    user = User(
        nom=nom, prenom=prenom, login=login_val, role=role,
        direction_id=int(direction_id) if direction_id else None,
        service_id=int(service_id) if service_id else None,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'Utilisateur {prenom} {nom} créé.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@editeur_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    directions = Direction.query.order_by(Direction.nom).all()
    services = Service.query.order_by(Service.nom).all()

    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        role = request.form.get('role', '').strip()
        if not all([nom, prenom, role]):
            flash('Nom, prénom et rôle sont obligatoires.', 'danger')
            return redirect(url_for('admin.user_edit', user_id=user_id))
        user.nom = nom
        user.prenom = prenom
        user.role = role
        direction_id = request.form.get('direction_id') or None
        service_id = request.form.get('service_id') or None
        try:
            user.direction_id = int(direction_id) if direction_id else None
            user.service_id = int(service_id) if service_id else None
        except (ValueError, TypeError):
            flash('Identifiant de direction ou service invalide.', 'danger')
            return redirect(url_for('admin.user_edit', user_id=user_id))
        user.actif = ('actif' in request.form)
        new_pw = request.form.get('password', '').strip()
        if new_pw:
            user.set_password(new_pw)
        db.session.commit()
        flash('Utilisateur mis à jour.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', user=user,
                           directions=directions, services=services)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@editeur_required
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.login == 'admin' and user.actif:
        flash('Impossible de désactiver le compte administrateur principal.', 'danger')
        return redirect(url_for('admin.users'))
    user.actif = not user.actif
    db.session.commit()
    etat = 'activé' if user.actif else 'désactivé'
    flash(f'{user.prenom} {user.nom} {etat}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@editeur_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.login == 'admin':
        flash('Impossible de supprimer le compte administrateur principal.', 'danger')
        return redirect(url_for('admin.users'))
    if user.id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'danger')
        return redirect(url_for('admin.users'))
    nom = f'{user.prenom} {user.nom}'
    db.session.delete(user)
    db.session.commit()
    flash(f'Utilisateur {nom} supprimé.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@editeur_required
def user_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    nouveau_mdp = request.form.get('nouveau_mdp', '').strip()
    if len(nouveau_mdp) < 6:
        flash('Le mot de passe temporaire doit contenir au moins 6 caractères.', 'danger')
        return redirect(url_for('admin.users'))
    user.set_password(nouveau_mdp)
    db.session.commit()
    flash(f'Mot de passe de {user.prenom} {user.nom} réinitialisé. Communiquez-lui le nouveau mot de passe.', 'success')
    return redirect(url_for('admin.users'))


# ─── Directions ─────────────────────────────────────────────────────────────

@admin_bp.route('/directions')
@admin_required
def directions():
    directions = Direction.query.order_by(Direction.code).all()
    return render_template('admin/directions.html', directions=directions)


@admin_bp.route('/directions/add', methods=['POST'])
@editeur_required
def direction_add():
    code = request.form.get('code', '').strip().upper()
    nom = request.form.get('nom', '').strip()
    if not code or not nom:
        flash('Code et nom obligatoires.', 'danger')
        return redirect(url_for('admin.directions'))
    if Direction.query.filter_by(code=code).first():
        flash(f"Le code « {code} » existe déjà.", 'danger')
        return redirect(url_for('admin.directions'))
    db.session.add(Direction(code=code, nom=nom))
    db.session.commit()
    flash(f'Direction {code} créée.', 'success')
    return redirect(url_for('admin.directions'))


@admin_bp.route('/directions/<int:dir_id>/edit', methods=['POST'])
@editeur_required
def direction_edit(dir_id):
    d = Direction.query.get_or_404(dir_id)
    code = request.form.get('code', '').strip().upper()
    nom = request.form.get('nom', '').strip()
    if not code or not nom:
        flash('Code et nom sont obligatoires.', 'danger')
        return redirect(url_for('admin.directions'))
    d.code = code
    d.nom = nom
    db.session.commit()
    flash('Direction mise à jour.', 'success')
    return redirect(url_for('admin.directions'))


@admin_bp.route('/directions/<int:dir_id>/delete', methods=['POST'])
@editeur_required
def direction_delete(dir_id):
    d = Direction.query.get_or_404(dir_id)
    if d.services:
        flash('Impossible : des services sont rattachés à cette direction.', 'danger')
        return redirect(url_for('admin.directions'))
    db.session.delete(d)
    db.session.commit()
    flash('Direction supprimée.', 'success')
    return redirect(url_for('admin.directions'))


# ─── Services ────────────────────────────────────────────────────────────────

@admin_bp.route('/services')
@admin_required
def services():
    services = Service.query.order_by(Service.code).all()
    directions = Direction.query.order_by(Direction.nom).all()
    return render_template('admin/services.html', services=services, directions=directions)


@admin_bp.route('/services/add', methods=['POST'])
@editeur_required
def service_add():
    code = request.form.get('code', '').strip().upper()
    nom = request.form.get('nom', '').strip()
    direction_id = request.form.get('direction_id')
    if not all([code, nom, direction_id]):
        flash('Tous les champs sont obligatoires.', 'danger')
        return redirect(url_for('admin.services'))
    if Service.query.filter_by(code=code).first():
        flash(f"Le code « {code} » existe déjà.", 'danger')
        return redirect(url_for('admin.services'))
    db.session.add(Service(code=code, nom=nom, direction_id=int(direction_id)))
    db.session.commit()
    flash(f'Service {code} créé.', 'success')
    return redirect(url_for('admin.services'))


@admin_bp.route('/services/<int:svc_id>/edit', methods=['POST'])
@editeur_required
def service_edit(svc_id):
    s = Service.query.get_or_404(svc_id)
    code = request.form.get('code', '').strip().upper()
    nom = request.form.get('nom', '').strip()
    if not code or not nom:
        flash('Code et nom sont obligatoires.', 'danger')
        return redirect(url_for('admin.services'))
    try:
        direction_id = int(request.form.get('direction_id', 0))
    except (ValueError, TypeError):
        flash('Direction invalide.', 'danger')
        return redirect(url_for('admin.services'))
    s.code = code
    s.nom = nom
    s.direction_id = direction_id
    db.session.commit()
    flash('Service mis à jour.', 'success')
    return redirect(url_for('admin.services'))


@admin_bp.route('/services/<int:svc_id>/delete', methods=['POST'])
@editeur_required
def service_delete(svc_id):
    s = Service.query.get_or_404(svc_id)
    db.session.delete(s)
    db.session.commit()
    flash('Service supprimé.', 'success')
    return redirect(url_for('admin.services'))


# ─── Années ──────────────────────────────────────────────────────────────────

@admin_bp.route('/annees')
@admin_required
def annees():
    annees = Annee.query.order_by(Annee.annee.desc()).all()
    return render_template('admin/annees.html', annees=annees)


@admin_bp.route('/annees/add', methods=['POST'])
@editeur_required
def annee_add():
    val = request.form.get('annee')
    if not val:
        flash('Année obligatoire.', 'danger')
        return redirect(url_for('admin.annees'))
    val = int(val)
    if Annee.query.filter_by(annee=val).first():
        flash(f"L'année {val} existe déjà.", 'danger')
        return redirect(url_for('admin.annees'))
    db.session.add(Annee(annee=val, actif=False))
    db.session.commit()
    flash(f'Année {val} créée.', 'success')
    return redirect(url_for('admin.annees'))


@admin_bp.route('/annees/<int:ann_id>/activate', methods=['POST'])
@editeur_required
def annee_activate(ann_id):
    Annee.query.update({'actif': False})
    a = Annee.query.get_or_404(ann_id)
    a.actif = True
    db.session.commit()
    # Mettre à jour la session pour que le badge en haut change immédiatement
    session['annee_id'] = a.id
    session['annee'] = a.annee
    flash(f'Année {a.annee} activée.', 'success')
    return redirect(url_for('admin.annees'))


@admin_bp.route('/annees/<int:ann_id>/deactivate', methods=['POST'])
@editeur_required
def annee_deactivate(ann_id):
    a = Annee.query.get_or_404(ann_id)
    a.actif = False
    db.session.commit()
    session.pop('annee_id', None)
    session.pop('annee', None)
    flash(f'Année {a.annee} désactivée.', 'warning')
    return redirect(url_for('admin.annees'))


@admin_bp.route('/annees/<int:ann_id>/delete', methods=['POST'])
@editeur_required
def annee_delete(ann_id):
    a = Annee.query.get_or_404(ann_id)
    if a.actif:
        flash('Impossible de supprimer une année active. Activez une autre année d\'abord.', 'danger')
        return redirect(url_for('admin.annees'))
    if a.programmes:
        flash(f'Impossible : le PTA {a.annee} contient des données. Supprimez d\'abord le contenu.', 'danger')
        return redirect(url_for('admin.annees'))
    db.session.delete(a)
    db.session.commit()
    flash(f'Année {a.annee} supprimée.', 'success')
    return redirect(url_for('admin.annees'))


# ─── Structures externes ────────────────────────────────────────────────────

@admin_bp.route('/structures-externes')
@admin_required
def structures_externes():
    items = StructureExterne.query.order_by(StructureExterne.nom).all()
    return render_template('admin/structures_externes.html', items=items)


@admin_bp.route('/structures-externes/add', methods=['POST'])
@editeur_required
def struct_ext_add():
    nom = request.form.get('nom', '').strip()
    if not nom:
        flash('Le nom est obligatoire.', 'danger')
        return redirect(url_for('admin.structures_externes'))
    se = StructureExterne(
        nom=nom,
        type_org=request.form.get('type_org', '').strip() or None,
        description=request.form.get('description', '').strip() or None,
    )
    db.session.add(se)
    db.session.commit()
    flash(f'Structure externe « {nom} » ajoutée.', 'success')
    return redirect(url_for('admin.structures_externes'))


@admin_bp.route('/structures-externes/<int:se_id>/edit', methods=['POST'])
@editeur_required
def struct_ext_edit(se_id):
    se = StructureExterne.query.get_or_404(se_id)
    nom = request.form.get('nom', '').strip()
    if not nom:
        flash('Le nom est obligatoire.', 'danger')
        return redirect(url_for('admin.structures_externes'))
    se.nom = nom
    se.type_org = request.form.get('type_org', '').strip() or None
    se.description = request.form.get('description', '').strip() or None
    db.session.commit()
    flash(f'Structure externe « {nom} » mise à jour.', 'success')
    return redirect(url_for('admin.structures_externes'))


@admin_bp.route('/structures-externes/<int:se_id>/delete', methods=['POST'])
@editeur_required
def struct_ext_delete(se_id):
    se = StructureExterne.query.get_or_404(se_id)
    nom = se.nom
    db.session.delete(se)
    db.session.commit()
    flash(f'Structure externe « {nom} » supprimée.', 'success')
    return redirect(url_for('admin.structures_externes'))


# ─── Sauvegardes PTA ─────────────────────────────────────────────────────────

@admin_bp.route('/backups')
@admin_required
def backups():
    sauvegardes = PTABackup.query.order_by(PTABackup.created_at.desc()).all()
    return render_template('admin/backups.html', sauvegardes=sauvegardes)


@admin_bp.route('/backups/<int:backup_id>/delete', methods=['POST'])
@editeur_required
def backup_delete(backup_id):
    b = PTABackup.query.get_or_404(backup_id)
    db.session.delete(b)
    db.session.commit()
    flash('Sauvegarde supprimée définitivement.', 'success')
    return redirect(url_for('admin.backups'))


@admin_bp.route('/backups/<int:backup_id>/restore', methods=['POST'])
@editeur_required
def backup_restore(backup_id):
    b = PTABackup.query.get_or_404(backup_id)
    annee = Annee.query.get(b.annee_id) if b.annee_id else None
    if not annee:
        flash("L'année PTA de cette sauvegarde n'existe plus. Créez-la d'abord dans Années.", 'danger')
        return redirect(url_for('admin.backups'))

    existing = Programme.query.filter_by(annee_id=annee.id).count()
    if existing > 0:
        flash(
            f"Le PTA {annee.annee} n'est pas vide ({existing} programme(s) existant(s)). "
            f"Réinitialisez d'abord le PTA depuis la page PTA Global avant de restaurer.",
            'danger'
        )
        return redirect(url_for('admin.backups'))

    password = request.form.get('password', '').strip()
    if not current_user.check_password(password):
        flash('Mot de passe incorrect.', 'danger')
        return redirect(url_for('admin.backups'))

    data = json.loads(b.contenu)

    def get_svcs(ids): return [s for s in (Service.query.get(i) for i in ids) if s]
    def get_dirs(ids): return [d for d in (Direction.query.get(i) for i in ids) if d]
    def get_ses(ids):  return [se for se in (StructureExterne.query.get(i) for i in ids) if se]

    nb_acts = 0
    nb_taches = 0

    for pd in data['programmes']:
        prog = Programme(
            annee_id=annee.id, numero=pd['numero'], nom=pd['nom'],
            description=pd.get('description'),
            objectif_specifique=pd.get('objectif_specifique'),
            poids=pd.get('poids', 0),
        )
        db.session.add(prog)
        db.session.flush()

        for pjd in pd['projets']:
            pj = Projet(
                programme_id=prog.id, numero=pjd['numero'], nom=pjd['nom'],
                description=pjd.get('description'), poids=pjd.get('poids', 0),
            )
            db.session.add(pj)
            db.session.flush()

            for ad in pjd['activites']:
                a = Activite(
                    projet_id=pj.id, numero=ad['numero'], nom=ad['nom'],
                    description=ad.get('description'),
                    direction_responsable_id=ad.get('direction_responsable_id'),
                    imputation_budgetaire=ad.get('imputation_budgetaire'),
                    ressources_propres=ad.get('ressources_propres', 0),
                    fadec_affecte=ad.get('fadec_affecte', 0),
                    fadec_non_affecte=ad.get('fadec_non_affecte', 0),
                    autres_partenaires=ad.get('autres_partenaires', 0),
                    autres_fonds=ad.get('autres_fonds', 0),
                    details_financement=ad.get('details_financement'),
                    acteurs_externes=ad.get('acteurs_externes'),
                    periode_debut=ad.get('periode_debut'),
                    periode_fin=ad.get('periode_fin'),
                    mode_execution=ad.get('mode_execution', 'Direct'),
                    poids=ad.get('poids', 0),
                )
                a.services_intervenants = get_svcs(ad.get('services_intervenants', []))
                a.directions_associees  = get_dirs(ad.get('directions_associees', []))
                a.structures_externes   = get_ses(ad.get('structures_externes', []))
                db.session.add(a)
                db.session.flush()
                nb_acts += 1

                for td in ad.get('taches', []):
                    t = Tache(
                        activite_id=a.id, numero=td['numero'],
                        ordre=td.get('ordre', 0), nom=td['nom'],
                        description=td.get('description'),
                        poids=td.get('poids', 0),
                        imputation_budgetaire=td.get('imputation_budgetaire'),
                        ressources_propres=td.get('ressources_propres', 0),
                        fadec_affecte=td.get('fadec_affecte', 0),
                        fadec_non_affecte=td.get('fadec_non_affecte', 0),
                        autres_partenaires=td.get('autres_partenaires', 0),
                        autres_fonds=td.get('autres_fonds', 0),
                        details_financement=td.get('details_financement'),
                        acteurs_externes=td.get('acteurs_externes'),
                        mode_execution=td.get('mode_execution', 'Direct'),
                        service_responsable_id=td.get('service_responsable_id'),
                        direction_responsable_id=td.get('direction_responsable_id'),
                    )
                    t.services_concernes   = get_svcs(td.get('services_concernes', []))
                    t.directions_associees = get_dirs(td.get('directions_associees', []))
                    t.structures_externes  = get_ses(td.get('structures_externes', []))
                    db.session.add(t)
                    nb_taches += 1

    db.session.commit()
    flash(
        f'PTA {annee.annee} restauré depuis la sauvegarde #{b.id} : '
        f'{len(data["programmes"])} programmes, {nb_acts} activités, {nb_taches} tâches.',
        'success'
    )
    return redirect(url_for('pta.global_pta'))