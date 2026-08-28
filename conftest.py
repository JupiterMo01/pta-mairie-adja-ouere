"""
conftest.py — Configuration pytest pour l'application PTA Mairie.
DB SQLite en mémoire, rate-limiting désactivé, données de test minimales.
"""
import os
import pytest

# SECRET_KEY doit exister AVANT l'import de l'app (Config lève RuntimeError sinon)
os.environ.setdefault('SECRET_KEY', 'cle-tests-unitaires-non-production-xyz123456789abc')

from app import create_app
from models import (
    db as _db,
    User, Direction, Service, Annee,
    Programme, Projet, Activite, Tache, SuiviTache,
)
from werkzeug.security import generate_password_hash


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures principales
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    """
    Application Flask configurée pour les tests :
    - Base de données SQLite en mémoire (isolée, jetée après la session)
    - Rate-limiting désactivé
    - SESSION_COOKIE_SECURE désactivé (pas de HTTPS en tests)
    """
    flask_app = create_app(test_config={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'RATELIMIT_ENABLED': False,
        'RATELIMIT_STORAGE_URI': 'memory://',
        'SESSION_COOKIE_SECURE': False,
    })

    with flask_app.app_context():
        _db.create_all()
        _alimenter_db()

    yield flask_app


def _alimenter_db():
    """
    Crée le jeu de données minimal pour les tests :
    - 2 directions, 2 services
    - 1 année PTA active
    - 1 programme → 1 projet → 1 activité → 1 tâche (rattachée à SRH)
    - 6 utilisateurs (admin_éditeur, admin_lecteur, direction, 2 services, inactif)
    """
    # Directions
    dir1 = Direction(code='DAF', nom='Direction Administrative et Financière')
    dir2 = Direction(code='DTC', nom='Direction Technique et Culturelle')
    _db.session.add_all([dir1, dir2])
    _db.session.flush()

    # Services
    svc1 = Service(code='SRH', nom='Service des Ressources Humaines', direction_id=dir1.id)
    svc2 = Service(code='STC', nom='Service Technique Construction',  direction_id=dir2.id)
    _db.session.add_all([svc1, svc2])
    _db.session.flush()

    # Année PTA active
    annee = Annee(annee=2026, actif=True)
    _db.session.add(annee)
    _db.session.flush()

    # Hiérarchie PTA minimale
    prog  = Programme(annee_id=annee.id, numero=1, nom='Programme Test', poids=100.0)
    _db.session.add(prog)
    _db.session.flush()

    proj = Projet(programme_id=prog.id, numero=1, nom='Projet Test', poids=100.0)
    _db.session.add(proj)
    _db.session.flush()

    act = Activite(
        projet_id=proj.id, numero=1, nom='Activité Test',
        poids=100.0, direction_responsable_id=dir1.id,
    )
    _db.session.add(act)
    _db.session.flush()

    tache = Tache(
        activite_id=act.id, numero=1, nom='Tâche Test',
        poids=100.0, service_responsable_id=svc1.id,
    )
    tache.services_concernes.append(svc1)
    _db.session.add(tache)
    _db.session.flush()

    # Utilisateurs de test
    utilisateurs = [
        dict(nom='Admin',   prenom='Éditeur', login='admin_ed',  role='admin_editeur',
             password='admin2026', actif=True),
        dict(nom='Admin',   prenom='Lecteur', login='admin_lec', role='admin_lecteur',
             password='mdp_test',  actif=True),
        dict(nom='Chef',    prenom='DAF',     login='dir_daf',   role='direction',
             direction_id=dir1.id, password='mdp_test', actif=True),
        dict(nom='Agent',   prenom='SRH',     login='svc_srh',   role='service',
             service_id=svc1.id, direction_id=dir1.id,
             password='mdp_test', actif=True),
        dict(nom='Agent',   prenom='STC',     login='svc_stc',   role='service',
             service_id=svc2.id, direction_id=dir2.id,
             password='mdp_test', actif=True),
        dict(nom='Inactif', prenom='Test',    login='inactif',   role='service',
             password='mdp_test', actif=False),
    ]
    for info in utilisateurs:
        pwd = info.pop('password')
        _db.session.add(User(**info, password_hash=generate_password_hash(pwd)))

    _db.session.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Clients de test pré-authentifiés
# ──────────────────────────────────────────────────────────────────────────────

def _connecter(app, login, password):
    """Crée un client Flask et le connecte avec les identifiants donnés."""
    c = app.test_client()
    # L'URL réelle du login est /login (auth_bp sans url_prefix)
    c.post('/login', data={'login': login, 'password': password})
    return c


@pytest.fixture()
def client(app):
    """Client Flask non authentifié."""
    return app.test_client()


@pytest.fixture()
def client_admin(app):
    """Client connecté comme admin_editeur."""
    return _connecter(app, 'admin_ed', 'admin2026')


@pytest.fixture()
def client_lecteur(app):
    """Client connecté comme admin_lecteur."""
    return _connecter(app, 'admin_lec', 'mdp_test')


@pytest.fixture()
def client_direction(app):
    """Client connecté comme utilisateur direction (chef DAF)."""
    return _connecter(app, 'dir_daf', 'mdp_test')


@pytest.fixture()
def client_service(app):
    """Client connecté comme service SRH (direction DAF)."""
    return _connecter(app, 'svc_srh', 'mdp_test')


@pytest.fixture()
def client_service2(app):
    """Client connecté comme service STC (direction DTC — autre direction)."""
    return _connecter(app, 'svc_stc', 'mdp_test')


# ──────────────────────────────────────────────────────────────────────────────
# Fonctions utilitaires partagées
# ──────────────────────────────────────────────────────────────────────────────

def csrf_token(client):
    """Lit le token CSRF depuis la session du client Flask de test."""
    with client.session_transaction() as sess:
        return sess.get('_csrf_token', '')


def initialiser_csrf(client):
    """
    Déclenche inject_csrf en faisant un GET sur la page de login.
    - Utilisateur non connecté : la page de login se rend directement → inject_csrf s'exécute.
    - Utilisateur connecté : /login redirige vers /dashboard → inject_csrf s'exécute aussi.
    follow_redirects=True est nécessaire pour les deux cas.
    """
    if not csrf_token(client):
        client.get('/login', follow_redirects=True)


def post_csrf(client, url, data=None, follow_redirects=True):
    """
    Effectue un POST en incluant automatiquement le token CSRF.
    Initialise la session si le token n'existe pas encore.
    """
    initialiser_csrf(client)
    payload = dict(data or {})
    payload['_csrf_token'] = csrf_token(client)
    return client.post(url, data=payload, follow_redirects=follow_redirects)
