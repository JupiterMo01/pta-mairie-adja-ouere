from datetime import datetime, timezone
from functools import wraps
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import db, BudgetPluriannuel, MontantPluriannuelPTA, MontantPluriannuelPAI, \
                   TauxExecPTA, TauxExecPAI
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
    return render_template('pluriannuel/index.html',
                           annees=annees, pta_annees=pta_annees, pai_annees=pai_annees,
                           pta_exec_annees=pta_exec_annees, pai_exec_annees=pai_exec_annees)


# ── Ajouter une année ─────────────────────────────────────────────────────────

@pluriannuel_bp.route('/add', methods=['POST'])
@editeur_only
def add():
    try:
        annee_val = int(request.form.get('annee', 0))
    except (TypeError, ValueError):
        flash("Année invalide.", 'danger')
        return redirect(url_for('pluriannuel.index'))

    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return redirect(url_for('pluriannuel.index'))

    if BudgetPluriannuel.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà.", 'warning')
        return redirect(url_for('pluriannuel.index'))

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
    return redirect(url_for('pluriannuel.index'))


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
    return redirect(url_for('pluriannuel.index'))


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
    return redirect(url_for('pluriannuel.index'))


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
        return redirect(url_for('pluriannuel.index'))
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return redirect(url_for('pluriannuel.index'))
    if MontantPluriannuelPTA.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà dans les montants PTA.", 'warning')
        return redirect(url_for('pluriannuel.index'))
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
    return redirect(url_for('pluriannuel.index'))


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
    return redirect(url_for('pluriannuel.index'))


@pluriannuel_bp.route('/pta/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pta(row_id):
    row = db.get_or_404(MontantPluriannuelPTA, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pta_delete', f"PTA {annee_val} supprimé")
    flash(f"Année {annee_val} (PTA) supprimée.", 'warning')
    return redirect(url_for('pluriannuel.index'))


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
        return redirect(url_for('pluriannuel.index'))
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return redirect(url_for('pluriannuel.index'))
    if MontantPluriannuelPAI.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà dans les montants PAI.", 'warning')
        return redirect(url_for('pluriannuel.index'))
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
    return redirect(url_for('pluriannuel.index'))


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
    return redirect(url_for('pluriannuel.index'))


@pluriannuel_bp.route('/pai/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pai(row_id):
    row = db.get_or_404(MontantPluriannuelPAI, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pai_delete', f"PAI {annee_val} supprimé")
    flash(f"Année {annee_val} (PAI) supprimée.", 'warning')
    return redirect(url_for('pluriannuel.index'))


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
        return redirect(url_for('pluriannuel.index'))
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return redirect(url_for('pluriannuel.index'))
    if TauxExecPTA.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (taux exec PTA).", 'warning')
        return redirect(url_for('pluriannuel.index'))
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    err = _valider_taux(t1, t2, t3, t4)
    if err:
        flash(f"Taux PTA {annee_val} — {err}", 'danger')
        return redirect(url_for('pluriannuel.index'))
    row = TauxExecPTA(annee=annee_val, t1=t1, t2=t2, t3=t3, t4=t4,
                      date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id)
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pta_exec_add', f"Taux exec PTA {annee_val} ajouté")
    flash(f"Taux exécution PTA {annee_val} ajouté.", 'success')
    return redirect(url_for('pluriannuel.index'))


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
        return redirect(url_for('pluriannuel.index'))
    row.t1 = t1; row.t2 = t2; row.t3 = t3; row.t4 = t4
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pta_exec_edit', f"Taux exec PTA {row.annee} modifié")
    flash(f"Taux exécution PTA {row.annee} mis à jour.", 'success')
    return redirect(url_for('pluriannuel.index'))


@pluriannuel_bp.route('/pta-exec/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pta_exec(row_id):
    row = db.get_or_404(TauxExecPTA, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pta_exec_delete', f"Taux exec PTA {annee_val} supprimé")
    flash(f"Taux exécution PTA {annee_val} supprimé.", 'warning')
    return redirect(url_for('pluriannuel.index'))


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
        return redirect(url_for('pluriannuel.index'))
    if annee_val < 2000 or annee_val > 2100:
        flash("Année hors plage (2000–2100).", 'danger')
        return redirect(url_for('pluriannuel.index'))
    if TauxExecPAI.query.filter_by(annee=annee_val).first():
        flash(f"L'année {annee_val} existe déjà (taux exec PAI).", 'warning')
        return redirect(url_for('pluriannuel.index'))
    t1 = _parse_taux(request.form.get('t1'))
    t2 = _parse_taux(request.form.get('t2'))
    t3 = _parse_taux(request.form.get('t3'))
    t4 = _parse_taux(request.form.get('t4'))
    err = _valider_taux(t1, t2, t3, t4)
    if err:
        flash(f"Taux PAI {annee_val} — {err}", 'danger')
        return redirect(url_for('pluriannuel.index'))
    row = TauxExecPAI(annee=annee_val, t1=t1, t2=t2, t3=t3, t4=t4,
                      date_maj=datetime.now(timezone.utc), modified_by_id=current_user.id)
    db.session.add(row)
    db.session.commit()
    log_audit('pluriannuel_pai_exec_add', f"Taux exec PAI {annee_val} ajouté")
    flash(f"Taux exécution PAI {annee_val} ajouté.", 'success')
    return redirect(url_for('pluriannuel.index'))


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
        return redirect(url_for('pluriannuel.index'))
    row.t1 = t1; row.t2 = t2; row.t3 = t3; row.t4 = t4
    row.date_maj = datetime.now(timezone.utc)
    row.modified_by_id = current_user.id
    db.session.commit()
    log_audit('pluriannuel_pai_exec_edit', f"Taux exec PAI {row.annee} modifié")
    flash(f"Taux exécution PAI {row.annee} mis à jour.", 'success')
    return redirect(url_for('pluriannuel.index'))


@pluriannuel_bp.route('/pai-exec/delete/<int:row_id>', methods=['POST'])
@editeur_only
def delete_pai_exec(row_id):
    row = db.get_or_404(TauxExecPAI, row_id)
    annee_val = row.annee
    db.session.delete(row)
    db.session.commit()
    log_audit('pluriannuel_pai_exec_delete', f"Taux exec PAI {annee_val} supprimé")
    flash(f"Taux exécution PAI {annee_val} supprimé.", 'warning')
    return redirect(url_for('pluriannuel.index'))
