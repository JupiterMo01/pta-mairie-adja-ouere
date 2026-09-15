from flask import render_template, abort, request, jsonify
from flask_login import login_required, current_user
from models import db, Programme, Activite, PaiActivite
from pai import pai_bp
from utils import get_annee


@pai_bp.route('/')
@login_required
def index():
    """Affiche le PAI au nouveau format (vue écran + impression). Admins seulement."""
    if current_user.role not in ('admin_editeur', 'admin_lecteur'):
        abort(403)
    annee = get_annee()
    if not annee:
        abort(404)

    programmes = (
        Programme.query
        .filter_by(annee_id=annee.id)
        .order_by(Programme.numero)
        .all()
    )

    # Construire la structure PAI : seulement les activités d'investissement
    pai_data = []
    total_fp = total_fadec = total_ptfs = total_global = 0.0

    for pg in programmes:
        pg_projets = []
        for pj in pg.projets:
            inv_acts = [a for a in pj.activites
                       if a.type_activite and 'investissement' in a.type_activite.lower()]
            if inv_acts:
                pg_projets.append({'projet': pj, 'activites': inv_acts})
                for a in inv_acts:
                    total_fp     += a.src_rp
                    total_fadec  += a.src_fa + a.src_fn
                    total_ptfs   += a.src_ap + a.src_af
                    total_global += a.budget_total
        if pg_projets:
            pai_data.append({'programme': pg, 'projets': pg_projets})

    # Divisé par 1000 pour l'affichage en milliers de F CFA
    return render_template(
        'pai/index.html',
        annee=annee,
        pai_data=pai_data,
        total_fp=total_fp / 1000,
        total_fadec=total_fadec / 1000,
        total_ptfs=total_ptfs / 1000,
        total_global=total_global / 1000,
        can_edit=(current_user.role == 'admin_editeur'),
    )


@pai_bp.route('/edit/<int:activite_id>', methods=['POST'])
@login_required
def edit(activite_id):
    """Sauvegarde les champs PAI-spécifiques d'une activité (admin éditeur uniquement)."""
    if current_user.role != 'admin_editeur':
        abort(403)

    activite = db.session.get(Activite, activite_id)
    if not activite:
        abort(404)

    extra = PaiActivite.query.filter_by(activite_id=activite_id).first()
    if not extra:
        extra = PaiActivite(activite_id=activite_id)
        db.session.add(extra)

    extra.localisation     = request.form.get('localisation', '').strip() or None
    extra.poids_pai        = float(request.form.get('poids_pai', 0) or 0)
    extra.indicateurs      = request.form.get('indicateurs', '').strip() or None
    extra.fadec_type       = request.form.get('fadec_type', '').strip() or None
    extra.observations_pai = request.form.get('observations_pai', '').strip() or None

    db.session.commit()
    return jsonify({'ok': True})
