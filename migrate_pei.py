"""
migrate_pei.py — Crée la table pei_activites si elle n'existe pas encore.
Usage : python migrate_pei.py
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
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pei_activites'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE pei_activites (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                activite_id     INTEGER NOT NULL UNIQUE REFERENCES activites(id),
                montant_engage  REAL DEFAULT 0.0,
                montant_mandate REAL DEFAULT 0.0,
                montant_paye    REAL DEFAULT 0.0
            )
        """)
        conn.commit()
        print("✓ Table pei_activites créée.")
    else:
        print("  Table pei_activites déjà présente.")
    conn.close()
    print("✅ Migration PEI terminée.")
