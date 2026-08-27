from models import SuiviTache, Programme


# ── Constantes partagées ──────────────────────────────────────────────────────

MOIS_COURT = {
    'Janvier': 'Janv', 'Février': 'Fév', 'Mars': 'Mars', 'Avril': 'Avr',
    'Mai': 'Mai', 'Juin': 'Juin', 'Juillet': 'Juil', 'Août': 'Août',
    'Septembre': 'Sept', 'Octobre': 'Oct', 'Novembre': 'Nov', 'Décembre': 'Déc',
}

MOIS_ORDRE = {
    'Janvier': 1, 'Février': 2, 'Mars': 3,
    'Avril': 4,   'Mai': 5,    'Juin': 6,
    'Juillet': 7, 'Août': 8,   'Septembre': 9,
    'Octobre': 10, 'Novembre': 11, 'Décembre': 12,
}

TRIMESTRE_RANGE = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}


def get_annee():
    """Retourne l'année PTA sélectionnée en session, ou l'année active par défaut."""
    from flask import session
    from models import Annee
    annee_id = session.get('annee_id')
    if annee_id:
        return Annee.query.get(annee_id)
    return Annee.query.filter_by(actif=True).first()


def log_audit(action, details=None):
    """Enregistre une entrée dans le journal d'audit.
    Ne lève jamais d'exception — un échec de log ne doit pas bloquer l'app."""
    from models import AuditLog, db
    from flask import request
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            user_id   = current_user.id
            user_nom  = f"{current_user.prenom} {current_user.nom}"
            user_role = current_user.role
        else:
            user_id, user_nom, user_role = None, 'Anonyme', None
    except Exception:
        user_id, user_nom, user_role = None, 'Système', None
    try:
        ip = request.remote_addr
    except Exception:
        ip = None
    try:
        entry = AuditLog(
            user_id=user_id, user_nom=user_nom, user_role=user_role,
            action=action, details=details, ip=ip
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def get_suivi(tache_id, trimestre, annee_id, service_id=None):
    q = SuiviTache.query.filter_by(
        tache_id=tache_id, trimestre=trimestre, annee_id=annee_id
    )
    if service_id:
        q = q.filter_by(service_id=service_id)
    return q.first()


def taux_tache(tache, trimestre, annee_id):
    """Taux d'une tâche : 100% si exécutée, taux_execution si en cours, 0% sinon."""
    suivi = SuiviTache.query.filter_by(
        tache_id=tache.id, trimestre=trimestre, annee_id=annee_id
    ).first()
    if not suivi:
        return 0.0
    if suivi.statut == 'execute':
        return 100.0
    if suivi.statut == 'en_cours':
        return float(suivi.taux_execution or 0)
    return 0.0


def _filtrer_taches(activite, service_id=None, direction_id=None):
    """Retourne les tâches filtrées selon le service ou la direction."""
    taches = []
    for t in activite.taches:
        if service_id:
            if t.service_responsable_id != service_id:
                continue
        elif direction_id:
            if not t.service_responsable or t.service_responsable.direction_id != direction_id:
                continue
        taches.append(t)
    return taches


def taux_activite(activite, trimestre, annee_id, service_id=None, direction_id=None):
    """Moyenne pondérée des tâches (renormalisée si filtrage)."""
    taches = _filtrer_taches(activite, service_id, direction_id)
    if not taches:
        return None
    poids_total = sum(t.poids for t in taches)
    if poids_total == 0:
        return 0.0
    total = sum(t.poids * taux_tache(t, trimestre, annee_id) for t in taches)
    return round(total / poids_total, 2)


def taux_projet(projet, trimestre, annee_id, service_id=None, direction_id=None):
    """Moyenne pondérée des activités (renormalisée si filtrage)."""
    items = []
    for a in projet.activites:
        t = taux_activite(a, trimestre, annee_id, service_id, direction_id)
        if t is not None:
            items.append((a.poids, t))
    if not items:
        return None
    poids_total = sum(p for p, _ in items)
    if poids_total == 0:
        return 0.0
    return round(sum(p * t for p, t in items) / poids_total, 2)


def taux_programme(programme, trimestre, annee_id, service_id=None, direction_id=None):
    """Moyenne pondérée des projets."""
    items = []
    for p in programme.projets:
        t = taux_projet(p, trimestre, annee_id, service_id, direction_id)
        if t is not None:
            items.append((p.poids, t))
    if not items:
        return None
    poids_total = sum(p for p, _ in items)
    if poids_total == 0:
        return 0.0
    return round(sum(p * t for p, t in items) / poids_total, 2)


def taux_global(programmes, trimestre, annee_id, service_id=None, direction_id=None):
    """Moyenne pondérée des programmes."""
    items = []
    for prog in programmes:
        t = taux_programme(prog, trimestre, annee_id, service_id, direction_id)
        if t is not None:
            items.append((prog.poids, t))
    if not items:
        return None
    poids_total = sum(p for p, _ in items)
    if poids_total == 0:
        return 0.0
    return round(sum(p * t for p, t in items) / poids_total, 2)


def rapport_trimestriel(annee, trimestre, service_id=None, direction_id=None):
    """Construit la structure de données complète pour un rapport trimestriel."""
    programmes = Programme.query.filter_by(annee_id=annee.id).order_by(Programme.numero).all()
    data = []

    for prog in programmes:
        prog_data = {
            'programme': prog,
            'taux': taux_programme(prog, trimestre, annee.id, service_id, direction_id),
            'projets': []
        }
        for projet in prog.projets:
            proj_data = {
                'projet': projet,
                'taux': taux_projet(projet, trimestre, annee.id, service_id, direction_id),
                'activites': []
            }
            for activite in projet.activites:
                taches_filtrees = _filtrer_taches(activite, service_id, direction_id)
                if not taches_filtrees and (service_id or direction_id):
                    continue
                act_data = {
                    'activite': activite,
                    'taux': taux_activite(activite, trimestre, annee.id, service_id, direction_id),
                    'taches': []
                }
                for tache in (taches_filtrees if (service_id or direction_id) else activite.taches):
                    suivi = SuiviTache.query.filter_by(
                        tache_id=tache.id, trimestre=trimestre, annee_id=annee.id
                    ).first()
                    act_data['taches'].append({
                        'tache': tache,
                        'suivi': suivi,
                        'taux': taux_tache(tache, trimestre, annee.id)
                    })
                proj_data['activites'].append(act_data)
            if proj_data['activites']:
                prog_data['projets'].append(proj_data)
        if prog_data['projets']:
            data.append(prog_data)

    global_t = taux_global(programmes, trimestre, annee.id, service_id, direction_id)
    return data, global_t