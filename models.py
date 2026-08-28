from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    direction_id = db.Column(db.Integer, db.ForeignKey('directions.id'), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    actif = db.Column(db.Boolean, default=True)
    email = db.Column(db.String(200), nullable=True)

    direction = db.relationship('Direction', foreign_keys=[direction_id], backref='users')
    service = db.relationship('Service', foreign_keys=[service_id], backref='users')

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)

    @property
    def nom_complet(self): return f"{self.prenom} {self.nom}"

    @property
    def role_label(self):
        return {'admin_editeur': 'Admin Éditeur', 'admin_lecteur': 'Admin Lecteur',
                'direction': 'Direction', 'service': 'Service'}.get(self.role, self.role)


class Direction(db.Model):
    __tablename__ = 'directions'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    services = db.relationship('Service', backref='direction', lazy=True,
                               cascade='all, delete-orphan')


class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    direction_id = db.Column(db.Integer, db.ForeignKey('directions.id'), nullable=False)


class Annee(db.Model):
    __tablename__ = 'annees'
    id = db.Column(db.Integer, primary_key=True)
    annee = db.Column(db.Integer, unique=True, nullable=False)
    actif = db.Column(db.Boolean, default=False)
    objectif_general = db.Column(db.Text, nullable=True)


# ─── Hiérarchie PTA ────────────────────────────────────────────────────────

