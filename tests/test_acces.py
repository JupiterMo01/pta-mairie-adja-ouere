"""
tests/test_acces.py — Tests de contrôle d'accès par rôle + protection IDOR.

Couvre :
- admin_editeur peut accéder à /admin/ (route avec @admin_required)
- admin_lecteur et direction/service NE peuvent PAS accéder à /admin/
- Un service peut voir son propre PTA (/svcpta/<id>/print)
- Un service NE peut PAS voir le PTA d'un autre service (abort 403)
- Une direction peut voir son PTA (/dirpta/<id>/print)
- Une direction NE peut PAS voir le PTA d'une autre direction (abort 403)
- Un service NE peut PAS voir le PTA d'une direction différente (/dirpta/<id>/excel)

NOTE architecture :
  @admin_required  → réservé à admin_editeur UNIQUEMENT
  @editeur_required → idem
  Les admin_lecteur n'ont pas accès à /admin/ mais peuvent voir les PTA et dashboard.
"""
import pytest
from models import Direction, Service


# ──────────────────────────────────────────────────────────────────────────────
# Accès à /admin/
# ──────────────────────────────────────────────────────────────────────────────

class TestAccesAdmin:

    def test_admin_editeur_peut_acceder(self, client_admin):
        """admin_editeur → /admin/ = 200 (seul rôle autorisé par @admin_required)."""
        r = client_admin.get('/admin/')
        assert r.status_code == 200, "admin_editeur doit accéder à /admin/"

    def test_admin_lecteur_redirige_de_admin(self, client_lecteur):
        """
        admin_lecteur → /admin/ est redirigé (pas 200).
        @admin_required n'autorise que admin_editeur.
        """
        r = client_lecteur.get('/admin/', follow_redirects=False)
        assert r.status_code in (301, 302, 303), (
            "admin_lecteur ne doit pas accéder à /admin/ (réservé admin_editeur)"
        )

    def test_direction_ne_peut_pas_acceder(self, client_direction):
        """Utilisateur direction → /admin/ redirigé (pas 200)."""
        r = client_direction.get('/admin/', follow_redirects=False)
        assert r.status_code in (301, 302, 303), (
            "Un utilisateur 'direction' ne doit pas accéder à /admin/"
        )

    def test_service_ne_peut_pas_acceder(self, client_service):
        """Utilisateur service → /admin/ redirigé (pas 200)."""
        r = client_service.get('/admin/', follow_redirects=False)
        assert r.status_code in (301, 302, 303), (
            "Un utilisateur 'service' ne doit pas accéder à /admin/"
        )

    def test_non_connecte_redirige_vers_login(self, client):
        """Non connecté → /admin/ redirige vers /login."""
        r = client.get('/admin/', follow_redirects=False)
        assert r.status_code in (301, 302, 303)
        # La redirection doit pointer vers la page de login
        location = r.headers.get('Location', '')
        assert 'login' in location.lower(), (
            f"La redirection doit aller vers /login, obtenu : {location}"
        )

    def test_admin_lecteur_peut_acceder_dashboard(self, client_lecteur):
        """admin_lecteur peut accéder au tableau de bord général."""
        r = client_lecteur.get('/dashboard/', follow_redirects=True)
        assert r.status_code == 200, (
            "admin_lecteur doit pouvoir consulter le tableau de bord"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Protection IDOR sur /svcpta/<service_id>/print et /excel
# ──────────────────────────────────────────────────────────────────────────────

class TestIDORSvcPTA:

    def _ids(self, app):
        """Récupère les IDs des services SRH et STC depuis la DB de test."""
        with app.app_context():
            srh = Service.query.filter_by(code='SRH').first()
            stc = Service.query.filter_by(code='STC').first()
        return srh.id, stc.id

    def test_service_peut_voir_son_propre_print(self, app, client_service):
        """svc_srh peut afficher /svcpta/<srh_id>/print → 200."""
        srh_id, _ = self._ids(app)
        r = client_service.get(f'/svcpta/{srh_id}/print')
        assert r.status_code == 200, (
            f"svc_srh doit pouvoir voir son propre PTA (obtenu {r.status_code})"
        )

    def test_service_bloque_sur_autre_service(self, app, client_service2):
        """svc_stc ne peut PAS afficher /svcpta/<srh_id>/print → 403."""
        srh_id, _ = self._ids(app)
        r = client_service2.get(f'/svcpta/{srh_id}/print')
        assert r.status_code == 403, (
            "IDOR : svc_stc ne doit pas pouvoir voir le PTA de SRH"
        )

    def test_service_peut_voir_son_propre_excel(self, app, client_service):
        """svc_srh peut télécharger /svcpta/<srh_id>/excel → 200."""
        srh_id, _ = self._ids(app)
        r = client_service.get(f'/svcpta/{srh_id}/excel')
        assert r.status_code == 200, (
            f"svc_srh doit pouvoir exporter son propre PTA Excel (obtenu {r.status_code})"
        )

    def test_service_bloque_excel_autre_service(self, app, client_service2):
        """svc_stc ne peut PAS exporter /svcpta/<srh_id>/excel → 403."""
        srh_id, _ = self._ids(app)
        r = client_service2.get(f'/svcpta/{srh_id}/excel')
        assert r.status_code == 403, (
            "IDOR : svc_stc ne doit pas pouvoir exporter le PTA Excel de SRH"
        )

    def test_admin_peut_voir_tout_service(self, app, client_admin):
        """admin_editeur peut voir le PTA de n'importe quel service."""
        srh_id, stc_id = self._ids(app)
        for sid in (srh_id, stc_id):
            r = client_admin.get(f'/svcpta/{sid}/print')
            assert r.status_code == 200, (
                f"admin_editeur doit pouvoir voir /svcpta/{sid}/print"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Protection IDOR sur /dirpta/<direction_id>/print et /excel
# ──────────────────────────────────────────────────────────────────────────────

class TestIDORDirPTA:

    def _ids(self, app):
        """Récupère les IDs des directions DAF et DTC depuis la DB de test."""
        with app.app_context():
            daf = Direction.query.filter_by(code='DAF').first()
            dtc = Direction.query.filter_by(code='DTC').first()
        return daf.id, dtc.id

    def test_direction_peut_voir_sa_direction(self, app, client_direction):
        """dir_daf peut afficher /dirpta/<daf_id>/print → 200."""
        daf_id, _ = self._ids(app)
        r = client_direction.get(f'/dirpta/{daf_id}/print')
        assert r.status_code == 200, (
            f"dir_daf doit voir son propre PTA direction (obtenu {r.status_code})"
        )

    def test_direction_bloquee_sur_autre_direction(self, app, client_direction):
        """dir_daf ne peut PAS voir /dirpta/<dtc_id>/print → 403."""
        _, dtc_id = self._ids(app)
        r = client_direction.get(f'/dirpta/{dtc_id}/print')
        assert r.status_code == 403, (
            "IDOR : dir_daf ne doit pas voir le PTA de DTC"
        )

    def test_service_bloque_direction_differente(self, app, client_service2):
        """svc_stc (DTC) ne peut PAS voir /dirpta/<daf_id>/excel → 403."""
        daf_id, _ = self._ids(app)
        r = client_service2.get(f'/dirpta/{daf_id}/excel')
        assert r.status_code == 403, (
            "IDOR : svc_stc ne doit pas exporter le PTA de DAF"
        )

    def test_admin_peut_voir_toute_direction(self, app, client_admin):
        """admin_editeur peut voir le PTA de n'importe quelle direction."""
        daf_id, dtc_id = self._ids(app)
        for did in (daf_id, dtc_id):
            r = client_admin.get(f'/dirpta/{did}/print')
            assert r.status_code == 200, (
                f"admin_editeur doit pouvoir voir /dirpta/{did}/print"
            )
