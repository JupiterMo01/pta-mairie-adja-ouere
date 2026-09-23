from datetime import datetime, timezone
from functools import wraps
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user

from models import db, Direction, Service, \
                   BudgetPluriannuel, MontantPluriannuelPTA, MontantPluriannuelPAI, \
                   TauxExecPTA, TauxExecPAI, TauxFinPTA, TauxFinPAI, \
                   TauxEfficacitePTA, TauxEfficacitePAI, TauxEfficiencePTA, TauxEfficiencePAI, \
                   TauxExecDirection, TauxExecService
from pluriannuel import pluriannuel_bp
from utils import log_audit


def editeur_only(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin_editeur':
            flash("Accès réservé à l'administrateur éditeur.", 'danger')
            return redirect(url_for('pluriannuel.index'))
        return f(*args, **kwargs)
    return decorated


def _parse_float(v):
    try:
        return float(str(v or '0').replace(' ', '').replace(',', '.'))
    except (TypeError, ValueError):
        return 0.0


# ── Route principale ──────────────────────────────────────────────────────────

def _redir(anchor=''):
    return redirect(url_for('pluriannuel.index') + anchor)


def _parse_taux(v):
    """Retourne un float entre 0 et 100 ou None si vide."""
    s = str(v or '').replace(' ', '').replace(',', '.')
    if not s:
        return None
    try:
        f = round(float(s), 2)
        return max(0.0, min(100.0, f))
    except (TypeError, ValueError):
        return None




@pluriannuel_bp.route('/')
@login_required
def index():
    annees          = BudgetPluriannuel.query.order_by(BudgetPluriannuel.annee).all()
    pta_annees      = MontantPluriannuelPTA.query.order_by(MontantPluriannuelPTA.annee).all()
    pai_annees      = MontantPluriannuelPAI.query.order_by(MontantPluriannuelPAI.annee).all()
    pta_exec_annees = TauxExecPTA.query.order_by(TauxExecPTA.annee).all()
    pai_exec_annees = TauxExecPAI.query.order_by(TauxExecPAI.annee).all()
    pta_fin_annees        = TauxFinPTA.query.order_by(TauxFinPTA.annee).all()
    pai_fin_annees        = TauxFinPAI.query.order_by(TauxFinPAI.annee).all()
    pta_efficacite_annees = TauxEfficacitePTA.query.order_by(TauxEfficacitePTA.annee).all()
    pai_efficacite_annees = TauxEfficacitePAI.query.order_by(TauxEfficacitePAI.annee).all()
    pta_efficience_annees = TauxEfficiencePTA.query.order_by(TauxEfficiencePTA.annee).all()
    pai_efficience_annees = TauxEfficiencePAI.query.order_by(TauxEfficiencePAI.annee).all()
    dir_exec_rows = TauxExecDirection.query.order_by(
        TauxExecDirection.annee, TauxExecDirection.direction_id).all()
    svc_exec_rows = TauxExecService.query.order_by(
        TauxExecService.annee, TauxExecService.service_id).all()
    directions    = Direction.query.order_by(Direction.code).all()
    services      = Service.query.order_by(Service.code).all()
    dir_exec_json = [
        {'id': r.id, 'annee': r.annee, 'code': r.direction.code,
         'nom': r.direction.nom, 't1': r.t1, 't2': r.t2, 't3': r.t3, 't4': r.t4}
        for r in dir_exec_rows
    ]
    svc_exec_json = [
        {'id': r.id, 'annee': r.annee, 'code': r.service.code,
         'nom': r.service.nom, 't1': r.t1, 't2': r.t2, 't3': r.t3, 't4': r.t4}
        for r in svc_exec_rows
    ]
    return render_template('pluriannuel/index.html',
                           annees=annees, pta_annees=pta_annees, pai_annees=pai_annees,
                           pta_exec_annees=pta_exec_annees, pai_exec_annees=pai_exec_annees,
                           pta_fin_annees=pta_fin_annees, pai_fin_annees=pai_fin_annees,
                           pta_efficacite_annees=pta_efficacite_annees,
                           pai_efficacite_annees=pai_efficacite_annees,
                           pta_efficience_annees=pta_efficience_annees,
                           pai_efficience_annees=pai_efficience_annees,
                           dir_exec_rows=dir_exec_rows, svc_exec_rows=svc_exec_rows,
                           directions=directions, services=services,
                           dir_exec_json=dir_exec_json, svc_exec_json=svc_exec_json)


# ── Ajouter une année ─────────────────────────────────────────────────────────

@pluriannuel_bp.route('/add', methods=['POST'])
@editeur_only
def add():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-budget')

    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return _redir('#section-budget')

    if BudgetPluriannuel.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà.", 'warning')
        return _redir('#section-budget')

    primitif  = _parse_float(request.form.get('budget_primitif'))
    collectif = _parse_float(request.form.get('budget_collectif'))

    row = BudgetPluriannuel(
        annee=annee_val,
        budget_primitif=primitif,
        budget_collectif=collectif,
        date_maj=datetime.now(timezone.utc),
        modified_by_id=current_user.id,
    )
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_add', f"Année {annee_val} ajoutée — primitif {primitif:,.0f} / collectif {collectif:,.0f}")
    flash(f"Année {annee_val} ajoutée.", 'success')
    return _redir('#section-budget')


# ── Modifier une année ────────────────────────────────────────────────────────

@pluriannuel_bp.route('/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit(row_id):
    row = db.get_or_404(BudgetPluriannuel, row_id)
    row.budget_primitif  = _parse_float(request.form.get('budget_primitif'))
    row.budget_collectif = _parse_float(request.form.get('budget_collectif'))
    row.date_maj         = datetime.now(timezone.utc)
    row.modified_by_id   = current_user.id
    db.session.commit()
    log_audit('pluriannuel_edit', f"Année {row.annee} modifiée — primitif {row.budget_primitif:,.0f} / collectif {row.budget_collectif:,.0f}")
    flash(f"Année {row.annee} mise à jour.", 'success')
    return _redir('#section-budget')


# ── Supprimer une année ───────────────────────────────────────────────────────

@pluriannuel_bp.route('/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete(row_id):
    row = db.get_or_404(BudgetPluriannuel, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_delete', f"Année {annee_val} supprimée")
    flash(f"Année {annee_val} supprimée.", 'warning')
    return _redir('#section-budget')


# ════════════════════════════════════════════════════════════════
# Section II — Montants PTA
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/pta/add', methods=['POST'])
@editeur_only
def add_pta():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pta')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return _redir('#section-pta')
    if MontantPluriannuelPTA.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà dans les montants PTA.", 'warning')
        return _redir('#section-pta')
    row = MontantPluriannuelPTA(
        annee=annee_val,
        montant_pta=_parse_float(request.form.get('montant_pta')),
        montant_pta_rev=_parse_float(request.form.get('montant_pta_rev')),
        date_maj=datetime.now(timezone.utc),
        modified_by_id=current_user.id,
    )
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pta_add', f"PTA {annee_val} ajouté")
    flash(f"Année {annee_val} (PTA) ajoutée.", 'success')
    return _redir('#section-pta')


@pluriannuel_bp.route('/pta/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pta(row_id):
    row = db.get_or_404(MontantPluriannuelPTA, row_id)
    row.montant_pta     = _parse_float(request.form.get('montant_pta'))
    row.montant_pta_rev = _parse_float(request.form.get('montant_pta_rev'))
    row.date_maj        = datetime.now(timezone.utc)
    row.modified_by_id  = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pta_edit', f"PTA {row.annee} modifié")
    flash(f"Année {row.annee} (PTA) mise à jour.", 'success')
    return _redir('#section-pta')


@pluriannuel_bp.route('/pta/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pta(row_id):
    row = db.get_or_404(MontantPluriannuelPTA, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pta_delete', f"PTA {annee_val} supprimé")
    flash(f"Année {annee_val} (PTA) supprimée.", 'warning')
    return _redir('#section-pta')


# ════════════════════════════════════════════════════════════════
# Section III — Montants PAI
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/pai/add', methods=['POST'])
@editeur_only
def add_pai():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pai')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return _redir('#section-pai')
    if MontantPluriannuelPAI.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà dans les montants PAI.", 'warning')
        return _redir('#section-pai')
    row = MontantPluriannuelPAI(
        annee=annee_val,
        montant_pai=_parse_float(request.form.get('montant_pai')),
        montant_pai_rev=_parse_float(request.form.get('montant_pai_rev')),
        date_maj=datetime.now(timezone.utc),
        modified_by_id=current_user.id,
    )
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pai_add', f"PAI {annee_val} ajouté")
    flash(f"Année {annee_val} (PAI) ajoutée.", 'success')
    return _redir('#section-pai')


@pluriannuel_bp.route('/pai/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pai(row_id):
    row = db.get_or_404(MontantPluriannuelPAI, row_id)
    row.montant_pai     = _parse_float(request.form.get('montant_pai'))
    row.montant_pai_rev = _parse_float(request.form.get('montant_pai_rev'))
    row.date_maj        = datetime.now(timezone.utc)
    row.modified_by_id  = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pai_edit', f"PAI {row.annee} modifié")
    flash(f"Année {row.annee} (PAI) mise à jour.", 'success')
    return _redir('#section-pai')


@pluriannuel_bp.route('/pai/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pai(row_id):
    row = db.get_or_404(MontantPluriannuelPAI, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pai_delete', f"PAI {annee_val} supprimé")
    flash(f"Année {annee_val} (PAI) supprimée.", 'warning')
    return _redir('#section-pai')


# ════════════════════════════════════════════════════════════════
# Section IV — Taux d'exécution physique PTA
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/pta-exec/add', methods=['POST'])
@editeur_only
def add_pta_exec():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pta-exec')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return _redir('#section-pta-exec')
    if TauxExecPTA.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (taux exec PTA).", 'warning')
        return _redir('#section-pta-exec')
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    row = TauxExecPTA(annee=annee_val, t1=t1, t2=t2, t3=t3, t4=t4,
                      date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id)
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pta_exec_add', f"Taux exec PTA {annee_val} ajouté")
    flash(f"Taux exécution PTA {annee_val} ajouté.", 'success')
    return _redir('#section-pta-exec')


@pluriannuel_bp.route('/pta-exec/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pta_exec(row_id):
    row = db.get_or_404(TauxExecPTA, row_id)
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    row.t1 = t1; row.t2 = t2; row.t3 = t3; row.t4 = t4
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pta_exec_edit', f"Taux exec PTA {row.annee} modifié")
    flash(f"Taux exécution PTA {row.annee} mis à jour.", 'success')
    return _redir('#section-pta-exec')


@pluriannuel_bp.route('/pta-exec/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pta_exec(row_id):
    row = db.get_or_404(TauxExecPTA, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pta_exec_delete', f"Taux exec PTA {annee_val} supprimé")
    flash(f"Taux exécution PTA {annee_val} supprimé.", 'warning')
    return _redir('#section-pta-exec')


# ════════════════════════════════════════════════════════════════
# Section V — Taux d'exécution physique PAI
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/pai-exec/add', methods=['POST'])
@editeur_only
def add_pai_exec():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pai-exec')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return _redir('#section-pai-exec')
    if TauxExecPAI.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (taux exec PAI).", 'warning')
        return _redir('#section-pai-exec')
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    row = TauxExecPAI(annee=annee_val, t1=t1, t2=t2, t3=t3, t4=t4,
                      date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id)
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pai_exec_add', f"Taux exec PAI {annee_val} ajouté")
    flash(f"Taux exécution PAI {annee_val} ajouté.", 'success')
    return _redir('#section-pai-exec')


@pluriannuel_bp.route('/pai-exec/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pai_exec(row_id):
    row = db.get_or_404(TauxExecPAI, row_id)
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    row.t1 = t1; row.t2 = t2; row.t3 = t3; row.t4 = t4
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pai_exec_edit', f"Taux exec PAI {row.annee} modifié")
    flash(f"Taux exécution PAI {row.annee} mis à jour.", 'success')
    return _redir('#section-pai-exec')


@pluriannuel_bp.route('/pai-exec/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pai_exec(row_id):
    row = db.get_or_404(TauxExecPAI, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pai_exec_delete', f"Taux exec PAI {annee_val} supprimé")
    flash(f"Taux exécution PAI {annee_val} supprimé.", 'warning')
    return _redir('#section-pai-exec')


# ════════════════════════════════════════════════════════════════
# Helpers taux financiers
# ════════════════════════════════════════════════════════════════

_FIN_CHAMPS = ['t1_eng','t1_mand','t1_pmt',
               't2_eng','t2_mand','t2_pmt',
               't3_eng','t3_mand','t3_pmt',
               't4_eng','t4_mand','t4_pmt']


def _lire_fin(form):
    return {c: _parse_taux(form.get(c)) for c in _FIN_CHAMPS}


# ════════════════════════════════════════════════════════════════
# Section VI — Taux d'exécution financière PTA
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/pta-fin/add', methods=['POST'])
@editeur_only
def add_pta_fin():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pta-fin')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return _redir('#section-pta-fin')
    if TauxFinPTA.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (taux fin PTA).", 'warning')
        return _redir('#section-pta-fin')
    vals = _lire_fin(request.form)
    row = TauxFinPTA(annee=annee_val, date_maj=datetime.now(timezone.utc),
                     modified_by_id=current_user.id, **vals)
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pta_fin_add', f"Taux fin PTA {annee_val} ajouté")
    flash(f"Taux financiers PTA {annee_val} ajoutés.", 'success')
    return _redir('#section-pta-fin')


@pluriannuel_bp.route('/pta-fin/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pta_fin(row_id):
    row = db.get_or_404(TauxFinPTA, row_id)
    for c, v in _lire_fin(request.form).items():
        setattr(row, c, v)
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pta_fin_edit', f"Taux fin PTA {row.annee} modifié")
    flash(f"Taux financiers PTA {row.annee} mis à jour.", 'success')
    return _redir('#section-pta-fin')


@pluriannuel_bp.route('/pta-fin/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pta_fin(row_id):
    row = db.get_or_404(TauxFinPTA, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pta_fin_delete', f"Taux fin PTA {annee_val} supprimé")
    flash(f"Taux financiers PTA {annee_val} supprimés.", 'warning')
    return _redir('#section-pta-fin')


# ════════════════════════════════════════════════════════════════
# Section VII — Taux d'exécution financière PAI
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/pai-fin/add', methods=['POST'])
@editeur_only
def add_pai_fin():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pai-fin')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return _redir('#section-pai-fin')
    if TauxFinPAI.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (taux fin PAI).", 'warning')
        return _redir('#section-pai-fin')
    vals = _lire_fin(request.form)
    row = TauxFinPAI(annee=annee_val, date_maj=datetime.now(timezone.utc),
                     modified_by_id=current_user.id, **vals)
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pai_fin_add', f"Taux fin PAI {annee_val} ajouté")
    flash(f"Taux financiers PAI {annee_val} ajoutés.", 'success')
    return _redir('#section-pai-fin')


@pluriannuel_bp.route('/pai-fin/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pai_fin(row_id):
    row = db.get_or_404(TauxFinPAI, row_id)
    for c, v in _lire_fin(request.form).items():
        setattr(row, c, v)
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pai_fin_edit', f"Taux fin PAI {row.annee} modifié")
    flash(f"Taux financiers PAI {row.annee} mis à jour.", 'success')
    return _redir('#section-pai-fin')


@pluriannuel_bp.route('/pai-fin/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pai_fin(row_id):
    row = db.get_or_404(TauxFinPAI, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pai_fin_delete', f"Taux fin PAI {annee_val} supprimé")
    flash(f"Taux financiers PAI {annee_val} supprimés.", 'warning')
    return _redir('#section-pai-fin')


# ════════════════════════════════════════════════════════════════
# Sections VIII/IX — Taux d'efficacité (PTA et PAI)
# ════════════════════════════════════════════════════════════════

def _crud_simple(Model, annee_val, label, anchor):
    """Helper CRUD pour les modèles à 4 trimestres simples."""
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    return t1, t2, t3, t4


@pluriannuel_bp.route('/pta-efficacite/add', methods=['POST'])
@editeur_only
def add_pta_efficacite():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pta-efficacite')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage.", 'danger')
        return _redir('#section-pta-efficacite')
    if TauxEfficacitePTA.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (efficacité PTA).", 'warning')
        return _redir('#section-pta-efficacite')
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    db.session.add(TauxEfficacitePTA(annee=annee_val, t1=t1, t2=t2, t3=t3, t4=t4,
                                     date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id))
    db.session.commit()
    log_audit('pluriannuel_pta_efficacite_add', f"Efficacité PTA {annee_val} ajouté")
    flash(f"Efficacité PTA {annee_val} ajoutée.", 'success')
    return _redir('#section-pta-efficacite')


@pluriannuel_bp.route('/pta-efficacite/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pta_efficacite(row_id):
    row = db.get_or_404(TauxEfficacitePTA, row_id)
    row.t1 = _parse_taux(request.form.get('t1'))
    row.t2 = _parse_taux(request.form.get('t2'))
    row.t3 = _parse_taux(request.form.get('t3'))
    row.t4 = _parse_taux(request.form.get('t4'))
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pta_efficacite_edit', f"Efficacité PTA {row.annee} modifié")
    flash(f"Efficacité PTA {row.annee} mise à jour.", 'success')
    return _redir('#section-pta-efficacite')


@pluriannuel_bp.route('/pta-efficacite/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pta_efficacite(row_id):
    row = db.get_or_404(TauxEfficacitePTA, row_id)
    a = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pta_efficacite_delete', f"Efficacité PTA {a} supprimé")
    flash(f"Efficacité PTA {a} supprimée.", 'warning')
    return _redir('#section-pta-efficacite')


@pluriannuel_bp.route('/pai-efficacite/add', methods=['POST'])
@editeur_only
def add_pai_efficacite():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pai-efficacite')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage.", 'danger')
        return _redir('#section-pai-efficacite')
    if TauxEfficacitePAI.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (efficacité PAI).", 'warning')
        return _redir('#section-pai-efficacite')
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    db.session.add(TauxEfficacitePAI(annee=annee_val, t1=t1, t2=t2, t3=t3, t4=t4,
                                     date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id))
    db.session.commit()
    log_audit('pluriannuel_pai_efficacite_add', f"Efficacité PAI {annee_val} ajouté")
    flash(f"Efficacité PAI {annee_val} ajoutée.", 'success')
    return _redir('#section-pai-efficacite')


@pluriannuel_bp.route('/pai-efficacite/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pai_efficacite(row_id):
    row = db.get_or_404(TauxEfficacitePAI, row_id)
    row.t1 = _parse_taux(request.form.get('t1'))
    row.t2 = _parse_taux(request.form.get('t2'))
    row.t3 = _parse_taux(request.form.get('t3'))
    row.t4 = _parse_taux(request.form.get('t4'))
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pai_efficacite_edit', f"Efficacité PAI {row.annee} modifié")
    flash(f"Efficacité PAI {row.annee} mise à jour.", 'success')
    return _redir('#section-pai-efficacite')


@pluriannuel_bp.route('/pai-efficacite/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pai_efficacite(row_id):
    row = db.get_or_404(TauxEfficacitePAI, row_id)
    a = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pai_efficacite_delete', f"Efficacité PAI {a} supprimé")
    flash(f"Efficacité PAI {a} supprimée.", 'warning')
    return _redir('#section-pai-efficacite')


# ════════════════════════════════════════════════════════════════
# Sections X/XI — Taux d'efficience (PTA et PAI)
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/pta-efficience/add', methods=['POST'])
@editeur_only
def add_pta_efficience():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pta-efficience')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage.", 'danger')
        return _redir('#section-pta-efficience')
    if TauxEfficiencePTA.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (efficience PTA).", 'warning')
        return _redir('#section-pta-efficience')
    vals = _lire_fin(request.form)
    db.session.add(TauxEfficiencePTA(annee=annee_val, date_maj=datetime.now(timezone.utc),
                                     modified_by_id=current_user.id, **vals))
    db.session.commit()
    log_audit('pluriannuel_pta_efficience_add', f"Efficience PTA {annee_val} ajouté")
    flash(f"Efficience PTA {annee_val} ajoutée.", 'success')
    return _redir('#section-pta-efficience')


@pluriannuel_bp.route('/pta-efficience/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pta_efficience(row_id):
    row = db.get_or_404(TauxEfficiencePTA, row_id)
    for c, v in _lire_fin(request.form).items():
        setattr(row, c, v)
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pta_efficience_edit', f"Efficience PTA {row.annee} modifié")
    flash(f"Efficience PTA {row.annee} mise à jour.", 'success')
    return _redir('#section-pta-efficience')


@pluriannuel_bp.route('/pta-efficience/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pta_efficience(row_id):
    row = db.get_or_404(TauxEfficiencePTA, row_id)
    a = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pta_efficience_delete', f"Efficience PTA {a} supprimé")
    flash(f"Efficience PTA {a} supprimée.", 'warning')
    return _redir('#section-pta-efficience')


@pluriannuel_bp.route('/pai-efficience/add', methods=['POST'])
@editeur_only
def add_pai_efficience():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return _redir('#section-pai-efficience')
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage.", 'danger')
        return _redir('#section-pai-efficience')
    if TauxEfficiencePAI.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (efficience PAI).", 'warning')
        return _redir('#section-pai-efficience')
    vals = _lire_fin(request.form)
    db.session.add(TauxEfficiencePAI(annee=annee_val, date_maj=datetime.now(timezone.utc),
                                     modified_by_id=current_user.id, **vals))
    db.session.commit()
    log_audit('pluriannuel_pai_efficience_add', f"Efficience PAI {annee_val} ajouté")
    flash(f"Efficience PAI {annee_val} ajoutée.", 'success')
    return _redir('#section-pai-efficience')


@pluriannuel_bp.route('/pai-efficience/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_pai_efficience(row_id):
    row = db.get_or_404(TauxEfficiencePAI, row_id)
    for c, v in _lire_fin(request.form).items():
        setattr(row, c, v)
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pai_efficience_edit', f"Efficience PAI {row.annee} modifié")
    flash(f"Efficience PAI {row.annee} mise à jour.", 'success')
    return _redir('#section-pai-efficience')


@pluriannuel_bp.route('/pai-efficience/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pai_efficience(row_id):
    row = db.get_or_404(TauxEfficiencePAI, row_id)
    a = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pai_efficience_delete', f"Efficience PAI {a} supprimé")
    flash(f"Efficience PAI {a} supprimée.", 'warning')
    return _redir('#section-pai-efficience')


# ════════════════════════════════════════════════════════════════
# Section XII — Taux d'exécution physique par direction
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/dir-exec/add', methods=['POST'])
@editeur_only
def add_dir_exec():
    try:
        annee_val = int(request.form.get('annee', 0))
        dir_id    = int(request.form.get('direction_id', 0))
    except (TypeError, ValueError):
        flash("Données invalides.", 'danger')
        return _redir('#section-dir-exec')
    if annee_val < 2016 or annee_val > 2100:
        flash("Année hors plage (2016–2100).", 'danger')
        return _redir('#section-dir-exec')
    if not dir_id:
        flash("Veuillez sélectionner une direction.", 'danger')
        return _redir('#section-dir-exec')
    if TauxExecDirection.query.filter_by(annee=annee_val, direction_id=dir_id).first():
        flash("Cette direction a déjà un taux pour cette année.", 'warning')
        return _redir('#section-dir-exec')
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    db.session.add(TauxExecDirection(
        annee=annee_val, direction_id=dir_id, t1=t1, t2=t2, t3=t3, t4=t4,
        date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id))
    db.session.commit()
    log_audit('pluriannuel_dir_exec_add', f"Exec dir {annee_val}/{dir_id} ajouté")
    flash("Taux ajouté.", 'success')
    return _redir('#section-dir-exec')


@pluriannuel_bp.route('/dir-exec/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_dir_exec(row_id):
    row = db.get_or_404(TauxExecDirection, row_id)
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    row.t1 = t1; row.t2 = t2; row.t3 = t3; row.t4 = t4
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_dir_exec_edit', f"Exec dir {row.annee}/{row.direction_id} modifié")
    flash("Taux mis à jour.", 'success')
    return _redir('#section-dir-exec')


@pluriannuel_bp.route('/dir-exec/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_dir_exec(row_id):
    row = db.get_or_404(TauxExecDirection, row_id)
    info = f"{row.annee}/{row.direction.code}"
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_dir_exec_delete', f"Exec dir {info} supprimé")
    flash("Taux supprimé.", 'warning')
    return _redir('#section-dir-exec')


# ════════════════════════════════════════════════════════════════
# Section XIII — Taux d'exécution physique par service
# ════════════════════════════════════════════════════════════════

@pluriannuel_bp.route('/svc-exec/add', methods=['POST'])
@editeur_only
def add_svc_exec():
    try:
        annee_val = int(request.form.get('annee', 0))
        svc_id    = int(request.form.get('service_id', 0))
    except (TypeError, ValueError):
        flash("Données invalides.", 'danger')
        return _redir('#section-svc-exec')
    if annee_val < 2016 or annee_val > 2100:
        flash("Année hors plage (2016–2100).", 'danger')
        return _redir('#section-svc-exec')
    if not svc_id:
        flash("Veuillez sélectionner un service.", 'danger')
        return _redir('#section-svc-exec')
    if TauxExecService.query.filter_by(annee=annee_val, service_id=svc_id).first():
        flash("Ce service a déjà un taux pour cette année.", 'warning')
        return _redir('#section-svc-exec')
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    db.session.add(TauxExecService(
        annee=annee_val, service_id=svc_id, t1=t1, t2=t2, t3=t3, t4=t4,
        date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id))
    db.session.commit()
    log_audit('pluriannuel_svc_exec_add', f"Exec svc {annee_val}/{svc_id} ajouté")
    flash("Taux ajouté.", 'success')
    return _redir('#section-svc-exec')


@pluriannuel_bp.route('/svc-exec/edit/<int:row_id>', methods=['POST'])
@editeur_only
def edit_svc_exec(row_id):
    row = db.get_or_404(TauxExecService, row_id)
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    row.t1 = t1; row.t2 = t2; row.t3 = t3; row.t4 = t4
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_svc_exec_edit', f"Exec svc {row.annee}/{row.service_id} modifié")
    flash("Taux mis à jour.", 'success')
    return _redir('#section-svc-exec')


@pluriannuel_bp.route('/svc-exec/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_svc_exec(row_id):
    row = db.get_or_404(TauxExecService, row_id)
    info = f"{row.annee}/{row.service.code}"
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_svc_exec_delete', f"Exec svc {info} supprimé")
    flash("Taux supprimé.", 'warning')
    return _redir('#section-svc-exec')


# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT EXCEL SUIVI PLURIANNUEL — openpyxl avec en-tête institutionnel
# ══════════════════════════════════════════════════════════════════════════════

def _pluri_header(ws, titre_section, nc):
    """En-tête institutionnel (bandeau + logo + contacts) + titre section."""
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    import os as _os, io as _io
    from flask import current_app

    lc = get_column_letter(nc)
    b_end   = max(nc // 4, 2)
    l_w     = max(nc // 4, 1)
    l_start = nc - l_w + 1
    c_end   = l_start - 1

    for rn, h in [(1, 22), (2, 8), (3, 22)]:
        ws.row_dimensions[rn].height = h

    ws.merge_cells(f'A1:{get_column_letter(b_end)}3')
    ws.merge_cells(f'{get_column_letter(b_end+1)}1:{get_column_letter(c_end)}3')
    if l_start <= nc:
        ws.merge_cells(f'{get_column_letter(l_start)}1:{lc}3')

    c = ws.cell(row=1, column=b_end + 1)
    c.value = "BP 02 Adja-Ouèrè\nTél : +229 01 61 91 96 12\nEmail : contact.adjaouere@mairie.bj"
    c.font = Font(bold=True, size=9)
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    try:
        from openpyxl.drawing.image import Image as _XIm
        from PIL import Image as _PI
        _img = _os.path.join(current_app.root_path, 'static', 'img')
        _H = 52
        for _path, _at_a1 in [
            (_os.path.join(_img, 'bandeau.png'),     True),
            (_os.path.join(_img, 'logo_commune.png'), False),
        ]:
            if not _os.path.exists(_path):
                continue
            _buf = _io.BytesIO()
            with _PI.open(_path) as _p:
                _ow, _oh = _p.size
                _p.save(_buf, 'PNG')
            _buf.seek(0)
            _xi = _XIm(_buf)
            _xi.height = _H
            _xi.width = int(_ow * _H / _oh)
            if _at_a1:
                ws.add_image(_xi, 'A1')
            else:
                try:
                    from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
                    from openpyxl.drawing.xdr import XDRPositiveSize2D
                    _a = OneCellAnchor()
                    _a._from = AnchorMarker(col=nc - 1, colOff=-int(_xi.width * 9525),
                                            row=0, rowOff=0)
                    _a.ext = XDRPositiveSize2D(int(_xi.width * 9525), int(_H * 9525))
                    _xi.anchor = _a
                    ws.add_image(_xi)
                except Exception:
                    ws.add_image(_xi, f'{get_column_letter(max(nc - 1, 1))}1')
    except Exception:
        pass

    ws.merge_cells(f'A4:{lc}4')
    c4 = ws['A4']
    c4.value = titre_section
    c4.font = Font(bold=True, size=13, color='FFFFFF')
    c4.alignment = Alignment(horizontal='center', vertical='center')
    c4.fill = PatternFill('solid', fgColor='1F4E79')
    ws.row_dimensions[4].height = 26
    return 5


def _pluri_footer(ws, nc):
    """Pied de page : date export + nom du service."""
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter
    from datetime import datetime as _dt
    lc  = get_column_letter(nc)
    row = ws.max_row + 1
    mid = max(nc // 2 + 1, 4)
    ws.merge_cells(f'A{row}:{get_column_letter(min(mid - 1, nc))}{row}')
    c = ws.cell(row=row, column=1,
                value=f"Exporté le {_dt.now().strftime('%d/%m/%Y à %H:%M')}")
    c.font = Font(bold=True, size=8)
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells(f'{get_column_letter(mid)}{row}:{lc}{row}')
    c2 = ws.cell(row=row, column=mid,
                 value='Direction du Développement Local et de la Planification (DDLP)')
    c2.font = Font(bold=True, size=8)
    c2.alignment = Alignment(horizontal='right', vertical='center')


def _wr_p(ws, row, values, fill, bold, brd, ctr, lft, num_cols=None):
    """Écrit une ligne dans la feuille courante."""
    from openpyxl.styles import Font
    num_cols = num_cols or set()
    for col, v in enumerate(values, 1):
        c = ws.cell(row=row, column=col, value=v)
        c.fill = fill
        c.font = Font(bold=bold, size=9)
        c.border = brd
        c.alignment = lft if col <= 2 else ctr
        if col in num_cols and isinstance(v, (int, float)):
            c.number_format = '#,##0'


# ── Sections I / II : budget pluriannuel PTA / PAI ───────────────────────────

def _write_budget_pta_sheet(ws, rows):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    NC = 5
    thin = Side(style='thin')
    brd  = Border(left=thin, right=thin, top=thin, bottom=thin)
    ctr  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    lft  = Alignment(horizontal='left',   vertical='center', wrap_text=True)
    hdr  = PatternFill('solid', fgColor='BDD7EE')
    alt1 = PatternFill('solid', fgColor='EBF5FB')
    alt2 = PatternFill('solid', fgColor='FFFFFF')
    sr = _pluri_header(ws, 'I — Évolution du montant du budget municipal PTA', NC)
    for col, h in enumerate(['Année', 'Montant PTA primitif (F CFA)',
                              'Montant PTA révisé (F CFA)', 'Écart (F CFA)', 'Variation (%)'], 1):
        c = ws.cell(row=sr, column=col, value=h)
        c.fill = hdr; c.font = Font(bold=True, size=9); c.alignment = ctr; c.border = brd
    ws.row_dimensions[sr].height = 30; sr += 1
    for idx, r in enumerate(rows):
        var = r.variation_pct
        _wr_p(ws, sr + idx,
              [r.annee, r.montant_pta or 0, r.montant_pta_rev or 0, r.ecart,
               f'{var:.2f} %' if var is not None else '—'],
              alt1 if idx % 2 == 0 else alt2, False, brd, ctr, lft, num_cols={2, 3, 4})
    for col_l, w in zip('ABCDE', [8, 28, 28, 18, 14]):
        ws.column_dimensions[col_l].width = w
    _pluri_footer(ws, NC)


def _write_budget_pai_sheet(ws, rows):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    NC = 5
    thin = Side(style='thin')
    brd  = Border(left=thin, right=thin, top=thin, bottom=thin)
    ctr  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    lft  = Alignment(horizontal='left',   vertical='center', wrap_text=True)
    hdr  = PatternFill('solid', fgColor='BDD7EE')
    alt1 = PatternFill('solid', fgColor='EBF5FB')
    alt2 = PatternFill('solid', fgColor='FFFFFF')
    sr = _pluri_header(ws, 'II — Évolution du montant du budget municipal PAI', NC)
    for col, h in enumerate(['Année', 'Montant PAI primitif (F CFA)',
                              'Montant PAI révisé (F CFA)', 'Écart (F CFA)', 'Variation (%)'], 1):
        c = ws.cell(row=sr, column=col, value=h)
        c.fill = hdr; c.font = Font(bold=True, size=9); c.alignment = ctr; c.border = brd
    ws.row_dimensions[sr].height = 30; sr += 1
    for idx, r in enumerate(rows):
        var = r.variation_pct
        _wr_p(ws, sr + idx,
              [r.annee, r.montant_pai or 0, r.montant_pai_rev or 0, r.ecart,
               f'{var:.2f} %' if var is not None else '—'],
              alt1 if idx % 2 == 0 else alt2, False, brd, ctr, lft, num_cols={2, 3, 4})
    for col_l, w in zip('ABCDE', [8, 28, 28, 18, 14]):
        ws.column_dimensions[col_l].width = w
    _pluri_footer(ws, NC)


# ── Section V : budget général ────────────────────────────────────────────────

def _write_budget_gen_sheet(ws, rows):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    NC = 5
    thin = Side(style='thin')
    brd  = Border(left=thin, right=thin, top=thin, bottom=thin)
    ctr  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    lft  = Alignment(horizontal='left',   vertical='center', wrap_text=True)
    hdr  = PatternFill('solid', fgColor='BDD7EE')
    alt1 = PatternFill('solid', fgColor='EBF5FB')
    alt2 = PatternFill('solid', fgColor='FFFFFF')
    sr = _pluri_header(ws, 'V — Évolution du budget général', NC)
    for col, h in enumerate(['Année', 'Budget primitif (F CFA)',
                              'Budget collectif (F CFA)', 'Écart (F CFA)', 'Variation (%)'], 1):
        c = ws.cell(row=sr, column=col, value=h)
        c.fill = hdr; c.font = Font(bold=True, size=9); c.alignment = ctr; c.border = brd
    ws.row_dimensions[sr].height = 30; sr += 1
    for idx, r in enumerate(rows):
        var = r.variation_pct
        _wr_p(ws, sr + idx,
              [r.annee, r.budget_primitif or 0, r.budget_collectif or 0, r.ecart,
               f'{var:.2f} %' if var is not None else '—'],
              alt1 if idx % 2 == 0 else alt2, False, brd, ctr, lft, num_cols={2, 3, 4})
    for col_l, w in zip('ABCDE', [8, 25, 25, 18, 14]):
        ws.column_dimensions[col_l].width = w
    _pluri_footer(ws, NC)


# ── Sections III/IV/VIII/IX : taux T1-T4 simples ─────────────────────────────

def _write_taux_t4_sheet(ws, titre, rows):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    NC = 5
    thin = Side(style='thin')
    brd  = Border(left=thin, right=thin, top=thin, bottom=thin)
    ctr  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    lft  = Alignment(horizontal='left',   vertical='center', wrap_text=True)
    hdr  = PatternFill('solid', fgColor='BDD7EE')
    alt1 = PatternFill('solid', fgColor='EBF5FB')
    alt2 = PatternFill('solid', fgColor='FFFFFF')
    sr = _pluri_header(ws, titre, NC)
    for col, h in enumerate(['Année', 'T1 (%)', 'T2 (%)', 'T3 (%)', 'T4 (%)'], 1):
        c = ws.cell(row=sr, column=col, value=h)
        c.fill = hdr; c.font = Font(bold=True, size=9); c.alignment = ctr; c.border = brd
    ws.row_dimensions[sr].height = 22; sr += 1
    pct = lambda v: round(v, 2) if v is not None else '—'
    for idx, r in enumerate(rows):
        _wr_p(ws, sr + idx,
              [r.annee, pct(r.t1), pct(r.t2), pct(r.t3), pct(r.t4)],
              alt1 if idx % 2 == 0 else alt2, False, brd, ctr, lft)
    for col_l, w in zip('ABCDE', [8, 12, 12, 12, 12]):
        ws.column_dimensions[col_l].width = w
    _pluri_footer(ws, NC)


# ── Sections VI/VII/X/XI : taux engagement/mandatement/paiement ──────────────

def _write_taux_fin_sheet(ws, titre, rows):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    NC = 13
    thin = Side(style='thin')
    brd  = Border(left=thin, right=thin, top=thin, bottom=thin)
    ctr  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    lft  = Alignment(horizontal='left',   vertical='center', wrap_text=True)
    hdr  = PatternFill('solid', fgColor='BDD7EE')
    alt1 = PatternFill('solid', fgColor='EBF5FB')
    alt2 = PatternFill('solid', fgColor='FFFFFF')
    sr = _pluri_header(ws, titre, NC)
    hr1 = ['Année', 'T1', '', '', 'T2', '', '', 'T3', '', '', 'T4', '', '']
    hr2 = ['', 'Eng. (%)', 'Mand. (%)', 'Pmt. (%)',
               'Eng. (%)', 'Mand. (%)', 'Pmt. (%)',
               'Eng. (%)', 'Mand. (%)', 'Pmt. (%)',
               'Eng. (%)', 'Mand. (%)', 'Pmt. (%)']
    for col, v in enumerate(hr1, 1):
        c = ws.cell(row=sr, column=col, value=v)
        c.fill = hdr; c.font = Font(bold=True, size=9); c.alignment = ctr; c.border = brd
    for col, v in enumerate(hr2, 1):
        c = ws.cell(row=sr + 1, column=col, value=v)
        c.fill = hdr; c.font = Font(bold=True, size=9); c.alignment = ctr; c.border = brd
    ws.merge_cells(f'A{sr}:A{sr+1}')
    for sc in [2, 5, 8, 11]:
        ws.merge_cells(f'{get_column_letter(sc)}{sr}:{get_column_letter(sc+2)}{sr}')
    ws.row_dimensions[sr].height = 18
    ws.row_dimensions[sr + 1].height = 18
    sr += 2
    pct = lambda v: round(v, 2) if v is not None else '—'
    for idx, r in enumerate(rows):
        _wr_p(ws, sr + idx,
              [r.annee,
               pct(r.t1_eng), pct(r.t1_mand), pct(r.t1_pmt),
               pct(r.t2_eng), pct(r.t2_mand), pct(r.t2_pmt),
               pct(r.t3_eng), pct(r.t3_mand), pct(r.t3_pmt),
               pct(r.t4_eng), pct(r.t4_mand), pct(r.t4_pmt)],
              alt1 if idx % 2 == 0 else alt2, False, brd, ctr, lft)
    for i, w in enumerate([8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    _pluri_footer(ws, NC)


# ── Sections XII/XIII : taux physique par entité ──────────────────────────────

def _write_taux_entite_sheet(ws, titre, rows, get_code, get_nom, lbl):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    NC = 7
    thin = Side(style='thin')
    brd  = Border(left=thin, right=thin, top=thin, bottom=thin)
    ctr  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    lft  = Alignment(horizontal='left',   vertical='center', wrap_text=True)
    hdr  = PatternFill('solid', fgColor='BDD7EE')
    alt1 = PatternFill('solid', fgColor='EBF5FB')
    alt2 = PatternFill('solid', fgColor='FFFFFF')
    sr = _pluri_header(ws, titre, NC)
    for col, h in enumerate(
            ['Année', f'Code {lbl}', f'Nom {lbl}', 'T1 (%)', 'T2 (%)', 'T3 (%)', 'T4 (%)'], 1):
        c = ws.cell(row=sr, column=col, value=h)
        c.fill = hdr; c.font = Font(bold=True, size=9); c.alignment = ctr; c.border = brd
    ws.row_dimensions[sr].height = 22; sr += 1
    pct = lambda v: round(v, 2) if v is not None else '—'
    for idx, r in enumerate(rows):
        _wr_p(ws, sr + idx,
              [r.annee, get_code(r), get_nom(r),
               pct(r.t1), pct(r.t2), pct(r.t3), pct(r.t4)],
              alt1 if idx % 2 == 0 else alt2, False, brd, ctr, lft)
    for col_l, w in zip('ABCDEFG', [8, 12, 35, 12, 12, 12, 12]):
        ws.column_dimensions[col_l].width = w
    _pluri_footer(ws, NC)


# ── Route export ──────────────────────────────────────────────────────────────

@pluriannuel_bp.route('/export-excel', methods=['POST'])
@login_required
def export_excel():
    import io as _io
    from openpyxl import Workbook
    from datetime import datetime as _dt

    sections = request.form.getlist('sections')
    if not sections:
        flash('Sélectionnez au moins une section à exporter.', 'warning')
        return redirect(url_for('pluriannuel.index'))

    ORDRE = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII']

    def _make_sheets(wb):
        if 'I' in sections:
            _write_budget_pta_sheet(
                wb.create_sheet('I-Budget PTA'),
                MontantPluriannuelPTA.query.order_by(MontantPluriannuelPTA.annee).all())
        if 'II' in sections:
            _write_budget_pai_sheet(
                wb.create_sheet('II-Budget PAI'),
                MontantPluriannuelPAI.query.order_by(MontantPluriannuelPAI.annee).all())
        if 'III' in sections:
            _write_taux_t4_sheet(
                wb.create_sheet('III-Exec Fin PTA'),
                "III — Taux d'exécution financière PTA",
                TauxExecPTA.query.order_by(TauxExecPTA.annee).all())
        if 'IV' in sections:
            _write_taux_t4_sheet(
                wb.create_sheet('IV-Exec Fin PAI'),
                "IV — Taux d'exécution financière PAI",
                TauxExecPAI.query.order_by(TauxExecPAI.annee).all())
        if 'V' in sections:
            _write_budget_gen_sheet(
                wb.create_sheet('V-Budget Général'),
                BudgetPluriannuel.query.order_by(BudgetPluriannuel.annee).all())
        if 'VI' in sections:
            _write_taux_fin_sheet(
                wb.create_sheet('VI-Fin PTA'),
                'VI — Taux de financement PTA',
                TauxFinPTA.query.order_by(TauxFinPTA.annee).all())
        if 'VII' in sections:
            _write_taux_fin_sheet(
                wb.create_sheet('VII-Fin PAI'),
                'VII — Taux de financement PAI',
                TauxFinPAI.query.order_by(TauxFinPAI.annee).all())
        if 'VIII' in sections:
            _write_taux_t4_sheet(
                wb.create_sheet('VIII-Efficacité PTA'),
                "VIII — Taux d'efficacité PTA",
                TauxEfficacitePTA.query.order_by(TauxEfficacitePTA.annee).all())
        if 'IX' in sections:
            _write_taux_t4_sheet(
                wb.create_sheet('IX-Efficacité PAI'),
                "IX — Taux d'efficacité PAI",
                TauxEfficacitePAI.query.order_by(TauxEfficacitePAI.annee).all())
        if 'X' in sections:
            _write_taux_fin_sheet(
                wb.create_sheet('X-Efficience PTA'),
                "X — Taux d'efficience PTA",
                TauxEfficiencePTA.query.order_by(TauxEfficiencePTA.annee).all())
        if 'XI' in sections:
            _write_taux_fin_sheet(
                wb.create_sheet('XI-Efficience PAI'),
                "XI — Taux d'efficience PAI",
                TauxEfficiencePAI.query.order_by(TauxEfficiencePAI.annee).all())
        if 'XII' in sections:
            _write_taux_entite_sheet(
                wb.create_sheet('XII-Exec Phys Dir'),
                "XII — Taux d'exécution physique par Direction",
                TauxExecDirection.query.order_by(
                    TauxExecDirection.annee, TauxExecDirection.direction_id).all(),
                lambda r: r.direction.code, lambda r: r.direction.nom, 'Direction')
        if 'XIII' in sections:
            _write_taux_entite_sheet(
                wb.create_sheet('XIII-Exec Phys Svc'),
                "XIII — Taux d'exécution physique par Service",
                TauxExecService.query.order_by(
                    TauxExecService.annee, TauxExecService.service_id).all(),
                lambda r: r.service.code, lambda r: r.service.nom, 'Service')

    wb = Workbook()
    wb.remove(wb.active)
    _make_sheets(wb)

    if not wb.worksheets:
        flash('Aucune donnée à exporter.', 'warning')
        return redirect(url_for('pluriannuel.index'))

    output = _io.BytesIO()
    wb.save(output)
    output.seek(0)
    fname = f"Suivi_Pluriannuel_{_dt.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=fname)