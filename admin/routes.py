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

    user = User(
        nom=nom, prenom=prenom, login=login_val, role=role,
        direction_id=int(direction_id) if direction_id else None,
        service_id=int(service_id) if service_id else None,
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
                # Many-to-many : services et directions intervenants
                act_new.services_intervenants = list(act_src.services_intervenants)
                act_new.directions_associees  = list(act_src.directions_associees)
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
                    # Many-to-many : services et directions concernés
                    tache_new.services_concernes   = list(tache_src.services_concernes)
                    tache_new.directions_associees = list(tache_src.directions_associees)
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
@admin_required
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