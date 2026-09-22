from datetime import datetime, timezone
from functools import wraps
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import db, BudgetPluriannuel, MontantPluriannuelPTA, MontantPluriannuelPAI, \
                   TauxExecPTA, TauxExecPAI, TauxFinPTA, TauxFinPAI
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


def _valider_taux(t1, t2, t3, t4):
    """Vérifie la non-décroissance T1→T4 (ignore les None).
    Retourne un message d'erreur ou None si OK."""
    vals = [(i+1, v) for i, v in enumerate([t1, t2, t3, t4]) if v is not None]
    for idx in range(len(vals) - 1):
        num_a, va = vals[idx]
        num_b, vb = vals[idx + 1]
        if vb < va:
            return (f"T{num_b} ({vb:.2f} %) ne peut pas être inférieur à "
                    f"T{num_a} ({va:.2f} %) — le taux d'exécution est cumulatif.")
    return None


@pluriannuel_bp.route('/')
@login_required
def index():
    annees          = BudgetPluriannuel.query.order_by(BudgetPluriannuel.annee).all()
    pta_annees      = MontantPluriannuelPTA.query.order_by(MontantPluriannuelPTA.annee).all()
    pai_annees      = MontantPluriannuelPAI.query.order_by(MontantPluriannuelPAI.annee).all()
    pta_exec_annees = TauxExecPTA.query.order_by(TauxExecPTA.annee).all()
    pai_exec_annees = TauxExecPAI.query.order_by(TauxExecPAI.annee).all()
    pta_fin_annees  = TauxFinPTA.query.order_by(TauxFinPTA.annee).all()
    pai_fin_annees  = TauxFinPAI.query.order_by(TauxFinPAI.annee).all()
    return render_template('pluriannuel/index.html',
                           annees=annees, pta_annees=pta_annees, pai_annees=pai_annees,
                           pta_exec_annees=pta_exec_annees, pai_exec_annees=pai_exec_annees,
                           pta_fin_annees=pta_fin_annees, pai_fin_annees=pai_fin_annees)


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
    err = _valider_taux(t1, t2, t3, t4)
    if err:
        flash(f"Taux PTA {annee_val} — {err}", 'danger')
        return _redir('#section-pta-exec')
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
    err = _valider_taux(t1, t2, t3, t4)
    if err:
        flash(f"Taux PTA {row.annee} — {err}", 'danger')
        return _redir('#section-pta-exec')
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
    err = _valider_taux(t1, t2, t3, t4)
    if err:
        flash(f"Taux PAI {annee_val} — {err}", 'danger')
        return _redir('#section-pai-exec')
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
    err = _valider_taux(t1, t2, t3, t4)
    if err:
        flash(f"Taux PAI {row.annee} — {err}", 'danger')
        return _redir('#section-pai-exec')
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