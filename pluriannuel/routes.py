from datetime import datetime, timezone
from functools import wraps
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import db, BudgetPluriannuel
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

@pluriannuel_bp.route('/')
@login_required
def index():
    annees = BudgetPluriannuel.query.order_by(BudgetPluriannuel.annee).all()
    return render_template('pluriannuel/index.html', annees=annees)


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
