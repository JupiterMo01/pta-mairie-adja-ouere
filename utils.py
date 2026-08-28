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


def _renorm(items, src='original_poids', dst='new_poids'):
    """Recalcule les poids pour que leur somme soit exactement 100.
    Le dernier élément absorbe les micro-erreurs d'arrondi.
    Source unique partagée par dirpta, svcpta et suivi (évite la duplication).
    """
    if not items:
        return
    total = sum(i[src] for i in items)
    if total == 0:
        eq = round(100 / len(items), 4)
        for i in items:
            i[dst] = eq
        return
    running = 0.0
    for idx, i in enumerate(items):
        if idx == len(items) - 1:
            i[dst] = round(100.0 - running, 4)
        else:
            p = round(i[src] / total * 100, 4)
            i[dst] = p
            running += p


def valider_mdp(mdp):
    """Valide la robustesse d'un mot de passe.
    Retourne None si le mot de passe est valide, sinon un message d'erreur (str).
    Règles : 8 caractères minimum, au moins 1 chiffre, au moins 1 majuscule.
    """
    if len(mdp) < 8:
        return 'Le mot de passe doit contenir au moins 8 caractères.'
    if not any(c.isdigit() for c in mdp):
        return 'Le mot de passe doit contenir au moins un chiffre (0-9).'
    if not any(c.isupper() for c in mdp):
        return 'Le mot de passe doit contenir au moins une lettre majuscule.'
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