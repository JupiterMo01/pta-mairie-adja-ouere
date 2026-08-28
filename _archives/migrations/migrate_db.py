"""
Migration v2 — Nouvelles colonnes PTA (sources de financement, objectifs, ordre tâches).
Exécuter UNE SEULE FOIS : python migrate_db.py
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'instance', 'pta_mairie.db')

def add_col(c, table, col, typ, default=None):
    c.execute(f"PRAGMA table_info({table})")
    existing = [r[1] for r in c.fetchall()]
    if col not in existing:
        sql = f"ALTER TABLE {table} ADD COLUMN {col} {typ}"
        if default is not None:
            sql += f" DEFAULT {default}"
        c.execute(sql)
        print(f"  + {table}.{col}")
    # silencieux si déjà présent

conn = sqlite3.connect(DB)
cur = conn.cursor()
print("=== Migration v2 ===")

# ── Annees ─────────────────────────────────────────────────────────────────
add_col(cur, 'annees', 'objectif_general', 'TEXT')

# ── Programmes ─────────────────────────────────────────────────────────────
add_col(cur, 'programmes', 'objectif_specifique', 'TEXT')

# ── Activites ──────────────────────────────────────────────────────────────
for f in ['ressources_propres', 'fadec_affecte', 'fadec_non_affecte',
          'autres_partenaires', 'autres_fonds']:
    add_col(cur, 'activites', f, 'REAL', 0)
add_col(cur, 'activites', 'details_financement', 'TEXT')
add_col(cur, 'activites', 'acteurs_externes', 'TEXT')

# ── Taches ─────────────────────────────────────────────────────────────────
add_col(cur, 'taches', 'ordre', 'INTEGER', 0)
add_col(cur, 'taches', 'imputation_budgetaire', 'TEXT')
for f in ['ressources_propres', 'fadec_affecte', 'fadec_non_affecte',
          'autres_partenaires', 'autres_fonds']:
    add_col(cur, 'taches', f, 'REAL', 0)
add_col(cur, 'taches', 'details_financement', 'TEXT')
add_col(cur, 'taches', 'acteurs_externes', 'TEXT')

# ── Nouvelles tables d'association direction ────────────────────────────────
cur.execute('''CREATE TABLE IF NOT EXISTS activite_directions (
    activite_id INTEGER NOT NULL,
    direction_id INTEGER NOT NULL,
    PRIMARY KEY (activite_id, direction_id)
)''')
cur.execute('''CREATE TABLE IF NOT EXISTS tache_directions (
    tache_id INTEGER NOT NULL,
    direction_id INTEGER NOT NULL,
    PRIMARY KEY (tache_id, direction_id)
)''')

# Initialiser ordre des tâches existantes
cur.execute('''
    UPDATE taches SET ordre = numero WHERE ordre = 0 OR ordre IS NULL
''')

conn.commit()
conn.close()
print("✅ Migration v2 terminée.")