class Programme(db.Model):
    __tablename__ = 'programmes'
    id = db.Column(db.Integer, primary_key=True)
    annee_id = db.Column(db.Integer, db.ForeignKey('annees.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    objectif_specifique = db.Column(db.Text, nullable=True)
    poids = db.Column(db.Float, default=0.0)
    observations = db.Column(db.Text, nullable=True)

    annee = db.relationship('Annee', backref='programmes')
    projets = db.relationship('Projet', backref='programme', lazy=True,
                              cascade='all, delete-orphan', order_by='Projet.numero')

    @property
    def code(self): return str(self.numero)

    @property
    def libelle(self): return f"Programme {self.numero} : {self.nom}"

    @property
    def budget_total(self):
        return sum(p.budget_total for p in self.projets)

    @property
    def ressources_propres(self): return sum(p.ressources_propres for p in self.projets)
    @property
    def fadec_affecte(self): return sum(p.fadec_affecte for p in self.projets)
    @property
    def fadec_non_affecte(self): return sum(p.fadec_non_affecte for p in self.projets)
    @property
    def autres_partenaires(self): return sum(p.autres_partenaires for p in self.projets)
    @property
    def autres_fonds(self): return sum(p.autres_fonds for p in self.projets)


class Projet(db.Model):
    __tablename__ = 'projets'
    id = db.Column(db.Integer, primary_key=True)
    programme_id = db.Column(db.Integer, db.ForeignKey('programmes.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    poids = db.Column(db.Float, default=0.0)
    observations = db.Column(db.Text, nullable=True)

    activites = db.relationship('Activite', backref='projet', lazy=True,
                                cascade='all, delete-orphan', order_by='Activite.numero')

    @property
    def code(self): return f"{self.programme.numero}.{self.numero}"

    @property
    def libelle(self): return f"Projet {self.code} : {self.nom}"

    @property
    def budget_total(self): return sum(a.budget_total for a in self.activites)

    @property
    def ressources_propres(self): return sum(a.src_rp for a in self.activites)
    @property
    def fadec_affecte(self): return sum(a.src_fa for a in self.activites)
    @property
    def fadec_non_affecte(self): return sum(a.src_fn for a in self.activites)
    @property
    def autres_partenaires(self): return sum(a.src_ap for a in self.activites)
    @property
    def autres_fonds(self): return sum(a.src_af for a in self.activites)


# Tables d'association
activite_services = db.Table(
    'activite_services',
    db.Column('activite_id', db.Integer, db.ForeignKey('activites.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True)
)

activite_directions = db.Table(
    'activite_directions',
    db.Column('activite_id', db.Integer, db.ForeignKey('activites.id'), primary_key=True),
    db.Column('direction_id', db.Integer, db.ForeignKey('directions.id'), primary_key=True)
)


class Activite(db.Model):
    __tablename__ = 'activites'
    id = db.Column(db.Integer, primary_key=True)
    projet_id = db.Column(db.Integer, db.ForeignKey('projets.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    direction_responsable_id = db.Column(db.Integer, db.ForeignKey('directions.id'), nullable=True)
    imputation_budgetaire = db.Column(db.String(200), nullable=True)
    # Sources de financement (somme des tâches)
    ressources_propres = db.Column(db.Float, default=0.0)
    fadec_affecte = db.Column(db.Float, default=0.0)
    fadec_non_affecte = db.Column(db.Float, default=0.0)
    autres_partenaires = db.Column(db.Float, default=0.0)
    autres_fonds = db.Column(db.Float, default=0.0)
    details_financement = db.Column(db.Text, nullable=True)
    acteurs_externes = db.Column(db.Text, nullable=True)
    periode_debut = db.Column(db.String(20), nullable=True)
    periode_fin = db.Column(db.String(20), nullable=True)
    mode_execution = db.Column(db.String(100), nullable=True, default='Direct')
    type_activite = db.Column(db.String(50), nullable=False, default='Activité de fonctionnement')
    poids = db.Column(db.Float, default=0.0)
    observations = db.Column(db.Text, nullable=True)

    direction_responsable = db.relationship('Direction', foreign_keys=[direction_responsable_id])
    services_intervenants = db.relationship('Service', secondary=activite_services, lazy='subquery')
    directions_associees = db.relationship('Direction', secondary=activite_directions,
                                           lazy='subquery',
                                           primaryjoin='Activite.id == activite_directions.c.activite_id',
                                           secondaryjoin='Direction.id == activite_directions.c.direction_id')
    taches = db.relationship('Tache', backref='activite', lazy=True,
                             cascade='all, delete-orphan',
                             order_by='Tache.ordre, Tache.numero')

    @property
    def code(self): return f"{self.projet.code}.{self.numero}"

    @property
    def libelle(self): return f"Activité {self.code} : {self.nom}"

    @property
    def budget_total(self):
        if self.taches:
            return sum(t.budget_total for t in self.taches)
        return (self.ressources_propres or 0) + (self.fadec_affecte or 0) + \
               (self.fadec_non_affecte or 0) + (self.autres_partenaires or 0) + \
               (self.autres_fonds or 0)

    # Sources calculées depuis les tâches quand elles existent
    @property
    def src_rp(self):
        return sum(t.ressources_propres or 0 for t in self.taches) if self.taches else (self.ressources_propres or 0)
    @property
    def src_fa(self):
        return sum(t.fadec_affecte or 0 for t in self.taches) if self.taches else (self.fadec_affecte or 0)
    @property
    def src_fn(self):
        return sum(t.fadec_non_affecte or 0 for t in self.taches) if self.taches else (self.fadec_non_affecte or 0)
    @property
    def src_ap(self):
        return sum(t.autres_partenaires or 0 for t in self.taches) if self.taches else (self.autres_partenaires or 0)
    @property
    def src_af(self):
        return sum(t.autres_fonds or 0 for t in self.taches) if self.taches else (self.autres_fonds or 0)


# Tables d'association tâches
tache_services = db.Table(
    'tache_services',
    db.Column('tache_id', db.Integer, db.ForeignKey('taches.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True)
)

tache_directions = db.Table(
    'tache_directions',
    db.Column('tache_id', db.Integer, db.ForeignKey('taches.id'), primary_key=True),
    db.Column('direction_id', db.Integer, db.ForeignKey('directions.id'), primary_key=True)
)


class Tache(db.Model):
    __tablename__ = 'taches'
    id = db.Column(db.Integer, primary_key=True)
    activite_id = db.Column(db.Integer, db.ForeignKey('activites.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    ordre = db.Column(db.Integer, default=0)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    poids = db.Column(db.Float, default=0.0)
    service_responsable_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    imputation_budgetaire = db.Column(db.String(200), nullable=True)
    # Sources de financement (saisie directe au niveau tâche)
    ressources_propres = db.Column(db.Float, default=0.0)
    fadec_affecte = db.Column(db.Float, default=0.0)
    fadec_non_affecte = db.Column(db.Float, default=0.0)
    autres_partenaires = db.Column(db.Float, default=0.0)
    autres_fonds = db.Column(db.Float, default=0.0)
    details_financement = db.Column(db.Text, nullable=True)
    acteurs_externes = db.Column(db.Text, nullable=True)
    mode_execution = db.Column(db.String(100), nullable=True, default='Direct')
    periode_debut = db.Column(db.String(20), nullable=True)
    periode_fin = db.Column(db.String(20), nullable=True)
    observations = db.Column(db.Text, nullable=True)

    direction_responsable_id = db.Column(db.Integer, db.ForeignKey('directions.id'), nullable=True)

    service_responsable = db.relationship('Service', foreign_keys=[service_responsable_id])
    direction_responsable = db.relationship('Direction', foreign_keys=[direction_responsable_id])
    services_concernes = db.relationship('Service', secondary=tache_services, lazy='subquery')
    directions_associees = db.relationship('Direction', secondary=tache_directions,
                                           lazy='subquery',
                                           primaryjoin='Tache.id == tache_directions.c.tache_id',
                                           secondaryjoin='Direction.id == tache_directions.c.direction_id')
    suivis = db.relationship('SuiviTache', backref='tache', lazy=True,
                             cascade='all, delete-orphan')

    @property
    def code(self): return f"{self.activite.code}.{self.numero}"

    @property
    def budget_total(self):
        return (self.ressources_propres or 0) + (self.fadec_affecte or 0) + \
               (self.fadec_non_affecte or 0) + (self.autres_partenaires or 0) + \
               (self.autres_fonds or 0)


class SuiviTache(db.Model):
    __tablename__ = 'suivi_taches'
    id = db.Column(db.Integer, primary_key=True)
    tache_id = db.Column(db.Integer, db.ForeignKey('taches.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    trimestre = db.Column(db.Integer, nullable=False)
    annee_id = db.Column(db.Integer, db.ForeignKey('annees.id'), nullable=False)
    statut = db.Column(db.String(20), default='non_execute')
    taux_execution = db.Column(db.Float, nullable=True)   # saisi manuellement si en_cours
    observation = db.Column(db.Text, nullable=True)
    date_maj = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    modified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    service = db.relationship('Service', foreign_keys=[service_id])
    annee = db.relationship('Annee', foreign_keys=[annee_id])
    modified_by = db.relationship('User', foreign_keys=[modified_by_id])

    __table_args__ = (
        db.UniqueConstraint('tache_id', 'service_id', 'trimestre', 'annee_id',
                            name='unique_suivi'),
    )

    @property
    def taux(self):
        if self.statut == 'execute':
            return 100.0
        if self.statut == 'en_cours':
            return float(self.taux_execution or 0)
        return 0.0


# Constantes modes d'exécution
MODES_EXECUTION = [
    'Direct',
    'Consultation',
    "Maîtrise d'ouvrage délégué",
    'Régie',
]


# ─── Bibliothèque d'activités ─────────────────────────────────────────────────

biblio_act_services = db.Table(
    'biblio_act_services',
    db.Column('biblio_act_id', db.Integer, db.ForeignKey('biblio_activites.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True)
)

biblio_act_directions = db.Table(
    'biblio_act_directions',
    db.Column('biblio_act_id', db.Integer, db.ForeignKey('biblio_activites.id'), primary_key=True),
    db.Column('direction_id', db.Integer, db.ForeignKey('directions.id'), primary_key=True)
)

biblio_tache_services = db.Table(
    'biblio_tache_services',
    db.Column('biblio_tache_id', db.Integer, db.ForeignKey('biblio_taches.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True)
)

biblio_tache_directions = db.Table(
    'biblio_tache_directions',
    db.Column('biblio_tache_id', db.Integer, db.ForeignKey('biblio_taches.id'), primary_key=True),
    db.Column('direction_id', db.Integer, db.ForeignKey('directions.id'), primary_key=True)
)


class BiblioActivite(db.Model):
    __tablename__ = 'biblio_activites'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    direction_responsable_id = db.Column(db.Integer, db.ForeignKey('directions.id'), nullable=True)
    mode_execution = db.Column(db.String(100), nullable=True, default='Direct')
    type_activite = db.Column(db.String(50), nullable=True, default='Activité de fonctionnement')
    imputation_budgetaire = db.Column(db.String(200), nullable=True)
    periode_debut = db.Column(db.String(20), nullable=True)
    periode_fin = db.Column(db.String(20), nullable=True)
    poids = db.Column(db.Float, default=0.0)
    ressources_propres = db.Column(db.Float, default=0.0)
    fadec_affecte = db.Column(db.Float, default=0.0)
    fadec_non_affecte = db.Column(db.Float, default=0.0)
    autres_partenaires = db.Column(db.Float, default=0.0)
    autres_fonds = db.Column(db.Float, default=0.0)
    details_financement = db.Column(db.Text, nullable=True)
    acteurs_externes = db.Column(db.Text, nullable=True)

    direction_responsable = db.relationship('Direction', foreign_keys=[direction_responsable_id])
    services_associes = db.relationship('Service', secondary=biblio_act_services, lazy='subquery')
    directions_associees = db.relationship(
        'Direction', secondary=biblio_act_directions, lazy='subquery',
        primaryjoin='BiblioActivite.id == biblio_act_directions.c.biblio_act_id',
        secondaryjoin='Direction.id == biblio_act_directions.c.direction_id')
    taches = db.relationship('BiblioTache', backref='biblio_activite', lazy=True,
                             cascade='all, delete-orphan', order_by='BiblioTache.numero')

    @property
    def budget_total(self):
        if self.taches:
            return sum(t.budget_total for t in self.taches)
        return (self.ressources_propres or 0) + (self.fadec_affecte or 0) + \
               (self.fadec_non_affecte or 0) + (self.autres_partenaires or 0) + \
               (self.autres_fonds or 0)

    @property
    def src_rp(self):
        return sum(t.ressources_propres or 0 for t in self.taches) if self.taches else (self.ressources_propres or 0)
    @property
    def src_fa(self):
        return sum(t.fadec_affecte or 0 for t in self.taches) if self.taches else (self.fadec_affecte or 0)
    @property
    def src_fn(self):
        return sum(t.fadec_non_affecte or 0 for t in self.taches) if self.taches else (self.fadec_non_affecte or 0)
    @property
    def src_ap(self):
        return sum(t.autres_partenaires or 0 for t in self.taches) if self.taches else (self.autres_partenaires or 0)
    @property
    def src_af(self):
        return sum(t.autres_fonds or 0 for t in self.taches) if self.taches else (self.autres_fonds or 0)


class BiblioTache(db.Model):
    __tablename__ = 'biblio_taches'
    id = db.Column(db.Integer, primary_key=True)
    biblio_activite_id = db.Column(db.Integer, db.ForeignKey('biblio_activites.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    poids = db.Column(db.Float, default=0.0)
    service_responsable_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    imputation_budgetaire = db.Column(db.String(200), nullable=True)
    ressources_propres = db.Column(db.Float, default=0.0)
    fadec_affecte = db.Column(db.Float, default=0.0)
    fadec_non_affecte = db.Column(db.Float, default=0.0)
    autres_partenaires = db.Column(db.Float, default=0.0)
    autres_fonds = db.Column(db.Float, default=0.0)
    details_financement = db.Column(db.Text, nullable=True)
    acteurs_externes = db.Column(db.Text, nullable=True)
    mode_execution = db.Column(db.String(100), nullable=True, default='Direct')
    periode_debut  = db.Column(db.String(20), nullable=True)
    periode_fin    = db.Column(db.String(20), nullable=True)
    observations   = db.Column(db.Text, nullable=True)

    direction_responsable_id = db.Column(db.Integer, db.ForeignKey('directions.id'), nullable=True)

    service_responsable = db.relationship('Service', foreign_keys=[service_responsable_id])
    direction_responsable = db.relationship('Direction', foreign_keys=[direction_responsable_id])
    services_concernes = db.relationship('Service', secondary=biblio_tache_services, lazy='subquery')
    directions_associees = db.relationship(
        'Direction', secondary=biblio_tache_directions, lazy='subquery',
        primaryjoin='BiblioTache.id == biblio_tache_directions.c.biblio_tache_id',
        secondaryjoin='Direction.id == biblio_tache_directions.c.direction_id')

    @property
    def budget_total(self):
        return (self.ressources_propres or 0) + (self.fadec_affecte or 0) + \
               (self.fadec_non_affecte or 0) + (self.autres_partenaires or 0) + \
               (self.autres_fonds or 0)


# ─── Backup PTA ───────────────────────────────────────────────────────────────

class PTABackup(db.Model):
    __tablename__ = 'pta_backups'
    id = db.Column(db.Integer, primary_key=True)
    annee_id = db.Column(db.Integer, db.ForeignKey('annees.id'), nullable=True)
    annee_label = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    nb_programmes = db.Column(db.Integer, default=0)
    nb_activites = db.Column(db.Integer, default=0)
    nb_taches = db.Column(db.Integer, default=0)
    contenu = db.Column(db.Text, nullable=False)

    created_by = db.relationship('User', foreign_keys=[created_by_id])
    annee = db.relationship('Annee', foreign_keys=[annee_id])


# ─── Journal d'audit ─────────────────────────────────────────────────────────

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id          = db.Column(db.Integer, primary_key=True)
    horodatage  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_nom    = db.Column(db.String(150))   # snapshot — survit à la suppression du compte
    user_role   = db.Column(db.String(30))
    action      = db.Column(db.String(80),    nullable=False)
    details     = db.Column(db.Text)
    ip          = db.Column(db.String(45))


# ─── Structures externes (ONGs, prestataires, partenaires techniques) ─────────

activite_struct_ext = db.Table(
    'activite_struct_ext',
    db.Column('activite_id', db.Integer, db.ForeignKey('activites.id'), primary_key=True),
    db.Column('struct_ext_id', db.Integer, db.ForeignKey('structures_externes.id'), primary_key=True)
)

tache_struct_ext = db.Table(
    'tache_struct_ext',
    db.Column('tache_id', db.Integer, db.ForeignKey('taches.id'), primary_key=True),
    db.Column('struct_ext_id', db.Integer, db.ForeignKey('structures_externes.id'), primary_key=True)
)

biblio_act_struct_ext = db.Table(
    'biblio_act_struct_ext',
    db.Column('biblio_act_id', db.Integer, db.ForeignKey('biblio_activites.id'), primary_key=True),
    db.Column('struct_ext_id', db.Integer, db.ForeignKey('structures_externes.id'), primary_key=True)
)

biblio_tache_struct_ext = db.Table(
    'biblio_tache_struct_ext',
    db.Column('biblio_tache_id', db.Integer, db.ForeignKey('biblio_taches.id'), primary_key=True),
    db.Column('struct_ext_id', db.Integer, db.ForeignKey('structures_externes.id'), primary_key=True)
)


class StructureExterne(db.Model):
    __tablename__ = 'structures_externes'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    type_org = db.Column(db.String(100))
    description = db.Column(db.Text)


# Relations ajoutées après définition de StructureExterne (forward references)
Activite.structures_externes = db.relationship(
    'StructureExterne', secondary=activite_struct_ext, lazy='subquery')
Tache.structures_externes = db.relationship(
    'StructureExterne', secondary=tache_struct_ext, lazy='subquery')
BiblioActivite.structures_externes = db.relationship(
    'StructureExterne', secondary=biblio_act_struct_ext, lazy='subquery')
BiblioTache.structures_externes = db.relationship(
    'StructureExterne', secondary=biblio_tache_struct_ext, lazy='subquery')