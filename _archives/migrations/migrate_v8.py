"""
migrate_v8.py — Ajout du champ email dans la table users
Mairie d'Adja-Ouèrè — Système PTA
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'pta_mairie.db')

print(f"Base de données : {DB}")
conn = sqlite3.connect(DB)
cur  = conn.cursor()

cur.execute("SELECT name FROM pragma_table_info('users') WHERE name='email'")
if not cur.fetchone():
    cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
    print("✓ Colonne 'email' ajoutée à la table users.")
else:
    print("→ Colonne 'email' déjà présente, rien à faire.")

conn.commit()
conn.close()
print("Migration v8 terminée.")
