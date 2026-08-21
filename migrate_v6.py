"""
migrate_v6.py
=============
Ajoute periode_debut et periode_fin à la table biblio_taches.

Usage :
    python migrate_v6.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'pta_mairie.db')


def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())


def main():
    print(f"Base : {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("ERREUR : base introuvable.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    for col in ('periode_debut', 'periode_fin'):
        if col_exists(cur, 'biblio_taches', col):
            print(f"  Colonne {col} déjà présente — ignorée.")
        else:
            cur.execute(f"ALTER TABLE biblio_taches ADD COLUMN {col} VARCHAR(20)")
            print(f"  Colonne {col} ajoutée.")

    conn.commit()
    conn.close()
    print("Migration v6 terminée.")


if __name__ == '__main__':
    main()
