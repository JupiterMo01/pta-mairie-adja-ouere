"""
Migration PAI v2 :
  - Ajoute la colonne inclure_dans_pai (BOOLEAN, default 1) à la table activites
  - Crée les tables pai_programmes et pai_projets
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
os.environ.setdefault('SECRET_KEY', 'dev123')

from app import create_app
from models import db

app = create_app()

with app.app_context():
    conn = db.engine.raw_connection()
    cur  = conn.cursor()

    # 1. Ajouter inclure_dans_pai à activites (si absent)
    cur.execute("PRAGMA table_info(activites)")
    cols = [row[1] for row in cur.fetchall()]
    if 'inclure_dans_pai' not in cols:
        cur.execute("ALTER TABLE activites ADD COLUMN inclure_dans_pai BOOLEAN DEFAULT 1")
        # Mettre à True (1) pour toutes les activités d'investissement existantes
        cur.execute("""
            UPDATE activites
            SET inclure_dans_pai = 1
            WHERE LOWER(type_activite) LIKE '%investissement%'
        """)
        cur.execute("""
            UPDATE activites
            SET inclure_dans_pai = 0
            WHERE LOWER(type_activite) NOT LIKE '%investissement%'
        """)
        print("✓ Colonne inclure_dans_pai ajoutée à activites")
    else:
        print("  Colonne inclure_dans_pai déjà présente")

    # 2. Créer pai_programmes (si absent)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pai_programmes'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE pai_programmes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                programme_id INTEGER NOT NULL UNIQUE REFERENCES programmes(id),
                poids_pai REAL DEFAULT 0.0
            )
        """)
        print("✓ Table pai_programmes créée")
    else:
        print("  Table pai_programmes déjà présente")

    # 3. Créer pai_projets (si absent)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pai_projets'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE pai_projets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                projet_id INTEGER NOT NULL UNIQUE REFERENCES projets(id),
                poids_pai REAL DEFAULT 0.0
            )
        """)
        print("✓ Table pai_projets créée")
    else:
        print("  Table pai_projets déjà présente")

    conn.commit()
    conn.close()

    # Vérification finale
    from models import Activite, Annee
    annee = Annee.query.filter_by(actif=True).first()
    if annee:
        from models import Programme
        pgs = Programme.query.filter_by(annee_id=annee.id).all()
        inv_inclus = [a for pg in pgs for pj in pg.projets for a in pj.activites
                      if a.type_activite and 'investissement' in a.type_activite.lower()
                      and a.inclure_dans_pai is not False]
        print(f"\nAnnée active : {annee.annee}")
        print(f"Activités d'investissement incluses dans le PAI : {len(inv_inclus)}")
    print("\n✅ Migration PAI v2 terminée.")
