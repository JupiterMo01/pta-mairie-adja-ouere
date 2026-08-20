"""
migrate_v4.py
Ajoute la colonne taux_execution dans la table suivi_taches.
"""
import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), 'instance', 'pta_mairie.db')

conn = sqlite3.connect(DB)
cur  = conn.cursor()

cur.execute("PRAGMA table_info(suivi_taches)")
existing = [r[1] for r in cur.fetchall()]

if 'taux_execution' not in existing:
    cur.execute("ALTER TABLE suivi_taches ADD COLUMN taux_execution REAL")
    print("✓ Colonne taux_execution ajoutée dans suivi_taches.")
else:
    print("→ Colonne taux_execution déjà présente, rien à faire.")

conn.commit()
conn.close()
print("Migration v4 terminée.")