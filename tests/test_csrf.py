"""
tests/test_csrf.py — Tests de protection CSRF.

Vérifie que :
- Un POST vers une route protégée SANS token CSRF → 403
- Un POST vers une route protégée AVEC le bon token CSRF → pas 403
- La route /login est exclue de la vérification CSRF (blueprint 'auth')
- Le token CSRF via en-tête X-CSRF-Token est accepté (pour les appels AJAX)
"""
import pytest
from conftest import csrf_token, post_csrf, initialiser_csrf


class TestProtectionCSRF:

    def test_post_sans_csrf_vers_admin_bloque(self, client_admin):
        """
        POST vers /admin/backup-now SANS token CSRF → 403.
        (La vérification CSRF bloque avant même la logique de la route.)
        """
        r = client_admin.post('/admin/backup-now', data={})
        assert r.status_code == 403, (
            "Un POST sans token CSRF doit être rejeté avec 403"
        )

    def test_post_token_incorrect_bloque(self, client_admin):
        """Token CSRF présent mais invalide → 403."""
        r = client_admin.post(
            '/admin/backup-now',
            data={'_csrf_token': 'mauvais_token_xyz_000'},
        )
        assert r.status_code == 403, (
            "Un token CSRF incorrect doit être rejeté avec 403"
        )

    def test_post_avec_bon_token_csrf_accepte(self, client_admin):
        """POST avec le bon token CSRF → traité (pas 403)."""
        initialiser_csrf(client_admin)
        token = csrf_token(client_admin)
        assert token, "Le token CSRF doit être présent dans la session"

        # POST vers purge-suivi (admin_editeur uniquement, CSRF requis)
        r = client_admin.post(
            '/admin/purge-suivi',
            data={'_csrf_token': token},
            follow_redirects=True,
        )
        # La requête doit être traitée (pas 403 ni 405)
        assert r.status_code != 403, (
            "Un POST avec le bon token CSRF ne doit pas être rejeté"
        )
        assert r.status_code != 405, "Méthode POST non acceptée sur cette route"

    def test_token_csrf_different_entre_sessions(self, app):
        """Deux clients distincts ont des tokens CSRF différents."""
        c1 = app.test_client()
        c2 = app.test_client()

        initialiser_csrf(c1)
        initialiser_csrf(c2)

        t1 = csrf_token(c1)
        t2 = csrf_token(c2)

        assert t1, "Client 1 doit avoir un token CSRF"
        assert t2, "Client 2 doit avoir un token CSRF"
        assert t1 != t2, (
            "Deux sessions différentes ne doivent pas partager le même token CSRF"
        )

    def test_login_sans_csrf_autorise(self, client):
        """
        POST vers /login SANS token CSRF → 200 ou redirection (pas 403).
        Le blueprint 'auth' est explicitement exclu de la vérification CSRF.
        """
        r = client.post(
            '/login',
            data={'login': 'admin_ed', 'password': 'admin2026'},
            follow_redirects=False,
        )
        assert r.status_code != 403, (
            "La page /login ne doit PAS exiger de token CSRF"
        )

    def test_post_avec_token_header_x_csrf(self, client_admin):
        """
        POST avec le token CSRF dans l'en-tête X-CSRF-Token (appels AJAX).
        Doit être accepté au même titre qu'un champ de formulaire.
        """
        initialiser_csrf(client_admin)
        token = csrf_token(client_admin)

        r = client_admin.post(
            '/admin/purge-suivi',
            headers={'X-CSRF-Token': token},
            data={},
            follow_redirects=True,
        )
        assert r.status_code != 403, (
            "Le token CSRF via en-tête X-CSRF-Token doit être accepté"
        )
