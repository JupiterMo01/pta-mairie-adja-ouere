from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from models import db, Tache, SuiviTache, Annee, Programme
from suivi import suivi_bp


def get_annee():
    annee_id = session.get('annee_id')
    if annee_id:
        return Annee.query.get(annee_id)
    return Annee.query.filter_by(actif=True).first()


@suivi_bp.route('/')
@login_required
def index():
    # Les admins sont redirigés vers les rapports
    if current_user.role in ('admin_editeur', 'admin_lecteur'):
        return redirect(url_for('rapports.index'))

    annee = get_annee()
    trimestre = request.args.get('trimestre', 1, type=int)

    service_id = current_user.service_id
    direction_id = current_user.direction_id

    programmes = []
    if annee:
        programmes = Programme.query.filter_by(annee_id=annee.id)\
                                    .order_by(Programme.numero).all()

    taches_data = []
    for prog in programmes:
        for projet in prog.projets:
            for activite in projet.activites:
                for tache in activite.taches:
                    # Les directions voient toutes les tâches de leurs services
                    if current_user.role == 'direction':
                        if not tache.service_responsable:
                            continue
                        if tache.service_responsable.direction_id != direction_id:
                            continue
                    # Les services voient uniquement leurs tâches
                    elif current_user.role == 'service':
                        if tache.service_responsable_id != service_id:
                            continue

                    suivi = SuiviTache.query.filter_by(
                        tache_id=tache.id,
                        trimestre=trimestre,
                        annee_id=annee.id,
                    ).first()
                    taches_data.append({
                        'tache': tache,
                        'suivi': suivi,
                        'activite': activite,
                        'projet': projet,
                        'programme': prog,
                        'peut_modifier': (current_user.role == 'service' and
                                          tache.service_responsable_id == service_id),
                    })

    return render_template('suivi/index.html',
                           taches_data=taches_data, annee=annee,
                           trimestre=trimestre, trimestres=[1, 2, 3, 4])


@suivi_bp.route('/tache/<int:tache_id>/update', methods=['POST'])
@login_required
def update_tache(tache_id):
    if current_user.role != 'service':
        flash('Seuls les services peuvent mettre à jour le suivi.', 'danger')
        return redirect(url_for('suivi.index'))

    tache = Tache.query.get_or_404(tache_id)
    service_id = current_user.service_id

    if tache.service_responsable_id != service_id:
        flash("Cette tâche n'appartient pas à votre service.", 'danger')
        return redirect(url_for('suivi.index'))

    annee = get_annee()
    if not annee:
        flash('Aucune année active.', 'danger')
        return redirect(url_for('suivi.index'))

    trimestre = request.form.get('trimestre', type=int)
    statut = request.form.get('statut', 'non_execute')
    observation = request.form.get('observation', '').strip()

    if statut not in ('execute', 'en_cours', 'non_execute'):
        flash('Statut invalide.', 'danger')
        return redirect(url_for('suivi.index', trimestre=trimestre))

    suivi = SuiviTache.query.filter_by(
        tache_id=tache_id, service_id=service_id,
        trimestre=trimestre, annee_id=annee.id,
    ).first()

    if suivi:
        suivi.statut = statut
        suivi.observation = observation
        suivi.date_maj = datetime.utcnow()
        suivi.modified_by_id = current_user.id
    else:
        suivi = SuiviTache(
            tache_id=tache_id, service_id=service_id,
            trimestre=trimestre, annee_id=annee.id,
            statut=statut, observation=observation,
            modified_by_id=current_user.id,
        )
        db.session.add(suivi)

    db.session.commit()

    # Réponse AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'statut': statut})

    flash('Suivi mis à jour.', 'success')
    return redirect(url_for('suivi.index', trimestre=trimestre))