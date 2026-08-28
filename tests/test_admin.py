"""
tests/test_admin.py — Tests des fonctions d'administration.

Couvre :
- Purge du suivi : supprime tous les SuiviTache de l'année active
- Purge réservée à admin_editeur (admin_lecteur et service refusés)
- Page /admin/ visible par admin_editeur avec les compteurs
- Présence/absence du bouton Purger selon le rôle
"""
import pytest
from conftest import post_csrf
from models import SuiviTache, Tache, Annee, Service


# ──────────────────────────────────────────────────────────────────────────────
# Purge du suivi
# ──────────────────────────────────────────────────────────────────────────────

class TestPurgeSuivi:

    def _creer_suivis(self, app):
        """Crée 3 SuiviTache pour la tâche de test, retourne leur nombre."""
        with app.app_context():
            from models import db
            annee = Annee.query.filter_by(actif=True).first()
            tache = Tache.query.first()
            svc   = Service.query.filter_by(code='SRH').first()

            # Nettoyage préalable (cas où le test précédent n'a pas nettoyé)
            SuiviTache.query.filter_by(annee_id=annee.id).delete()
            db.session.flush()

            for t in (1, 2, 3):
                s = SuiviTache(
                    tache_id=tache.id, service_id=svc.id,
                    trimestre=t, annee_id=annee.id, statut='execute',
                )
                db.session.add(s)
            db.session.commit()

            return SuiviTache.query.filter_by(annee_id=annee.id).count()

    def _compter(self, app):
        """Compte les SuiviTache de l'année active."""
        with app.app_context():
            annee = Annee.query.filter_by(actif=True).first()
            return SuiviTache.query.filter_by(annee_id=annee.id).count()

    # ── Test principal ───────────────────────────────────────────────────────

    def test_purge_supprime_tous_les_suivis(self, app, client_admin):
        """
        Scénario complet :
        1. Crée des SuiviTache
        2. POST /admin/purge-suivi avec CSRF
        3. Vérifie que tous les enregistrements sont supprimés
        """
        nb_avant = self._creer_suivis(app)
        assert nb_avant > 0, "Des SuiviTache doivent exister avant la purge"

        r = post_csrf(client_admin, '/admin/purge-suivi', follow_redirects=True)
        assert r.status_code == 200, f"La purge doit réussir (obtenu {r.status_code})"

        nb_apres = self._compter(app)
        assert nb_apres == 0, (
            f"Après purge, il ne doit rester aucun suivi (trouvé : {nb_apres})"
        )

    # ── Contrôle d'accès ─────────────────────────────────────────────────────

    def test_purge_refusee_admin_lecteur(self, app, client_lecteur):
        """
        admin_lecteur ne peut pas purger (@editeur_required → redirect).
        """
        r = post_csrf(client_lecteur, '/admin/purge-suivi', follow_redirects=False)
        # @editeur_required redirige vers pta.global_pta quand le rôle est insuffisant
        assert r.status_code in (301, 302, 303), (
            f"admin_lecteur ne doit pas pouvoir purger le suivi (obtenu {r.status_code})"
        )

    def test_purge_refusee_service(self, app, client_service):
        """Un utilisateur 'service' ne peut pas déclencher la purge."""
        r = post_csrf(client_service, '/admin/purge-suivi', follow_redirects=False)
        assert r.status_code in (301, 302, 303), (
            f"Un utilisateur 'service' ne doit pas pouvoir purger (obtenu {r.status_code})"
        )

    def test_purge_refusee_non_connecte(self, app, client):
        """Un visiteur non connecté est redirigé vers login."""
        r = post_csrf(client, '/admin/purge-suivi', follow_redirects=False)
        assert r.status_code in (301, 302, 303)
        location = r.headers.get('Location', '')
        assert 'login' in location.lower(), (
            f"Non connecté doit être redirigé vers /login (obtenu Location: {location})"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Page d'accueil /admin/
# ──────────────────────────────────────────────────────────────────────────────

class TestAdminIndex:

    def test_page_admin_accessible_admin_editeur(self, client_admin):
        """admin_editeur voit la page d'administration (200)."""
        r = client_admin.get('/admin/')
        assert r.status_code == 200

    def test_page_admin_contient_stats(self, client_admin):
        """La page /admin/ affiche des compteurs (utilisateurs, directions…)."""
        r = client_admin.get('/admin/')
        contenu = r.data.decode('utf-8', errors='replace')
        assert 'Utilisateurs' in contenu
        assert 'Directions'   in contenu
        assert 'Services'     in contenu

    def test_page_admin_contient_bouton_purge(self, client_admin):
        """Le bouton Purger le suivi est visible pour admin_editeur."""
        r = client_admin.get('/admin/')
        contenu = r.data.decode('utf-8', errors='replace')
        assert 'purge-suivi' in contenu or 'urger' in contenu, (
            "Le bouton de purge doit être visible pour admin_editeur"
        )

    def test_page_admin_refusee_service(self, client_service):
        """Un utilisateur 'service' est redirigé depuis /admin/."""
        r = client_service.get('/admin/', follow_redirects=False)
        assert r.status_code in (301, 302, 303)
