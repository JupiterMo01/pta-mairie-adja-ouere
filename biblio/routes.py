from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from models import (db, BiblioActivite, BiblioTache, Direction, Service,
                    MODES_EXECUTION, StructureExterne, Annee, Programme, Projet, Activite, Tache)
from biblio import biblio_bp


def admin_editeur_only(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin_editeur':
            flash('Accès réservé au Super Administrateur.', 'danger')
            return redirect(url_for('pta.global_pta'))
        return f(*args, **kwargs)
    return decorated


def admin_ou_lecteur(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ('admin_editeur', 'admin_lecteur'):
            flash('Accès refusé.', 'danger')
            return redirect(url_for('pta.global_pta'))
        return f(*args, **kwargs)
    return decorated


def _parse_float(val, default=0.0):
    try:
        if isinstance(val, str):
            val = val.strip().replace(' ', '').replace(' ', '')
            if ',' in val:
                val = val.replace('.', '').replace(',', '.')
        return float(val or 0)
    except (ValueError, TypeError):
        return default


def _renumeroter(act_id):
    taches = BiblioTache.query.filter_by(biblio_activite_id=act_id).order_by(BiblioTache.numero).all()
    for i, t in enumerate(taches, 1):
        t.numero = i
    db.session.flush()


def _activite_from_form(a):
    a.nom = request.form.get('nom', '').strip() or a.nom
    a.description = request.form.get('description', '').strip()
    a.mode_execution = request.form.get('mode_execution', '').strip() or 'Direct'
    a.type_activite = request.form.get('type_activite', 'Activité de fonctionnement').strip() or 'Activité de fonctionnement'
    a.direction_responsable_id = request.form.get('direction_responsable_id') or None
    if a.direction_responsable_id:
        a.direction_responsable_id = int(a.direction_responsable_id)
    imp_type = request.form.get('imputation_type', 'neant')
    if imp_type == 'ligne':
        a.imputation_budgetaire = request.form.get('imputation_budgetaire', '').strip() or 'NÉANT'
    else:
        a.imputation_budgetaire = 'NÉANT'
    a.periode_debut = request.form.get('periode_debut', '').strip() or None
    a.periode_fin   = request.form.get('periode_fin',   '').strip() or None
    a.poids = _parse_float(request.form.get('poids'))
    a.ressources_propres = _parse_float(request.form.get('ressources_propres'))
    a.fadec_affecte = _parse_float(request.form.get('fadec_affecte'))
    a.fadec_non_affecte = _parse_float(request.form.get('fadec_non_affecte'))
    a.autres_partenaires = _parse_float(request.form.get('autres_partenaires'))
    a.autres_fonds = _parse_float(request.form.get('autres_fonds'))
    a.details_financement = request.form.get('details_financement', '').strip() or 'RAS'
    a.acteurs_externes = request.form.get('acteurs_externes', '').strip()
    structures_mode = request.form.get('structures_mode', 'aucun')
    if structures_mode == 'tous_services':
        a.services_associes = Service.query.order_by(Service.nom).all()
        a.directions_associees = []
    elif structures_mode == 'toutes_directions':
        a.services_associes = []
        a.directions_associees = Direction.query.order_by(Direction.nom).all()
    elif structures_mode == 'tous_sd':
        a.services_associes = Service.query.order_by(Service.nom).all()
        a.directions_associees = Direction.query.order_by(Direction.nom).all()
    elif structures_mode == 'manuel':
        a.services_associes = [db.session.get(Service, int(i)) for i in request.form.getlist('services_associes') if i]
        a.directions_associees = [db.session.get(Direction, int(i)) for i in request.form.getlist('directions_associees') if i]
    else:  # aucun
        a.services_associes = []
        a.directions_associees = []
    a.structures_externes = [db.session.get(StructureExterne, int(i))
                             for i in request.form.getlist('structures_externes') if i]


def _tache_from_form(t):
    t.nom = request.form.get('nom', '').strip() or t.nom
    t.poids = _parse_float(request.form.get('poids'))
    t.description = request.form.get('description', '').strip()
    resp_ref = request.form.get('responsable_ref', '').strip()
    if resp_ref.startswith('s_'):
        t.service_responsable_id = int(resp_ref[2:])
        t.direction_responsable_id = None
    elif resp_ref.startswith('d_'):
        t.direction_responsable_id = int(resp_ref[2:])
        t.service_responsable_id = None
    else:
        t.service_responsable_id = None
        t.direction_responsable_id = None
    imp_type = request.form.get('imputation_type', 'neant')
    if imp_type == 'ligne':
        t.imputation_budgetaire = request.form.get('imputation_budgetaire', '').strip() or 'NÉANT'
    else:
        t.imputation_budgetaire = 'NÉANT'
    t.ressources_propres = _parse_float(request.form.get('ressources_propres'))
    t.fadec_affecte = _parse_float(request.form.get('fadec_affecte'))
    t.fadec_non_affecte = _parse_float(request.form.get('fadec_non_affecte'))
    t.autres_partenaires = _parse_float(request.form.get('autres_partenaires'))
    t.autres_fonds = _parse_float(request.form.get('autres_fonds'))
    t.details_financement = request.form.get('details_financement', '').strip() or 'RAS'
    t.acteurs_externes = request.form.get('acteurs_externes', '').strip()
    t.mode_execution  = request.form.get('mode_execution',  '').strip() or 'Direct'
    t.periode_debut   = request.form.get('periode_debut',   '').strip() or None
    t.periode_fin     = request.form.get('periode_fin',     '').strip() or None
    t.observations    = request.form.get('observations',    '').strip() or None
    structures_mode = request.form.get('structures_mode', 'aucun')
    if structures_mode == 'tous_services':
        t.services_concernes = Service.query.order_by(Service.nom).all()
        t.directions_associees = []
    elif structures_mode == 'toutes_directions':
        t.services_concernes = []
        t.directions_associees = Direction.query.order_by(Direction.nom).all()
    elif structures_mode == 'tous_sd':
        t.services_concernes = Service.query.order_by(Service.nom).all()
        t.directions_associees = Direction.query.order_by(Direction.nom).all()
    elif structures_mode == 'manuel':
        t.services_concernes = [db.session.get(Service, int(i)) for i in request.form.getlist('services_concernes') if i]
        t.directions_associees = [db.session.get(Direction, int(i)) for i in request.form.getlist('directions_associees') if i]
    else:  # aucun
        t.services_concernes = []
        t.directions_associees = []
    t.structures_externes = [db.session.get(StructureExterne, int(i))
                             for i in request.form.getlist('structures_externes') if i]


# ─── Index ────────────────────────────────────────────────────────────────────

@biblio_bp.route('/')
@admin_ou_lecteur
def index():
    # Toutes les activités — la recherche est gérée côté client (JS)
    activites = BiblioActivite.query.order_by(BiblioActivite.nom).all()

    directions = Direction.query.order_by(Direction.nom).all()
    services = Service.query.order_by(Service.nom).all()
    structures_externes = StructureExterne.query.order_by(StructureExterne.nom).all()
    # Activités PTA de toutes les années (pour import)
    pta_acts = (
        db.session.query(Annee.annee, Activite.id, Activite.nom)
        .join(Programme, Programme.annee_id == Annee.id)
        .join(Projet,    Projet.programme_id == Programme.id)
        .join(Activite,  Activite.projet_id == Projet.id)
        .order_by(Annee.annee.desc(), Activite.nom)
        .all()
    )
    return render_template('biblio/index.html',
                           activites=activites, directions=directions,
                           services=services, modes_execution=MODES_EXECUTION,
                           structures_externes=structures_externes,
                           pta_acts=pta_acts)


# ─── Activités ────────────────────────────────────────────────────────────────

@biblio_bp.route('/activite/add', methods=['POST'])
@admin_editeur_only
def activite_add():
    nom = request.form.get('nom', '').strip()
    if not nom:
        flash('Le nom est obligatoire.', 'danger')
        return redirect(url_for('biblio.index'))
    a = BiblioActivite(nom=nom)
    _activite_from_form(a)
    db.session.add(a)
    db.session.commit()
    flash(f'Activité « {nom} » ajoutée à la bibliothèque.', 'success')
    return redirect(url_for('biblio.index', go=f'bact-{a.id}'))


@biblio_bp.route('/activite/<int:act_id>/edit', methods=['POST'])
@admin_editeur_only
def activite_edit(act_id):
    a = db.get_or_404(BiblioActivite, act_id)
    _activite_from_form(a)
    db.session.commit()
    flash('Activité mise à jour.', 'success')
    return redirect(url_for('biblio.index', go=f'bact-{act_id}'))


@biblio_bp.route('/activite/<int:act_id>/delete', methods=['POST'])
@admin_editeur_only
def activite_delete(act_id):
    a = db.get_or_404(BiblioActivite, act_id)
    # Trouver l'activité voisine (précédente ou suivante) pour le scroll de retour
    toutes = [x.id for x in BiblioActivite.query.order_by(BiblioActivite.nom).all()]
    idx = toutes.index(act_id) if act_id in toutes else -1
    voisine_id = None
    if idx >= 0:
        if idx + 1 < len(toutes):
            voisine_id = toutes[idx + 1]   # suivante (préférence)
        elif idx > 0:
            voisine_id = toutes[idx - 1]   # précédente si c'était la dernière
    db.session.delete(a)
    db.session.commit()
    flash('Activité supprimée de la bibliothèque.', 'success')
    if voisine_id:
        return redirect(url_for('biblio.index', go=f'bact-{voisine_id}'))
    return redirect(url_for('biblio.index'))


# ─── Tâches ───────────────────────────────────────────────────────────────────

@biblio_bp.route('/activite/<int:act_id>/tache/add', methods=['POST'])
@admin_editeur_only
def tache_add(act_id):
    db.get_or_404(BiblioActivite, act_id)
    nom = request.form.get('nom', '').strip()
    if not nom:
        flash('Le nom est obligatoire.', 'danger')
        return redirect(url_for('biblio.index'))
    # Insertion après une tâche existante ?
    after_id = request.form.get('after_id', type=int)
    if after_id:
        ref = BiblioTache.query.filter_by(id=after_id, biblio_activite_id=act_id).first()
        if ref:
            apres = BiblioTache.query.filter_by(biblio_activite_id=act_id)\
                                      .filter(BiblioTache.numero > ref.numero).all()
            for ta in apres:
                ta.numero += 1
            db.session.flush()
            numero = ref.numero + 1
        else:
            last = BiblioTache.query.filter_by(biblio_activite_id=act_id).order_by(BiblioTache.numero.desc()).first()
            numero = (last.numero + 1) if last else 1
    else:
        last = BiblioTache.query.filter_by(biblio_activite_id=act_id).order_by(BiblioTache.numero.desc()).first()
        numero = (last.numero + 1) if last else 1
    t = BiblioTache(biblio_activite_id=act_id, numero=numero, nom=nom)
    _tache_from_form(t)
    db.session.add(t)
    db.session.commit()
    flash(f'Tâche « {nom} » ajoutée.', 'success')
    return redirect(url_for('biblio.index', go=f'btache-{t.id}'))


@biblio_bp.route('/tache/<int:tache_id>/edit', methods=['POST'])
@admin_editeur_only
def tache_edit(tache_id):
    t = db.get_or_404(BiblioTache, tache_id)
    _tache_from_form(t)
    db.session.commit()
    flash('Tâche mise à jour.', 'success')
    return redirect(url_for('biblio.index', go=f'btache-{tache_id}'))


@biblio_bp.route('/tache/<int:tache_id>/move/<direction>', methods=['POST'])
@admin_editeur_only
def tache_move(tache_id, direction):
    t = db.get_or_404(BiblioTache, tache_id)
    act_id = t.biblio_activite_id
    taches = BiblioTache.query.filter_by(biblio_activite_id=act_id).order_by(BiblioTache.numero).all()
    idx = next((i for i, x in enumerate(taches) if x.id == tache_id), None)
    if direction == 'up' and idx and idx > 0:
        taches[idx].numero, taches[idx - 1].numero = taches[idx - 1].numero, taches[idx].numero
    elif direction == 'down' and idx is not None and idx < len(taches) - 1:
        taches[idx].numero, taches[idx + 1].numero = taches[idx + 1].numero, taches[idx].numero
    db.session.flush()
    _renumeroter(act_id)
    db.session.commit()
    return redirect(url_for('biblio.index', go=f'btache-{tache_id}'))


@biblio_bp.route('/tache/<int:tache_id>/duplicate', methods=['POST'])
@admin_editeur_only
def tache_duplicate(tache_id):
    t = db.get_or_404(BiblioTache, tache_id)
    act_id = t.biblio_activite_id
    placement = request.form.get('placement', 'end')
    if placement == 'after':
        apres = BiblioTache.query.filter_by(biblio_activite_id=act_id)\
                                  .filter(BiblioTache.numero > t.numero).all()
        for ta in apres:
            ta.numero += 1
        db.session.flush()
        new_num = t.numero + 1
    else:
        last = BiblioTache.query.filter_by(biblio_activite_id=act_id).order_by(BiblioTache.numero.desc()).first()
        new_num = (last.numero + 1) if last else 1
    nt = BiblioTache(
        biblio_activite_id=act_id, numero=new_num, nom=t.nom,
        description=t.description, poids=t.poids,
        service_responsable_id=t.service_responsable_id,
        direction_responsable_id=t.direction_responsable_id,
        imputation_budgetaire=t.imputation_budgetaire,
        mode_execution=t.mode_execution or 'Direct',
        periode_debut=t.periode_debut,
        periode_fin=t.periode_fin,
        ressources_propres=t.ressources_propres or 0,
        fadec_affecte=t.fadec_affecte or 0,
        fadec_non_affecte=t.fadec_non_affecte or 0,
        autres_partenaires=t.autres_partenaires or 0,
        autres_fonds=t.autres_fonds or 0,
        details_financement=t.details_financement,
        acteurs_externes=t.acteurs_externes,
        observations=t.observations,
    )
    nt.services_concernes = list(t.services_concernes)
    nt.directions_associees = list(t.directions_associees)
    nt.structures_externes = list(t.structures_externes)
    db.session.add(nt)
    db.session.flush()
    _renumeroter(act_id)
    db.session.commit()
    flash(f'Tâche « {t.nom} » dupliquée.', 'success')
    return redirect(url_for('biblio.index', go=f'btache-{nt.id}'))


@biblio_bp.route('/tache/<int:tache_id>/delete', methods=['POST'])
@admin_editeur_only
def tache_delete(tache_id):
    t = db.get_or_404(BiblioTache, tache_id)
    act_id = t.biblio_activite_id
    db.session.delete(t)
    db.session.flush()
    _renumeroter(act_id)
    db.session.commit()
    flash('Tâche supprimée.', 'success')
    return redirect(url_for('biblio.index', go=f'bact-{act_id}'))


# ─── Duplication d'activité ──────────────────────────────────────────────────

@biblio_bp.route('/activite/<int:act_id>/duplicate', methods=['POST'])
@admin_editeur_only
def activite_duplicate(act_id):
    src = db.get_or_404(BiblioActivite, act_id)
    new_nom = (src.nom + ' (copie)')[:300]
    a = BiblioActivite(
        nom=new_nom,
        description=src.description,
        direction_responsable_id=src.direction_responsable_id,
        mode_execution=src.mode_execution,
        type_activite=src.type_activite,
        imputation_budgetaire=src.imputation_budgetaire,
        periode_debut=src.periode_debut,
        periode_fin=src.periode_fin,
        poids=src.poids or 0,
        ressources_propres=src.ressources_propres or 0,
        fadec_affecte=src.fadec_affecte or 0,
        fadec_non_affecte=src.fadec_non_affecte or 0,
        autres_partenaires=src.autres_partenaires or 0,
        autres_fonds=src.autres_fonds or 0,
        details_financement=src.details_financement,
        acteurs_externes=src.acteurs_externes,
    )
    a.services_associes   = list(src.services_associes)
    a.directions_associees = list(src.directions_associees)
    a.structures_externes  = list(src.structures_externes)
    db.session.add(a)
    db.session.flush()
    for t in sorted(src.taches, key=lambda x: x.numero):
        nt = BiblioTache(
            biblio_activite_id=a.id, numero=t.numero, nom=t.nom,
            description=t.description, poids=t.poids or 0,
            service_responsable_id=t.service_responsable_id,
            direction_responsable_id=t.direction_responsable_id,
            imputation_budgetaire=t.imputation_budgetaire,
            mode_execution=t.mode_execution or 'Direct',
            periode_debut=t.periode_debut,
            periode_fin=t.periode_fin,
            ressources_propres=t.ressources_propres or 0,
            fadec_affecte=t.fadec_affecte or 0,
            fadec_non_affecte=t.fadec_non_affecte or 0,
            autres_partenaires=t.autres_partenaires or 0,
            autres_fonds=t.autres_fonds or 0,
            details_financement=t.details_financement,
            acteurs_externes=t.acteurs_externes,
            observations=t.observations,
        )
        nt.services_concernes  = list(t.services_concernes)
        nt.directions_associees = list(t.directions_associees)
        nt.structures_externes  = list(t.structures_externes)
        db.session.add(nt)
    db.session.commit()
    flash(f'Activité « {src.nom} » dupliquée.', 'success')
    return redirect(url_for('biblio.index', go=f'bact-{a.id}'))


# ─── Import depuis PTA ───────────────────────────────────────────────────────

def _copier_tache_pta_vers_biblio(t_pta, act_biblio_id, numero):
    """Copie une Tache PTA vers une BiblioTache."""
    nt = BiblioTache(
        biblio_activite_id=act_biblio_id, numero=numero, nom=t_pta.nom,
        description=t_pta.description, poids=t_pta.poids or 0,
        service_responsable_id=t_pta.service_responsable_id,
        direction_responsable_id=t_pta.direction_responsable_id,
        imputation_budgetaire=t_pta.imputation_budgetaire,
        mode_execution=t_pta.mode_execution or 'Direct',
        periode_debut=t_pta.periode_debut,
        periode_fin=t_pta.periode_fin,
        ressources_propres=t_pta.ressources_propres or 0,
        fadec_affecte=t_pta.fadec_affecte or 0,
        fadec_non_affecte=t_pta.fadec_non_affecte or 0,
        autres_partenaires=t_pta.autres_partenaires or 0,
        autres_fonds=t_pta.autres_fonds or 0,
        details_financement=t_pta.details_financement,
        acteurs_externes=t_pta.acteurs_externes,
        observations=t_pta.observations,
    )
    nt.services_concernes  = list(t_pta.services_concernes)
    nt.directions_associees = list(t_pta.directions_associees)
    nt.structures_externes  = list(t_pta.structures_externes)
    return nt


@biblio_bp.route('/import-activite-from-pta', methods=['POST'])
@admin_editeur_only
def import_activite_from_pta():
    """Importe une activité PTA (avec toutes ses tâches) dans la bibliothèque."""
    act_id = request.form.get('pta_activite_id', type=int)
    if not act_id:
        flash('Aucune activité sélectionnée.', 'danger')
        return redirect(url_for('biblio.index'))
    src = db.get_or_404(Activite, act_id)
    a = BiblioActivite(
        nom=src.nom,
        description=src.description,
        direction_responsable_id=src.direction_responsable_id,
        mode_execution=src.mode_execution or 'Direct',
        type_activite=getattr(src, 'type_activite', None) or 'Activité de fonctionnement',
        imputation_budgetaire=src.imputation_budgetaire,
        periode_debut=src.periode_debut,
        periode_fin=src.periode_fin,
        poids=src.poids or 0,
        ressources_propres=src.ressources_propres or 0,
        fadec_affecte=src.fadec_affecte or 0,
        fadec_non_affecte=src.fadec_non_affecte or 0,
        autres_partenaires=src.autres_partenaires or 0,
        autres_fonds=src.autres_fonds or 0,
        details_financement=src.details_financement,
        acteurs_externes=src.acteurs_externes,
    )
    a.services_associes    = list(src.services_intervenants)
    a.directions_associees = list(src.directions_associees)
    a.structures_externes  = list(src.structures_externes)
    db.session.add(a)
    db.session.flush()
    for i, t in enumerate(sorted(src.taches, key=lambda x: (x.ordre or 0, x.id)), 1):
        db.session.add(_copier_tache_pta_vers_biblio(t, a.id, i))
    db.session.commit()
    flash(f'Activité « {src.nom} » importée depuis le PTA ({len(src.taches)} tâche(s)).', 'success')
    return redirect(url_for('biblio.index', go=f'bact-{a.id}'))


@biblio_bp.route('/activite/<int:act_id>/import-taches-from-pta', methods=['POST'])
@admin_editeur_only
def import_taches_from_pta(act_id):
    """Importe des tâches d'une activité PTA dans une activité bibliothèque existante."""
    biblio_act = db.get_or_404(BiblioActivite, act_id)
    pta_act_id = request.form.get('pta_activite_id', type=int)
    if not pta_act_id:
        flash('Aucune activité PTA sélectionnée.', 'danger')
        return redirect(url_for('biblio.index', go=f'bact-{act_id}'))
    src = db.get_or_404(Activite, pta_act_id)
    last = BiblioTache.query.filter_by(biblio_activite_id=act_id)\
                             .order_by(BiblioTache.numero.desc()).first()
    next_num = (last.numero + 1) if last else 1
    nb = 0
    for t in sorted(src.taches, key=lambda x: (x.ordre or 0, x.id)):
        db.session.add(_copier_tache_pta_vers_biblio(t, act_id, next_num))
        next_num += 1
        nb += 1
    db.session.commit()
    flash(f'{nb} tâche(s) importée(s) depuis « {src.nom} » (PTA).', 'success')
    return redirect(url_for('biblio.index', go=f'bact-{act_id}'))


@biblio_bp.route('/activite/<int:act_id>/import-taches-from-biblio', methods=['POST'])
@admin_editeur_only
def import_taches_from_biblio(act_id):
    """Importe les tâches d'une autre activité bibliothèque dans celle-ci."""
    biblio_act = db.get_or_404(BiblioActivite, act_id)
    src_id = request.form.get('biblio_src_id', type=int)
    if not src_id or src_id == act_id:
        flash('Sélectionnez une activité bibliothèque source différente.', 'danger')
        return redirect(url_for('biblio.index', go=f'bact-{act_id}'))
    src = db.get_or_404(BiblioActivite, src_id)
    last = BiblioTache.query.filter_by(biblio_activite_id=act_id)\
                             .order_by(BiblioTache.numero.desc()).first()
    next_num = (last.numero + 1) if last else 1
    nb = 0
    for t in sorted(src.taches, key=lambda x: x.numero):
        nt = BiblioTache(
            biblio_activite_id=act_id, numero=next_num, nom=t.nom,
            description=t.description, poids=t.poids or 0,
            service_responsable_id=t.service_responsable_id,
            direction_responsable_id=t.direction_responsable_id,
            imputation_budgetaire=t.imputation_budgetaire,
            mode_execution=t.mode_execution or 'Direct',
            periode_debut=t.periode_debut,
            periode_fin=t.periode_fin,
            ressources_propres=t.ressources_propres or 0,
            fadec_affecte=t.fadec_affecte or 0,
            fadec_non_affecte=t.fadec_non_affecte or 0,
            autres_partenaires=t.autres_partenaires or 0,
            autres_fonds=t.autres_fonds or 0,
            details_financement=t.details_financement,
            acteurs_externes=t.acteurs_externes,
            observations=t.observations,
        )
        nt.services_concernes  = list(t.services_concernes)
        nt.directions_associees = list(t.directions_associees)
        nt.structures_externes  = list(t.structures_externes)
        db.session.add(nt)
        next_num += 1
        nb += 1
    db.session.commit()
    flash(f'{nb} tâche(s) importée(s) depuis « {src.nom} » (Bibliothèque).', 'success')
    return redirect(url_for('biblio.index', go=f'bact-{act_id}'))