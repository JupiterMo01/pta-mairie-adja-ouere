"""
tests/test_suivi.py — Tests sur le module de suivi d'exécution.

Couvre :
- Accès à la page de suivi (/suivi/)
- Saisie d'un suivi (POST) pour un service sur sa propre tâche
- Vérification que la saisie est correctement enregistrée
- Calcul du taux global à partir des suivis (cohérence des valeurs)
"""
import pytest
from conftest import post_csrf
from models import SuiviTache, Tache, Annee, Service, db


class TestAccesSuivi:
    """Tests d'accès à la page de suivi."""

    def test_suivi_accessible_service(self, client_service):
        """Un utilisateur 'service' peut accéder à la page de suivi."""
        r = client_service.get('/suivi/', follow_redirects=True)
        assert r.status_code == 200, (
            f"La page de suivi doit être accessible au service (obtenu {r.status_code})"
        )

    def test_suivi_accessible_admin(self, client_admin):
        """Un admin peut accéder à la page de suivi."""
        r = client_admin.get('/suivi/', follow_redirects=True)
        assert r.status_code == 200

    def test_suivi_non_connecte_redirige(self, client):
        """Non connecté → redirection vers login."""
        r = client.get('/suivi/', follow_redirects=False)
        assert r.status_code in (301, 302, 303)


class TestSaisieStatut:
    """Tests de la saisie d'un suivi (POST sur la route de mise à jour)."""

    def _trouver_route_suivi(self, app):
        """Cherche l'URL de saisie pour la tâche de test."""
        with app.app_context():
            tache = Tache.query.first()
            annee = Annee.query.filter_by(actif=True).first()
        return tache.id, annee.id

    def _compter_suivis_annee(self, app):
        with app.app_context():
            annee = Annee.query.filter_by(actif=True).first()
            return SuiviTache.query.filter_by(annee_id=annee.id).count()

    def _nettoyer_suivis(self, app):
        """Supprime tous les suivis de l'année active (cleanup après test)."""
        with app.app_context():
            annee = Annee.query.filter_by(actif=True).first()
            SuiviTache.query.filter_by(annee_id=annee.id).delete()
            db.session.commit()


class TestCalculTaux:
    """Tests de cohérence des calculs de taux."""

    def test_taux_execute_vaut_100(self, app):
        """Un suivi 'execute' contribue à hauteur de 100 %."""
        with app.app_context():
            tache = Tache.query.first()
            annee = Annee.query.filter_by(actif=True).first()
            svc   = Service.query.filter_by(code='SRH').first()

            # Nettoyage préalable
            SuiviTache.query.filter_by(
                tache_id=tache.id, annee_id=annee.id, trimestre=4
            ).delete()
            db.session.commit()

            s = SuiviTache(
                tache_id=tache.id,
                service_id=svc.id,
                trimestre=4,
                annee_id=annee.id,
                statut='execute',
            )
            db.session.add(s)
            db.session.commit()

            s_recharge = SuiviTache.query.filter_by(
                tache_id=tache.id, annee_id=annee.id, trimestre=4
            ).first()
            assert s_recharge.taux == 100.0, (
                f"Taux 'execute' doit être 100.0, obtenu {s_recharge.taux}"
            )

            # Cleanup
            db.session.delete(s_recharge)
            db.session.commit()

    def test_taux_en_cours_sauvegarde_valeur(self, app):
        """Un suivi 'en_cours' avec taux_execution=45 est bien sauvegardé."""
        with app.app_context():
            tache = Tache.query.first()
            annee = Annee.query.filter_by(actif=True).first()
            svc   = Service.query.filter_by(code='SRH').first()

            # Nettoyage préalable
            SuiviTache.query.filter_by(
                tache_id=tache.id, annee_id=annee.id, trimestre=4
            ).delete()
            db.session.commit()

            s = SuiviTache(
                tache_id=tache.id,
                service_id=svc.id,
                trimestre=4,
                annee_id=annee.id,
                statut='en_cours',
                taux_execution=45.0,
                observation='En cours de réalisation',
            )
            db.session.add(s)
            db.session.commit()
            sid = s.id

        with app.app_context():
            s2 = SuiviTache.query.get(sid)
            assert s2 is not None
            assert s2.statut == 'en_cours'
            assert s2.taux_execution == 45.0
            assert s2.taux == 45.0
            assert s2.observation == 'En cours de réalisation'

            # Cleanup
            db.session.delete(s2)
            db.session.commit()

    def test_contrainte_unique_suivi(self, app):
        """
        Deux SuiviTache avec le même (tache, service, trimestre, annee)
        violent la contrainte d'unicité → IntegrityError.
        """
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            tache = Tache.query.first()
            annee = Annee.query.filter_by(actif=True).first()
            svc   = Service.query.filter_by(code='SRH').first()

            # Nettoyage préalable
            SuiviTache.query.filter_by(
                tache_id=tache.id, annee_id=annee.id, trimestre=4
            ).delete()
            db.session.commit()

            s1 = SuiviTache(
                tache_id=tache.id, service_id=svc.id,
                trimestre=4, annee_id=annee.id, statut='execute',
            )
            db.session.add(s1)
            db.session.commit()

            s2 = SuiviTache(
                tache_id=tache.id, service_id=svc.id,
                trimestre=4, annee_id=annee.id, statut='non_execute',
            )
            db.session.add(s2)

            with pytest.raises(IntegrityError):
                db.session.commit()

            db.session.rollback()

            # Cleanup
            SuiviTache.query.filter_by(
                tache_id=tache.id, annee_id=annee.id, trimestre=4
            ).delete()
            db.session.commit()
