from functools import wraps
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
import json
from models import db, User, Direction, Service, Annee, StructureExterne, PTABackup, Programme, Projet, Activite, Tache
from admin import admin_bp
from utils import log_audit


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin_editeur':
            flash('Accès refusé. Réservé aux administrateurs éditeurs.', 'danger')
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


# ─── Sauvegarde manuelle ────────────────────────────────────────────────────

@admin_bp.route('/backup-now', methods=['POST'])
@editeur_required
def backup_now():
    """Déclenche une sauvegarde immédiate par email (admin_editeur uniquement)."""
    import importlib.util, os
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backup_pta.py')
    try:
        spec = importlib.util.spec_from_file_location('backup_pta', script)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run()
        log_audit('sauvegarde', 'Sauvegarde manuelle déclenchée depuis Administration')
        flash('Sauvegarde envoyée par email avec succès.', 'success')
    except FileNotFoundError:
        flash('Script de sauvegarde introuvable. Contactez l\'administrateur.', 'danger')
    except Exception as e:
        flash(f'Erreur lors de la sauvegarde : {e}', 'danger')
    return redirect(url_for('admin.index'))


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

    email_val = request.form.get('email', '').strip() or None

    user = User(
        nom=nom, prenom=prenom, login=login_val, role=role,
        direction_id=int(direction_id) if direction_id else None,
        service_id=int(service_id) if service_id else None,
        email=email_val,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    log_audit('user_cree', f"Compte créé : {prenom} {nom} ({role})")
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
        # Empêcher un admin de rétrograder son propre rôle (perte d'accès)
        if user.id == current_user.id and role != 'admin_editeur':
            flash('Vous ne pouvez pas modifier votre propre rôle d\'administrateur.', 'danger')
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
        user.email = request.form.get('email', '').strip() or None
        new_pw = request.form.get('password', '').strip()
        if new_pw:
            user.set_password(new_pw)
        db.session.commit()
        log_audit('user_modifie', f"Utilisateur modifié : {user.prenom} {user.nom} — rôle : {user.role}")
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
    action = 'user_active' if user.actif else 'user_desactive'
    log_audit(action, f"Compte {etat} : {user.prenom} {user.nom}")
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
    role = user.role
    db.session.delete(user)
    db.session.commit()
    log_audit('user_supprime', f"Compte supprimé : {nom} ({role})")
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
    log_audit('mdp_reinit', f"Mot de passe réinitialisé pour : {user.prenom} {user.nom}")
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
    if User.query.filter_by(direction_id=dir_id).first():
        flash('Impossible : des utilisateurs sont rattachés à cette direction.', 'danger')
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
    if User.query.filter_by(service_id=svc_id).first():
        flash('Impossible : des utilisateurs sont rattachés à ce service.', 'danger')
        return redirect(url_for('admin.services'))
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
    nouvelle = Annee(annee=val, actif=False)
    db.session.add(nouvelle)
    db.session.commit()
    log_audit('annee_cree', f"Année PTA créée : {val}")
    # Proposer immédiatement la copie du PTA de l'année source
    return redirect(url_for('admin.annee_confirm_copie', ann_id=nouvelle.id))


@admin_bp.route('/annees/<int:ann_id>/confirmer-copie')
@editeur_required
def annee_confirm_copie(ann_id):
    """Page de confirmation : copier ou non le PTA de l'année source vers la nouvelle année."""
    nouvelle = Annee.query.get_or_404(ann_id)
    # Source = année active, sinon la plus récente différente de la nouvelle
    source = Annee.query.filter_by(actif=True).first()
    if not source or source.id == ann_id:
        source = Annee.query.filter(Annee.id != ann_id)\
                             .order_by(Annee.annee.desc()).first()
    from models import Programme
    nb_prog_source = Programme.query.filter_by(
        annee_id=source.id).count() if source else 0
    return render_template('admin/annee_copie_confirm.html',
                           nouvelle=nouvelle,
                           source=source,
                           nb_prog_source=nb_prog_source)


@admin_bp.route('/annees/<int:ann_id>/copier-pta', methods=['POST'])
@editeur_required
def annee_copier_pta(ann_id):
    """Copie la structure complète du PTA (sans suivi) depuis l'année source."""
    nouvelle = Annee.query.get_or_404(ann_id)
    source_id = request.form.get('source_id', type=int)
    if not source_id:
        flash('Année source introuvable.', 'danger')
        return redirect(url_for('admin.annees'))

    source = Annee.query.get_or_404(source_id)
    from models import Programme, Projet, Activite, Tache

    # Vérifier que la nouvelle année est bien vide
    if Programme.query.filter_by(annee_id=ann_id).first():
        flash(f'Le PTA {nouvelle.annee} contient déjà des données. Copie annulée.', 'danger')
        return redirect(url_for('admin.annees'))

    nb_prog = nb_proj = nb_act = nb_tache = 0

    for prog_src in Programme.query.filter_by(annee_id=source_id)\
                                   .order_by(Programme.numero).all():
        prog_new = Programme(
            annee_id            = ann_id,
            numero              = prog_src.numero,
            nom                 = prog_src.nom,
            description         = prog_src.description,
            objectif_specifique = prog_src.objectif_specifique,
            poids               = prog_src.poids,
            observations        = prog_src.observations,
        )
        db.session.add(prog_new)
        db.session.flush()   # obtenir prog_new.id
        nb_prog += 1

        for proj_src in sorted(prog_src.projets, key=lambda p: p.numero):
            proj_new = Projet(
                programme_id = prog_new.id,
                numero       = proj_src.numero,
                nom          = proj_src.nom,
                description  = proj_src.description,
                poids        = proj_src.poids,
                observations = proj_src.observations,
            )
            db.session.add(proj_new)
            db.session.flush()
            nb_proj += 1

            for act_src in sorted(proj_src.activites, key=lambda a: a.numero):
                act_new = Activite(
                    projet_id               = proj_new.id,
                    numero                  = act_src.numero,
                    nom                     = act_src.nom,
                    description             = act_src.description,
                    direction_responsable_id= act_src.direction_responsable_id,
                    imputation_budgetaire   = act_src.imputation_budgetaire,
                    ressources_propres      = act_src.ressources_propres,
                    fadec_affecte           = act_src.fadec_affecte,
                    fadec_non_affecte       = act_src.fadec_non_affecte,
                    autres_partenaires      = act_src.autres_partenaires,
                    autres_fonds            = act_src.autres_fonds,
                    details_financement     = act_src.details_financement,
                    acteurs_externes        = act_src.acteurs_externes,
                    periode_debut           = act_src.periode_debut,
                    periode_fin             = act_src.periode_fin,
                    mode_execution          = act_src.mode_execution,
                    type_activite           = act_src.type_activite,
                    poids                   = act_src.poids,
                    observations            = act_src.observations,
                )
                # Many-to-many : services, directions et structures externes intervenants
                act_new.services_intervenants = list(act_src.services_intervenants)
                act_new.directions_associees  = list(act_src.directions_associees)
                act_new.structures_externes   = list(act_src.structures_externes)
                db.session.add(act_new)
                db.session.flush()
                nb_act += 1

                for tache_src in sorted(act_src.taches,
                                        key=lambda t: (t.ordre, t.numero)):
                    tache_new = Tache(
                        activite_id             = act_new.id,
                        numero                  = tache_src.numero,
                        ordre                   = tache_src.ordre,
                        nom                     = tache_src.nom,
                        description             = tache_src.description,
                        poids                   = tache_src.poids,
                        service_responsable_id  = tache_src.service_responsable_id,
                        direction_responsable_id= tache_src.direction_responsable_id,
                        imputation_budgetaire   = tache_src.imputation_budgetaire,
                        ressources_propres      = tache_src.ressources_propres,
                        fadec_affecte           = tache_src.fadec_affecte,
                        fadec_non_affecte       = tache_src.fadec_non_affecte,
                        autres_partenaires      = tache_src.autres_partenaires,
                        autres_fonds            = tache_src.autres_fonds,
                        details_financement     = tache_src.details_financement,
                        acteurs_externes        = tache_src.acteurs_externes,
                        mode_execution          = tache_src.mode_execution,
                        periode_debut           = tache_src.periode_debut,
                        periode_fin             = tache_src.periode_fin,
                        observations            = tache_src.observations,
                    )
                    # Many-to-many : services, directions et structures externes concernés
                    tache_new.services_concernes   = list(tache_src.services_concernes)
                    tache_new.directions_associees = list(tache_src.directions_associees)
                    tache_new.structures_externes  = list(tache_src.structures_externes)
                    db.session.add(tache_new)
                    nb_tache += 1

    # Copier aussi l'objectif général de l'année source
    nouvelle.objectif_general = source.objectif_general
    db.session.commit()
    log_audit('annee_pta_copie', f"PTA {source.annee} → {nouvelle.annee} : {nb_prog} prog., {nb_proj} proj., {nb_act} act., {nb_tache} tâches")

    flash(
        f'Structure du PTA {source.annee} copiée vers {nouvelle.annee} avec succès : '
        f'{nb_prog} programme(s), {nb_proj} projet(s), '
        f'{nb_act} activité(s), {nb_tache} tâche(s). '
        "Aucune donnée de suivi n'a été copiée.",
        'success'
    )
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
    log_audit('annee_activee', f"Année PTA activée : {a.annee}")
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
    log_audit('annee_desactivee', f"Année PTA désactivée : {a.annee}")
    flash(f'Année {a.annee} désactivée.', 'warning')
    return redirect(url_for('admin.annees'))


@admin_bp.route('/annees/<int:ann_id>/purge-suivi', methods=['POST'])
@editeur_required
def annee_purge_suivi(ann_id):
    """Vide uniquement les données de suivi (suivi_taches) pour une année."""
    a = Annee.query.get_or_404(ann_id)
    from models import SuiviTache
    nb = SuiviTache.query.filter_by(annee_id=ann_id).delete()
    db.session.commit()
    log_audit('annee_purge_suivi', f"Suivi PTA {a.annee} purgé : {nb} enregistrement(s) supprimé(s)")
    flash(f'Suivi de {a.annee} vidé : {nb} enregistrement(s) supprimé(s). '
          f'La structure du PTA est conservée.', 'success')
    return redirect(url_for('admin.annees'))


@admin_bp.route('/annees/<int:ann_id>/purge-pta', methods=['POST'])
@editeur_required
def annee_purge_pta(ann_id):
    """Vide TOUT le PTA d'une année (suivi + programmes/projets/activités/tâches)."""
    a = Annee.query.get_or_404(ann_id)
    from models import SuiviTache, Programme
    # 1. Suivi d'abord (FK vers taches)
    nb_suivi = SuiviTache.query.filter_by(annee_id=ann_id).delete()
    db.session.flush()
    # 2. Programmes en cascade → projets → activités → tâches
    programmes = Programme.query.filter_by(annee_id=ann_id).all()
    nb_prog = len(programmes)
    for prog in programmes:
        db.session.delete(prog)
    db.session.commit()
    log_audit('annee_purge_pta', f"PTA {a.annee} entièrement purgé : {nb_suivi} suivi(s), {nb_prog} programme(s)")
    flash(f'PTA {a.annee} entièrement vidé : {nb_suivi} suivi(s) et '
          f'{nb_prog} programme(s) supprimé(s) (avec projets, activités, tâches). '
          f'L\'année {a.annee} existe toujours et peut être réimportée.', 'success')
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


# ─── Journal d'audit ────────────────────────────────────────────────────────

@admin_bp.route('/journal')
@editeur_required
def journal():
    from models import AuditLog
    import datetime as _dt

    page          = request.args.get('page', 1, type=int)
    filtre_action = request.args.get('action', '').strip()
    filtre_user   = request.args.get('user', '').strip()
    filtre_depuis = request.args.get('depuis', '').strip()

    q = AuditLog.query.order_by(AuditLog.horodatage.desc())

    if filtre_action:
        q = q.filter(AuditLog.action == filtre_action)
    if filtre_user:
        q = q.filter(
            db.or_(
                AuditLog.user_nom.ilike(f'%{filtre_user}%'),
                AuditLog.user_role.ilike(f'%{filtre_user}%'),
            )
        )
    if filtre_depuis:
        try:
            depuis = _dt.datetime.strptime(filtre_depuis, '%Y-%m-%d')
            q = q.filter(AuditLog.horodatage >= depuis)
        except ValueError:
            filtre_depuis = ''

    pagination = q.paginate(page=page, per_page=50, error_out=False)
    entries    = pagination.items

    # Liste de toutes les actions distinctes (pour le filtre)
    actions_dispo = [r[0] for r in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]

    return render_template('admin/journal.html',
        entries=entries,
        pagination=pagination,
        actions_dispo=actions_dispo,
        filtre_action=filtre_action,
        filtre_user=filtre_user,
        filtre_depuis=filtre_depuis,
    )


@admin_bp.route('/journal/purge', methods=['POST'])
@editeur_required
def journal_purge():
    """Purge tout ou partie du journal d'audit."""
    from models import AuditLog
    import datetime as _dt

    mode = request.form.get('mode', 'tout')   # 'tout' ou 'avant'
    nb   = 0

    if mode == 'avant':
        avant_str = request.form.get('avant_date', '').strip()
        try:
            avant = _dt.datetime.strptime(avant_str, '%Y-%m-%d')
            nb = AuditLog.query.filter(AuditLog.horodatage < avant).delete()
        except ValueError:
            flash('Date invalide. Aucune entrée supprimée.', 'danger')
            return redirect(url_for('admin.journal'))
    else:
        nb = AuditLog.query.delete()

    db.session.commit()
    log_audit('journal_purge', f"Journal d'audit purgé : {nb} entrée(s) supprimée(s) (mode : {mode})")
    flash(f'Journal purgé : {nb} entrée(s) supprimée(s).', 'success')
    return redirect(url_for('admin.journal'))


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


# ─── Emails PTA (rappel saisie + bilan) ──────────────────────────────────────

# Adresses toujours mises en copie (CC)
# Décommenter les deux lignes suivantes après validation en test :
# 'honzounnonluc@gmail.com'
# 'luc.honzounnon@mairie.bj'
_COPIES_FIXES = ['jupiter.gboyou@mairie.bj']


def _lire_cfg_smtp():
    """Lit GMAIL_USER / GMAIL_APP_PASSWORD depuis ~/.pta_backup_config."""
    import os
    cfg = {}
    with open(os.path.expanduser('~/.pta_backup_config'), encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip()
            if '=' in ligne and not ligne.startswith('#'):
                cle, val = ligne.split('=', 1)
                cfg[cle.strip()] = val.strip()
    for cle in ('GMAIL_USER', 'GMAIL_APP_PASSWORD'):
        if cle not in cfg:
            raise ValueError(f"Clé manquante dans config : {cle}")
    return cfg


def _get_destinataires():
    """Emails des utilisateurs actifs ayant une adresse renseignée."""
    return [
        u.email.strip()
        for u in User.query.filter(User.actif == True).all()
        if u.email and u.email.strip()
    ]


def _envoyer_smtp(cfg, msg, destinataires):
    """Envoie via Gmail SMTP — BCC : destinataires, CC : copies fixes."""
    import smtplib
    tous = [cfg['GMAIL_USER']] + destinataires + _COPIES_FIXES
    with smtplib.SMTP('smtp.gmail.com', 587) as srv:
        srv.ehlo()
        srv.starttls()
        srv.login(cfg['GMAIL_USER'], cfg['GMAIL_APP_PASSWORD'])
        srv.sendmail(cfg['GMAIL_USER'], tous, msg.as_string())


@admin_bp.route('/rappel-saisie', methods=['POST'])
@editeur_required
def rappel_saisie():
    """Envoie un rappel aux utilisateurs pour qu'ils renseignent leurs données PTA."""
    import datetime
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from utils import get_annee

    annee       = get_annee()
    annee_label = annee.annee if annee else datetime.date.today().year
    date_str    = datetime.date.today().strftime('%d/%m/%Y')
    plateforme  = request.host_url.rstrip('/')

    destinataires = _get_destinataires()
    if not destinataires:
        flash("Aucun utilisateur actif n'a d'adresse email renseignée.", 'warning')
        return redirect(url_for('admin.index'))

    try:
        cfg = _lire_cfg_smtp()
    except FileNotFoundError:
        flash("Fichier de configuration email introuvable (~/.pta_backup_config).", 'danger')
        return redirect(url_for('admin.index'))
    except ValueError as e:
        flash(f"Configuration email incomplète : {e}", 'danger')
        return redirect(url_for('admin.index'))

    sujet = f"[PTA Mairie {annee_label}] Rappel — Renseigner les données d'exécution"

    html_body = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.08);">
  <tr><td style="background:#1e3a5f;padding:24px 32px;">
    <p style="margin:0;color:#fcd116;font-size:11px;letter-spacing:1px;text-transform:uppercase;">
      Mairie d'Adja-Ouèrè · Système PTA {annee_label}</p>
    <h1 style="margin:8px 0 0;color:#fff;font-size:20px;line-height:1.3;">
      Rappel — Saisie des données d'exécution</h1>
    <p style="margin:4px 0 0;color:rgba(255,255,255,.7);font-size:13px;">{date_str}</p>
  </td></tr>
  <tr><td style="padding:28px 32px;">
    <p style="margin:0 0 16px;color:#374151;">Madame, Monsieur,</p>
    <p style="margin:0 0 16px;color:#374151;line-height:1.7;">
      Dans le cadre de l'évaluation du Plan de Travail Annuel (PTA) {annee_label}
      de la Mairie d'Adja-Ouèrè, vous êtes prié(e) de <strong>vous connecter sur la
      plateforme de gestion du PTA</strong> et de renseigner le niveau réel d'avancement
      de votre PTA avant la fin du trimestre en cours.
    </p>
    <div style="text-align:center;margin:24px 0;">
      <a href="{plateforme}" target="_blank"
         style="background:#1e3a5f;color:#fcd116;text-decoration:none;
                padding:12px 28px;border-radius:8px;font-weight:700;font-size:15px;
                display:inline-block;">
        Se connecter à la plateforme →
      </a>
    </div>
    <p style="margin:0 0 8px;color:#374151;line-height:1.7;">
      Une fois connecté(e), rendez-vous dans l'onglet <strong>« Faire suivi »</strong>
      pour mettre à jour vos données d'exécution.
    </p>
    <p style="margin:16px 0 0;color:#6b7280;font-size:13px;line-height:1.6;">
      Pour toute difficulté de connexion ou de saisie, contactez l'administrateur du système.
    </p>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
    <p style="margin:0;color:#9ca3af;font-size:11px;line-height:1.7;">
      Ce message a été envoyé depuis le Système PTA de la Mairie d'Adja-Ouèrè.<br>
      Émis par : <strong>Jupiter GBOYOU</strong> ·
      <a href="mailto:jupiter.gboyou@mairie.bj" style="color:#1e3a5f;">jupiter.gboyou@mairie.bj</a>
    </p>
    <p style="margin:6px 0 0;color:#9ca3af;font-size:11px;">
      &#x1F1E7;&#x1F1EF; République du Bénin &nbsp;·&nbsp; Mairie d'Adja-Ouèrè
    </p>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""

    texte_brut = (
        f"Rappel — Saisie des données d'exécution PTA {annee_label}\n"
        f"Date : {date_str}\n\n"
        f"Madame, Monsieur,\n\n"
        f"Dans le cadre de l'évaluation du PTA {annee_label}, vous êtes prié(e) de vous "
        f"connecter sur la plateforme ({plateforme}) et de renseigner le niveau réel "
        f"d'avancement de votre PTA avant la fin du trimestre.\n\n"
        f"Onglet : Faire suivi\n\n"
        f"---\nMairie d'Adja-Ouèrè · Système PTA"
    )

    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart('alternative')
    msg['From']     = f"Mairie d'Adja-Ouèrè PTA <{cfg['GMAIL_USER']}>"
    msg['To']       = cfg['GMAIL_USER']
    msg['Cc']       = ', '.join(destinataires)    # users visibles (voient qui a reçu)
    msg['Bcc']      = ', '.join(_COPIES_FIXES)    # copie silencieuse (voit la liste CC)
    msg['Subject']  = sujet
    msg['Reply-To'] = 'jupiter.gboyou@mairie.bj'
    msg.attach(MIMEText(texte_brut, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body,  'html',  'utf-8'))

    try:
        _envoyer_smtp(cfg, msg, destinataires)
    except Exception as e:
        flash(f"Erreur lors de l'envoi : {e}", 'danger')
        return redirect(url_for('admin.index'))

    log_audit('rappel_saisie',
              f"Rappel de saisie PTA {annee_label} envoyé à {len(destinataires)} destinataire(s)")
    flash(f"Rappel envoyé à {len(destinataires)} destinataire(s) + {len(_COPIES_FIXES)} copie(s).", 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/bilan-pta', methods=['POST'])
@editeur_required
def bilan_pta():
    """Envoie le bilan global PTA — taux et statuts identiques à l'interface Suivi."""
    import datetime
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from utils import get_annee

    annee       = get_annee()
    annee_label = annee.annee if annee else datetime.date.today().year
    date_str    = datetime.date.today().strftime('%d/%m/%Y')

    destinataires = _get_destinataires()
    if not destinataires:
        flash("Aucun utilisateur actif n'a d'adresse email renseignée.", 'warning')
        return redirect(url_for('admin.index'))

    try:
        cfg = _lire_cfg_smtp()
    except FileNotFoundError:
        flash("Fichier de configuration email introuvable (~/.pta_backup_config).", 'danger')
        return redirect(url_for('admin.index'))
    except ValueError as e:
        flash(f"Configuration email incomplète : {e}", 'danger')
        return redirect(url_for('admin.index'))

    if not annee:
        flash("Aucune année PTA active.", 'warning')
        return redirect(url_for('admin.index'))

    # ── Données — mêmes fonctions que le tableau de bord admin ──────────────────
    from suivi.routes import _compute_pta_global
    from dashboard.routes import (_compute_synthese_admin, _compute_dashboard_stats,
                                   _cibles_global)

    data     = _compute_pta_global(annee)
    cibles   = _cibles_global(annee)
    stats    = _compute_dashboard_stats(annee, data, cibles, with_nature=True)
    synthese = _compute_synthese_admin(annee)   # [{direction, taux, nb_taches, services:[...]}]

    # Global (trim=0)
    taux_global = round(stats['suivi'][0]['taux'], 1)
    glob_a      = stats['suivi'][0]['activites']   # execute / en_cours / non_execute / total
    total_glob  = glob_a['total']

    # Nature (trim=0)
    def _nat_a(key):
        d = stats.get(key) or {}
        return d.get(0, {}).get('activites',
                                {'execute': 0, 'en_cours': 0, 'non_execute': 0, 'total': 0})
    def _nat_t(key):
        d = stats.get(key) or {}
        return round(d.get(0, {}).get('taux', 0.0), 1)

    inv_a    = _nat_a('suivi_invest');  taux_inv = _nat_t('suivi_invest')
    fct_a    = _nat_a('suivi_fonct');   taux_fct = _nat_t('suivi_fonct')

    # ── HTML ──────────────────────────────────────────────────────────────────
    VERT   = '#16a34a'
    ORANGE = '#f59e0b'
    ROUGE  = '#dc2626'

    def _coul(t): return VERT if t >= 75 else (ORANGE if t >= 30 else ROUGE)

    def _cel_taux(t):
        return (f"<td style='padding:8px 10px;text-align:center;border-bottom:1px solid #e5e7eb;"
                f"font-weight:700;font-size:15px;color:{_coul(t)};'>{t}%</td>")

    def _lig_nat(acts, taux):
        tot = acts['total']
        return (
            f"<td style='padding:8px 10px;text-align:center;border-bottom:1px solid #e5e7eb;'>"
            f"<b style='color:{VERT};'>{acts['execute']}</b></td>"
            f"<td style='padding:8px 10px;text-align:center;border-bottom:1px solid #e5e7eb;'>"
            f"<b style='color:{ORANGE};'>{acts['en_cours']}</b></td>"
            f"<td style='padding:8px 10px;text-align:center;border-bottom:1px solid #e5e7eb;'>"
            f"<b style='color:{ROUGE};'>{acts['non_execute']}</b></td>"
            f"<td style='padding:8px 10px;text-align:center;border-bottom:1px solid #e5e7eb;"
            f"font-weight:700;'>{tot}</td>"
            + _cel_taux(taux)
        )

    TH  = "style='padding:10px;text-align:left;'"
    THC = "style='padding:10px;text-align:center;'"
    TS  = ("width='100%' cellpadding='0' cellspacing='0' "
           "style='border-collapse:collapse;font-size:13px;margin:10px 0 18px;'")
    VIDE3 = "<tr><td colspan='3' style='padding:10px;color:#9ca3af;text-align:center;'>—</td></tr>"
    VIDE5 = "<tr><td colspan='5' style='padding:10px;color:#9ca3af;text-align:center;'>—</td></tr>"

    # Table directions — Code | Direction | Taux
    # Seules les directions ayant au moins une tâche dans le PTA (nb_taches > 0)
    lig_d = ''.join(
        f"<tr>"
        f"<td style='padding:8px 10px;border-bottom:1px solid #e5e7eb;"
        f"font-weight:700;color:#1e3a5f;'>{item['direction'].code}</td>"
        f"<td style='padding:8px 10px;border-bottom:1px solid #e5e7eb;'>"
        f"{item['direction'].nom}</td>"
        + _cel_taux(round(item['taux'], 1)) + "</tr>"
        for item in synthese if item['nb_taches'] > 0
    ) or VIDE3
    entete_d = (f"<tr style='background:#1e3a5f;color:#fff;'>"
                f"<th {TH}>Code</th><th {TH}>Direction</th>"
                f"<th {THC}>Taux d'exécution</th></tr>")
    bloc_dir = f"<table {TS}>{entete_d}<tbody>{lig_d}</tbody></table>"

    # Table services — Code | Service (Dir) | Taux
    # Seuls les services ayant au moins une tâche dans le PTA (nb_taches > 0)
    lig_s = ''.join(
        f"<tr>"
        f"<td style='padding:8px 10px;border-bottom:1px solid #e5e7eb;"
        f"font-weight:700;color:#0f6f3a;'>{sv['service'].code}</td>"
        f"<td style='padding:8px 10px;border-bottom:1px solid #e5e7eb;'>"
        f"{sv['service'].nom} "
        f"<span style='color:#9ca3af;font-size:11px;'>({item['direction'].code})</span></td>"
        + _cel_taux(round(sv['taux'], 1)) + "</tr>"
        for item in synthese
        for sv in item['services'] if sv['nb_taches'] > 0
    ) or VIDE3
    entete_s = (f"<tr style='background:#0f6f3a;color:#fff;'>"
                f"<th {TH}>Code</th><th {TH}>Service (Direction)</th>"
                f"<th {THC}>Taux d'exécution</th></tr>")
    bloc_svc = f"<table {TS}>{entete_s}<tbody>{lig_s}</tbody></table>"

    # Table nature — ✅ En cours ⏸ Total Taux
    entete_nat = (
        f"<tr style='background:#1e3a5f;color:#fff;'>"
        f"<th {TH}>Nature</th>"
        f"<th {THC}>✅ Exéc.</th><th {THC}>🔄 En cours</th>"
        f"<th {THC}>⏸ Non exéc.</th><th {THC}>Total</th>"
        f"<th {THC}>Taux</th></tr>"
    )
    lig_n = (
        f"<tr><td style='padding:8px 10px;border-bottom:1px solid #e5e7eb;"
        f"font-weight:700;'>Investissement</td>" + _lig_nat(inv_a, taux_inv) + "</tr>"
        f"<tr><td style='padding:8px 10px;border-bottom:1px solid #e5e7eb;"
        f"font-weight:700;'>Fonctionnement</td>" + _lig_nat(fct_a, taux_fct) + "</tr>"
    )
    bloc_nat = f"<table {TS}>{entete_nat}<tbody>{lig_n}</tbody></table>"

    # Synthèse globale
    pct_e = round(glob_a['execute']     / total_glob * 100, 1) if total_glob else 0
    pct_c = round(glob_a['en_cours']    / total_glob * 100, 1) if total_glob else 0
    pct_n = round(glob_a['non_execute'] / total_glob * 100, 1) if total_glob else 0
    bloc_glob = (
        f"<table width='100%' cellpadding='0' cellspacing='0' "
        f"style='border-collapse:collapse;font-size:14px;'>"
        f"<tr style='background:#f1f5f9;'>"
        f"<td style='padding:12px;font-weight:700;color:#1e3a5f;'>"
        f"TOTAL — {total_glob} activité(s)</td>"
        f"<td style='padding:12px;text-align:center;'>"
        f"<span style='color:{VERT};font-weight:700;font-size:18px;'>{glob_a['execute']}</span><br>"
        f"<span style='font-size:11px;color:#6b7280;'>exécutée(s) ({pct_e}%)</span></td>"
        f"<td style='padding:12px;text-align:center;'>"
        f"<span style='color:{ORANGE};font-weight:700;font-size:18px;'>{glob_a['en_cours']}</span><br>"
        f"<span style='font-size:11px;color:#6b7280;'>en cours ({pct_c}%)</span></td>"
        f"<td style='padding:12px;text-align:center;'>"
        f"<span style='color:{ROUGE};font-weight:700;font-size:18px;'>{glob_a['non_execute']}</span><br>"
        f"<span style='font-size:11px;color:#6b7280;'>non exéc. ({pct_n}%)</span></td>"
        f"<td style='padding:12px;text-align:center;'>"
        f"<span style='color:{_coul(taux_global)};font-weight:700;font-size:22px;'>"
        f"{taux_global}%</span><br>"
        f"<span style='font-size:11px;color:#6b7280;'>taux global</span></td>"
        f"</tr></table>"
    )

    def sec(t): return f"<h2 style='margin:20px 0 6px;color:#1e3a5f;font-size:15px;border-bottom:2px solid #1e3a5f;padding-bottom:5px;'>{t}</h2>"

    html_body = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
<tr><td align="center">
<table width="720" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.08);">
  <tr><td style="background:#1e3a5f;padding:24px 32px;">
    <p style="margin:0;color:#fcd116;font-size:11px;letter-spacing:1px;text-transform:uppercase;">
      Mairie d'Adja-Ouèrè · Système PTA {annee_label}</p>
    <h1 style="margin:8px 0 0;color:#fff;font-size:20px;line-height:1.3;">Bilan global du PTA</h1>
    <p style="margin:4px 0 0;color:rgba(255,255,255,.7);font-size:13px;">État au {date_str}</p>
  </td></tr>
  <tr><td style="padding:28px 32px;">
    <p style="margin:0 0 20px;color:#374151;line-height:1.6;">
      Bonjour,<br>Bilan d'avancement du PTA {annee_label} à la date du <strong>{date_str}</strong>.
    </p>
    {sec('📊 Par direction — activités')}
    {bloc_dir}
    {sec('🏢 Par service — activités')}
    {bloc_svc}
    {sec('🏷️ Par nature — activités')}
    {bloc_nat}
    {sec('🌐 Synthèse globale')}
    {bloc_glob}
    <p style="margin:20px 0 0;color:#6b7280;font-size:12px;">
      Pour le détail complet, connectez-vous au système PTA.
    </p>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
    <p style="margin:0;color:#9ca3af;font-size:11px;line-height:1.7;">
      Message envoyé automatiquement depuis le Système PTA de la Mairie d'Adja-Ouèrè.<br>
      Émis par : <strong>Jupiter GBOYOU</strong> ·
      <a href="mailto:jupiter.gboyou@mairie.bj" style="color:#1e3a5f;">jupiter.gboyou@mairie.bj</a>
    </p>
    <p style="margin:6px 0 0;color:#9ca3af;font-size:11px;">
      &#x1F1E7;&#x1F1EF; République du Bénin &nbsp;·&nbsp; Mairie d'Adja-Ouèrè
    </p>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""

    texte_brut = (
        f"Bilan global PTA {annee_label} — État au {date_str}\n\n"
        f"GLOBAL : {total_glob} activité(s) | {glob_a['execute']} exéc. | "
        f"{glob_a['en_cours']} en cours | {glob_a['non_execute']} non exéc. | Taux : {taux_global}%\n\n"
        "PAR DIRECTION :\n"
        + '\n'.join(
            f"  {item['direction'].code} — {item['direction'].nom} : Taux {round(item['taux'], 1)}%"
            for item in synthese if item['nb_taches'] > 0
        )
        + "\n\nPAR SERVICE :\n"
        + '\n'.join(
            f"  {sv['service'].code} ({item['direction'].code}) — "
            f"{sv['service'].nom} : Taux {round(sv['taux'], 1)}%"
            for item in synthese
            for sv in item['services'] if sv['nb_taches'] > 0
        )
        + f"\n\nPAR NATURE :\n"
        f"  Investissement : {inv_a['total']} act. | Taux {taux_inv}%\n"
        f"  Fonctionnement : {fct_a['total']} act. | Taux {taux_fct}%"
        + "\n\n---\nMairie d'Adja-Ouèrè · Système PTA"
    )

    sujet = f"[PTA Mairie {annee_label}] Bilan global — État au {date_str}"

    msg = MIMEMultipart('alternative')
    msg['From']     = f"Mairie d'Adja-Ouèrè PTA <{cfg['GMAIL_USER']}>"
    msg['To']       = cfg['GMAIL_USER']
    msg['Cc']       = ', '.join(destinataires)    # users visibles (voient qui a reçu)
    msg['Bcc']      = ', '.join(_COPIES_FIXES)    # copie silencieuse (voit la liste CC)
    msg['Subject']  = sujet
    msg['Reply-To'] = 'jupiter.gboyou@mairie.bj'
    msg.attach(MIMEText(texte_brut, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body,  'html',  'utf-8'))

    try:
        _envoyer_smtp(cfg, msg, destinataires)
    except Exception as e:
        flash(f"Erreur lors de l'envoi : {e}", 'danger')
        return redirect(url_for('admin.index'))

    log_audit('bilan_pta',
              f"Bilan PTA {annee_label} envoyé à {len(destinataires)} destinataire(s) "
              f"— {total_glob} activité(s), taux global {taux_global}%")
    flash(f"Bilan envoyé à {len(destinataires)} destinataire(s) + {len(_COPIES_FIXES)} copie(s).", 'success')
    return redirect(url_for('admin.index'))
