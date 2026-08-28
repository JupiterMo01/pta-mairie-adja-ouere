"""
tests/test_modeles.py — Tests unitaires sur les modèles SQLAlchemy.

Couvre :
- SuiviTache.taux : propriété calculée selon le statut
- User.check_password : vérification du hash de mot de passe
- User.nom_complet : propriété de présentation
- Annee.actif : une seule année active à la fois (convention métier)
- Tache.services_concernes : many-to-many correctement initialisé
"""
import pytest
from models import (
    SuiviTache, User, Tache, Annee, Service,
    db,
)
from werkzeug.security import generate_password_hash


class TestSuiviTacheTaux:
    """Tests de la propriété SuiviTache.taux."""

    def _suivi(self, app, statut, taux_execution=None):
        """Crée un SuiviTache en mémoire (sans le sauvegarder en DB)."""
        with app.app_context():
            tache = Tache.query.first()
            annee = Annee.query.filter_by(actif=True).first()
            svc   = Service.query.filter_by(code='SRH').first()
            s = SuiviTache(
                tache_id=tache.id,
                service_id=svc.id,
                trimestre=4,
                annee_id=annee.id,
                statut=statut,
                taux_execution=taux_execution,
            )
            # On retourne les valeurs, pas l'objet (hors contexte)
            taux = s.taux
        return taux

    def test_taux_execute_vaut_100(self, app):
        """statut='execute' → taux = 100.0 (tâche terminée)."""
        assert self._suivi(app, 'execute') == 100.0

    def test_taux_non_execute_vaut_0(self, app):
        """statut='non_execute' → taux = 0.0 (rien fait)."""
        assert self._suivi(app, 'non_execute') == 0.0

    def test_taux_en_cours_utilise_taux_execution(self, app):
        """statut='en_cours', taux_execution=65 → taux = 65.0."""
        assert self._suivi(app, 'en_cours', taux_execution=65.0) == 65.0

    def test_taux_en_cours_sans_valeur_vaut_0(self, app):
        """statut='en_cours', taux_execution=None → taux = 0.0 (pas de saisie)."""
        assert self._suivi(app, 'en_cours', taux_execution=None) == 0.0

    def test_taux_en_cours_avec_valeur_partielle(self, app):
        """statut='en_cours', taux_execution=33.5 → taux = 33.5."""
        assert self._suivi(app, 'en_cours', taux_execution=33.5) == 33.5


class TestUserModele:
    """Tests sur le modèle User."""

    def test_check_password_correct(self, app):
        """check_password retourne True avec le bon mot de passe."""
        with app.app_context():
            u = User.query.filter_by(login='admin_ed').first()
            assert u is not None, "admin_ed doit exister dans la DB de test"
            assert u.check_password('admin2026') is True

    def test_check_password_incorrect(self, app):
        """check_password retourne False avec un mauvais mot de passe."""
        with app.app_context():
            u = User.query.filter_by(login='admin_ed').first()
            assert u.check_password('mauvais_mdp') is False

    def test_nom_complet(self, app):
        """nom_complet = '{prenom} {nom}'."""
        with app.app_context():
            u = User.query.filter_by(login='admin_ed').first()
            assert u.nom_complet == f"{u.prenom} {u.nom}"

    def test_role_label(self, app):
        """role_label retourne un libellé lisible pour chaque rôle."""
        with app.app_context():
            roles_attendus = {
                'admin_ed':  'Admin Éditeur',
                'admin_lec': 'Admin Lecteur',
                'dir_daf':   'Direction',
                'svc_srh':   'Service',
            }
            for login, label_attendu in roles_attendus.items():
                u = User.query.filter_by(login=login).first()
                assert u is not None, f"L'utilisateur '{login}' doit exister"
                assert u.role_label == label_attendu, (
                    f"role_label de '{login}' devrait être '{label_attendu}'"
                )

    def test_compte_inactif_existe(self, app):
        """Le compte 'inactif' existe et a actif=False."""
        with app.app_context():
            u = User.query.filter_by(login='inactif').first()
            assert u is not None
            assert u.actif is False


class TestAnneeModele:
    """Tests sur le modèle Annee."""

    def test_une_annee_active_existe(self, app):
        """La base de test a exactement une année active."""
        with app.app_context():
            nb = Annee.query.filter_by(actif=True).count()
            assert nb == 1, f"Exactement 1 année active attendue (trouvé : {nb})"

    def test_annee_2026_est_active(self, app):
        """L'année PTA 2026 est active dans la DB de test."""
        with app.app_context():
            a = Annee.query.filter_by(annee=2026).first()
            assert a is not None, "L'année 2026 doit exister"
            assert a.actif is True


class TestTacheModele:
    """Tests sur la tâche et ses relations."""

    def test_tache_a_un_service_concerne(self, app):
        """La tâche de test est rattachée au service SRH via services_concernes."""
        with app.app_context():
            t = Tache.query.first()
            assert t is not None, "Une tâche de test doit exister"
            codes = [s.code for s in t.services_concernes]
            assert 'SRH' in codes, (
                f"La tâche doit avoir SRH dans services_concernes (trouvé : {codes})"
            )

    def test_tache_a_un_code_hierarchique(self, app):
        """Tache.code = '{programme}.{projet}.{activite}.{tache}' (ex: 1.1.1.1)."""
        with app.app_context():
            t = Tache.query.first()
            assert '.' in t.code, f"Tache.code doit être hiérarchique, obtenu : '{t.code}'"

    def test_budget_total_tache_nul_sans_financement(self, app):
        """La tâche de test n'a pas de financement → budget_total = 0."""
        with app.app_context():
            t = Tache.query.first()
            assert t.budget_total == 0.0
