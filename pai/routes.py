from flask import render_template, abort
from flask_login import login_required
from models import db, Annee, PaiProgramme
from pai import pai_bp
from utils import get_annee


@pai_bp.route('/')
@login_required
def index():
    """Affiche le PAI au nouveau format (vue écran + impression)."""
    annee = get_annee()
    if not annee:
        abort(404)

    programmes = (
        PaiProgramme.query
        .filter_by(annee_id=annee.id)
        .order_by(PaiProgramme.numero)
        .all()
    )

    # Totaux globaux
    total_fp      = sum(a.fp           for pg in programmes for pj in pg.projets for a in pj.activites)
    total_fadec   = sum(a.montant_fadec for pg in programmes for pj in pg.projets for a in pj.activites)
    total_ptfs    = sum(a.autres_ptfs   for pg in programmes for pj in pg.projets for a in pj.activites)
    total_global  = sum(a.cout_total    for pg in programmes for pj in pg.projets for a in pj.activites)

    return render_template(
        'pai/index.html',
        annee=annee,
        programmes=programmes,
        total_fp=total_fp,
        total_fadec=total_fadec,
        total_ptfs=total_ptfs,
        total_global=total_global,
    )
