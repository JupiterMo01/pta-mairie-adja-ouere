"""
tests/test_principal.py — Droits réservés à l'administrateur principal (identifiant 'admin').

Couvre :
- Maintenance : seul le principal l'active, la désactive et garde l'accès pendant
- Années : création et activation réservées au principal
- Comptes : un autre admin éditeur crée des comptes direction ou service, mais pas de profil
  administrateur ni de compte DAAF / SBFC ; il modifie le nom d'un compte direction ou service,
  jamais son mot de passe ; il ne supprime, ne désactive ni ne réinitialise aucun compte
"""
import pytest
from conftest import post_csrf, _connecter
from models import db, User, Direction, Service, Annee


@pytest.fixture()
def maintenance_isolee(app, tmp_path):
    """Le fichier de maintenance des tests est isolé du dossier instance réel."""
    ancien = app.config.get('MAINTENANCE_FICHIER')
    app.config['MAINTENANCE_FICHIER'] = str(tmp_path / 'maintenance.json')
    yield
    app.config['MAINTENANCE_FICHIER'] = ancien


def _ids_financiers(app):
    """Crée au besoin la direction DAAF et le service SBFC, retourne leurs identifiants."""
    with app.app_context():
        daaf = Direction.query.filter_by(code='DAAF').first()
        if not daaf:
            daaf = Direction(code='DAAF', nom="Direction des Affaires Administratives et Financières")
            db.session.add(daaf)
            db.session.flush()
        sbfc = Service.query.filter_by(code='SBFC').first()
        if not sbfc:
            sbfc = Service(code='SBFC', nom='Service du Budget', direction_id=daaf.id)
            db.session.add(sbfc)
        db.session.commit()
        return daaf.id, sbfc.id


def _utilisateur(app, login):
    with app.app_context():
        return User.query.filter_by(login=login).first()


class TestMaintenance:

    def test_autre_admin_ne_peut_pas_activer(self, app, client_admin, maintenance_isolee):
        post_csrf(client_admin, '/admin/maintenance/activer', {'message': 'x'})
        assert client_admin.get('/admin/').status_code == 200   # plateforme toujours ouverte

    def test_seul_le_principal_garde_l_acces(self, app, maintenance_isolee):
        # Deux clients dans le même test : on vide l'utilisateur mémorisé par Flask-Login entre
        # chaque requête, sinon le second client hériterait de l'identité du premier.
        from flask import g, has_app_context

        def req(fonction, *args, **kwargs):
            if has_app_context():
                g.pop('_login_user', None)
            return fonction(*args, **kwargs)

        principal = req(_connecter, app, 'admin', 'principal2026')
        autre = req(_connecter, app, 'admin_ed', 'admin2026')
        req(post_csrf, principal, '/admin/maintenance/activer', {'message': 'Test'})
        try:
            assert req(principal.get, '/admin/').status_code == 200
            assert req(autre.get, '/admin/').status_code == 503
            req(post_csrf, autre, '/admin/maintenance/desactiver')
            assert req(autre.get, '/admin/').status_code == 503   # toujours en maintenance
        finally:
            req(post_csrf, principal, '/admin/maintenance/desactiver')
        assert req(autre.get, '/admin/').status_code == 200


class TestAnnees:

    def test_autre_admin_ne_cree_pas_d_annee(self, app, client_admin):
        post_csrf(client_admin, '/admin/annees/add', {'annee': '2031'})
        with app.app_context():
            assert Annee.query.filter_by(annee=2031).first() is None

    def test_autre_admin_n_active_pas_d_annee(self, app, client_admin):
        with app.app_context():
            a = Annee(annee=2032, actif=False)
            db.session.add(a)
            db.session.commit()
            aid = a.id
        post_csrf(client_admin, f'/admin/annees/{aid}/activate')
        with app.app_context():
            assert db.session.get(Annee, aid).actif is False
            assert Annee.query.filter_by(annee=2026).first().actif is True


