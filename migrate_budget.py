"""
migrate_budget.py — Crée la table budget_executions si elle n'existe pas encore.
Usage : python migrate_budget.py
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
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='budget_executions'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE budget_executions (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                annee_id                INTEGER NOT NULL REFERENCES annees(id),
                trimestre               INTEGER NOT NULL,
                type_depense            TEXT    NOT NULL,
                previsions              REAL    DEFAULT 0.0,
                montant_engage          REAL    DEFAULT 0.0,
                montant_mandate         REAL    DEFAULT 0.0,
                montant_paye            REAL    DEFAULT 0.0,
                previsions_verrouillees INTEGER DEFAULT 0,
                UNIQUE(annee_id, trimestre, type_depense)
            )
        """)
        conn.commit()
        print("✓ Table budget_executions créée.")
    else:
        print("  Table budget_executions déjà présente.")
    conn.close()
    print("✅ Migration Budget terminée.")
