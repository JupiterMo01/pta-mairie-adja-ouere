# (pas d'import top-level de models — chaque fonction importe ce dont elle a besoin)


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


def requete_pta(annee_id):
    """Requête des programmes d'une année avec toute la hiérarchie préchargée
    (projets, activités, tâches et leurs liens) en une dizaine de requêtes groupées.
    Sans cela, chaque accès à .projets / .activites / .taches déclenchait sa propre
    requête (plusieurs milliers par page). À compléter par .order_by(...).all()."""
    from sqlalchemy.orm import selectinload
    from models import Programme, Projet, Activite, Tache

    # Les listes associées (services, directions, structures) gardent volontairement leur
    # chargement d'origine : un chargement groupé les renverrait dans un autre ordre.
    def activites():
        return selectinload(Programme.projets).selectinload(Projet.activites)

    return Programme.query.filter_by(annee_id=annee_id).options(
        selectinload(Programme.pai_extra_prog),
        selectinload(Programme.projets).selectinload(Projet.pai_extra_proj),
        activites().selectinload(Activite.pai_extra),
        activites().selectinload(Activite.pei_extra),
        activites().selectinload(Activite.taches),
    )


def programmes_pta(annee_id):
    """Programmes d'une année (ordre des numéros), hiérarchie préchargée.
    Chargés une seule fois par page affichée : les calculs par direction et par service
    (tableau de bord, exports multi-feuilles…) réutilisent le même chargement.
    Le réemploi est annulé à chaque enregistrement en base (voir _vider_cache_pta)."""
    from flask import g, has_request_context
    from models import Programme
    if not has_request_context():
        return requete_pta(annee_id).order_by(Programme.numero).all()
    cache = g.setdefault('_cache_pta', {})
    if annee_id not in cache:
        cache[annee_id] = requete_pta(annee_id).order_by(Programme.numero).all()
    return list(cache[annee_id])


def _vider_cache_pta(*_args):
    from flask import g, has_app_context
    if has_app_context():
        g.pop('_cache_pta', None)


def _brancher_cache_pta():
    """Vide le cache du PTA après chaque validation ou annulation de transaction."""
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    if not event.contains(Session, 'after_commit', _vider_cache_pta):
        event.listen(Session, 'after_commit', _vider_cache_pta)
        event.listen(Session, 'after_rollback', _vider_cache_pta)


_brancher_cache_pta()


def _renorm(items, src='original_poids', dst='new_poids'):
    """Recalcule les poids pour que leur somme soit exactement 100.
    Le dernier élément absorbe les micro-erreurs d'arrondi.
    Source unique partagée par dirpta, svcpta et suivi (évite la duplication).
    """
    if not items:
        return
    total = sum(i[src] for i in items)
    if total == 0:
        eq = round(100 / len(items), 2)
        for i in items:
            i[dst] = eq
        return
    running = 0.0
    for idx, i in enumerate(items):
        if idx == len(items) - 1:
            i[dst] = round(100.0 - running, 2)
        else:
            p = round(i[src] / total * 100, 2)
            i[dst] = p
            running += p


def valider_mdp(mdp):
    """Valide la robustesse d'un mot de passe.
    Retourne None si le mot de passe est valide, sinon un message d'erreur (str).
    Règles : 10 caractères minimum, au moins 1 chiffre, 1 majuscule, 1 caractère spécial.
    """
    _SPECIAUX = set('!@#$%^&*()_+-=[]{}|;:\'",.<>?/`~\\')
    if len(mdp) < 10:
        return 'Le mot de passe doit contenir au moins 10 caractères.'
    if not any(c.isdigit() for c in mdp):
        return 'Le mot de passe doit contenir au moins un chiffre (0-9).'
    if not any(c.isupper() for c in mdp):
        return 'Le mot de passe doit contenir au moins une lettre majuscule.'
    if not any(c in _SPECIAUX for c in mdp):
        return 'Le mot de passe doit contenir au moins un caractère spécial (!@#$%^&*…).'
    return None   # valide


def get_annee():
    """Retourne l'année PTA sélectionnée en session, ou l'année active par défaut."""
    from flask import session
    from models import Annee, db
    annee_id = session.get('annee_id')
    if annee_id:
        return db.session.get(Annee, annee_id)
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


# ── Fonctions taux_* et rapport_trimestriel supprimées ───────────────────────
# Ces fonctions (get_suivi, _filtrer_taches, taux_tache, taux_activite,
# taux_projet, taux_programme, taux_global, rapport_trimestriel) n'étaient
# importées dans aucun module. Chaque blueprint (suivi, dirpta, svcpta, dashboard)
# implémente ses propres calculs. Supprimées lors du nettoyage maintenance 2026-08.
# L'historique git conserve la version complète si besoin (commit avant maintenance).