class TestComptes:

    def _creer(self, client, login, role, **extra):
        data = dict(nom='Test', prenom='Compte', login=login, role=role, password='')
        data.update({k: str(v) for k, v in extra.items()})
        post_csrf(client, '/admin/users/add', data)

    def test_autre_admin_cree_un_compte_service(self, app, client_admin):
        with app.app_context():
            srh = Service.query.filter_by(code='SRH').first().id
        self._creer(client_admin, 'svc_cree_ok', 'service', service_id=srh)
        assert _utilisateur(app, 'svc_cree_ok') is not None

    @pytest.mark.parametrize('role', ['admin_editeur', 'admin_lecteur'])
    def test_autre_admin_ne_cree_pas_d_admin(self, app, client_admin, role):
        self._creer(client_admin, f'refus_{role}', role)
        assert _utilisateur(app, f'refus_{role}') is None

    def test_autre_admin_ne_cree_pas_daaf_ni_sbfc(self, app, client_admin):
        daaf, sbfc = _ids_financiers(app)
        self._creer(client_admin, 'refus_daaf', 'direction', direction_id=daaf)
        self._creer(client_admin, 'refus_sbfc', 'service', service_id=sbfc)
        assert _utilisateur(app, 'refus_daaf') is None
        assert _utilisateur(app, 'refus_sbfc') is None

    def test_principal_cree_daaf(self, app, client_principal):
        daaf, _ = _ids_financiers(app)
        self._creer(client_principal, 'daaf_par_principal', 'direction', direction_id=daaf)
        assert _utilisateur(app, 'daaf_par_principal') is not None

    def test_autre_admin_ne_modifie_pas_un_compte_daaf(self, app, client_admin):
        daaf, _ = _ids_financiers(app)
        with app.app_context():
            if not User.query.filter_by(login='daaf_existant').first():
                u = User(nom='Chef', prenom='DAAF', login='daaf_existant', role='direction', direction_id=daaf)
                u.set_password('Mdp#Test2026')
                db.session.add(u)
                db.session.commit()
            uid = User.query.filter_by(login='daaf_existant').first().id
        post_csrf(client_admin, f'/admin/users/{uid}/edit',
                  dict(nom='Modifie', prenom='DAAF', role='direction', direction_id=daaf))
        assert _utilisateur(app, 'daaf_existant').nom == 'Chef'
        assert f'/admin/users/{uid}/edit' not in client_admin.get('/admin/users').data.decode()

    def test_autre_admin_modifie_le_nom_sans_toucher_au_reste(self, app, client_admin):
        u = _utilisateur(app, 'svc_stc')
        hash_avant, actif_avant = u.password_hash, u.actif
        post_csrf(client_admin, f'/admin/users/{u.id}/edit',
                  dict(nom='Renomme', prenom=u.prenom, role='service', service_id=u.service_id,
                       direction_id=u.direction_id or ''))
        u2 = _utilisateur(app, 'svc_stc')
        assert u2.nom == 'Renomme' and u2.password_hash == hash_avant and u2.actif == actif_avant

    def test_autre_admin_ne_change_pas_de_mot_de_passe(self, app, client_admin):
        u = _utilisateur(app, 'svc_stc')
        post_csrf(client_admin, f'/admin/users/{u.id}/edit',
                  dict(nom=u.nom, prenom=u.prenom, role='service', service_id=u.service_id,
                       password='NouveauMdp#2026'))
        assert _utilisateur(app, 'svc_stc').password_hash == u.password_hash

    def test_autre_admin_ne_modifie_pas_un_admin(self, app, client_admin):
        u = _utilisateur(app, 'admin_lec')
        post_csrf(client_admin, f'/admin/users/{u.id}/edit',
                  dict(nom='Pirate', prenom=u.prenom, role='admin_lecteur'))
        assert _utilisateur(app, 'admin_lec').nom == u.nom

    def test_autre_admin_ne_promeut_pas_en_admin(self, app, client_admin):
        u = _utilisateur(app, 'svc_stc')
        post_csrf(client_admin, f'/admin/users/{u.id}/edit',
                  dict(nom=u.nom, prenom=u.prenom, role='admin_editeur'))
        assert _utilisateur(app, 'svc_stc').role == 'service'

    @pytest.mark.parametrize('action', ['toggle', 'delete', 'reset-password'])
    def test_autre_admin_ni_supprime_ni_desactive_ni_reinitialise(self, app, client_admin, action):
        u = _utilisateur(app, 'svc_srh')
        post_csrf(client_admin, f'/admin/users/{u.id}/{action}')
        u2 = _utilisateur(app, 'svc_srh')
        assert u2 is not None and u2.actif == u.actif and u2.password_hash == u.password_hash
