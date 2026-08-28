"""
tests/test_auth.py — Tests d'authentification.

Couvre :
- Connexion avec identifiants corrects
- Refus en cas de mauvais mot de passe
- Refus si compte inactif
- Refus si login inexistant
- Déconnexion

NOTE sur les URLs :
  L'auth blueprint est enregistré sans url_prefix → les routes sont :
  /login, /logout, /mdp-oublie, /changer-mot-de-passe
"""
import pytest


class TestConnexion:
    """Tests de la route POST /login."""

    def test_login_identifiants_corrects_redirige(self, client):
        """Identifiants valides → redirection (succès de connexion)."""
        r = client.post(
            '/login',
            data={'login': 'admin_ed', 'password': 'admin2026'},
            follow_redirects=False,
        )
        # La connexion réussie doit rediriger vers le tableau de bord ou l'accueil
        assert r.status_code in (301, 302, 303), (
            f"Attendu une redirection après login réussi, obtenu {r.status_code}"
        )

    def test_login_identifiants_corrects_acces_admin(self, client):
        """Après connexion en admin_editeur, la page /admin/ est accessible."""
        client.post('/login', data={'login': 'admin_ed', 'password': 'admin2026'})
        r = client.get('/admin/', follow_redirects=False)
        assert r.status_code == 200, (
            f"admin_editeur doit pouvoir accéder à /admin/ après connexion (obtenu {r.status_code})"
        )

    def test_login_mauvais_mdp(self, client):
        """Mauvais mot de passe → formulaire renvoyé (200), accès protégé refusé."""
        r = client.post(
            '/login',
            data={'login': 'admin_ed', 'password': 'mdp_incorrect'},
            follow_redirects=True,
        )
        assert r.status_code == 200
        # Après un échec, /admin/ doit rediriger vers login
        r2 = client.get('/admin/', follow_redirects=False)
        assert r2.status_code in (301, 302, 303), (
            "Après échec de login, /admin/ doit rediriger vers login"
        )

    def test_login_login_inexistant(self, client):
        """Login inconnu → refus, accès protégé refusé."""
        client.post(
            '/login',
            data={'login': 'utilisateur_inexistant_xyz', 'password': 'mdp_test'},
            follow_redirects=True,
        )
        r = client.get('/admin/', follow_redirects=False)
        assert r.status_code in (301, 302, 303), (
            "Login inexistant ne doit pas donner accès à /admin/"
        )

    def test_login_compte_inactif(self, client):
        """Compte désactivé (actif=False) → refus de connexion."""
        # La route ne connecte que les utilisateurs actifs (filtre actif=True)
        client.post(
            '/login',
            data={'login': 'inactif', 'password': 'mdp_test'},
            follow_redirects=True,
        )
        # Le compte inactif ne doit pas accéder aux pages protégées
        r = client.get('/dashboard/', follow_redirects=False)
        assert r.status_code in (301, 302, 303), (
            "Un compte inactif ne doit pas avoir accès à l'application"
        )

    def test_login_champs_vides(self, client):
        """Champs login et password vides → formulaire renvoyé (200)."""
        r = client.post(
            '/login',
            data={'login': '', 'password': ''},
            follow_redirects=True,
        )
        # Aucun utilisateur avec login='' n'existe → formulaire renvoyé
        assert r.status_code == 200

    def test_login_tous_les_roles(self, app):
        """Chaque compte actif peut se connecter avec ses identifiants."""
        comptes = [
            ('admin_ed',  'admin2026'),
            ('admin_lec', 'mdp_test'),
            ('dir_daf',   'mdp_test'),
            ('svc_srh',   'mdp_test'),
            ('svc_stc',   'mdp_test'),
        ]
        for login, password in comptes:
            c = app.test_client()
            r = c.post(
                '/login',
                data={'login': login, 'password': password},
                follow_redirects=False,
            )
            assert r.status_code in (301, 302, 303), (
                f"Le compte '{login}' devrait pouvoir se connecter (obtenu {r.status_code})"
            )


class TestDeconnexion:
    """Tests de la route GET /logout."""

    def test_logout_redirige(self, client_admin):
        """Déconnexion → redirection."""
        r = client_admin.get('/logout', follow_redirects=False)
        assert r.status_code in (301, 302, 303), "Logout doit rediriger"

    def test_logout_coupe_acces_admin(self, client_admin):
        """Après déconnexion, /admin/ n'est plus accessible."""
        # Vérifie que le client peut accéder à /admin/ avant la déconnexion
        r_avant = client_admin.get('/admin/', follow_redirects=False)
        assert r_avant.status_code == 200, "admin_editeur doit accéder à /admin/ avant logout"

        # Déconnexion
        client_admin.get('/logout')

        # Après logout, /admin/ doit rediriger vers login
        r_apres = client_admin.get('/admin/', follow_redirects=False)
        assert r_apres.status_code in (301, 302, 303), (
            "Après logout, /admin/ doit rediriger vers la page de login"
        )
