"""Migration v7 : ajout de la colonne observations dans biblio_taches."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'pta_mairie.db')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Vérifier si la colonne existe déjà
cur.execute("PRAGMA table_info(biblio_taches)")
colonnes = [row[1] for row in cur.fetchall()]

if 'observations' not in colonnes:
    cur.execute("ALTER TABLE biblio_taches ADD COLUMN observations TEXT")
    print("Colonne observations ajoutée à biblio_taches.")
else:
    print("Colonne observations déjà présente — rien à faire.")

conn.commit()
conn.close()
print("Migration v7 terminée.")
