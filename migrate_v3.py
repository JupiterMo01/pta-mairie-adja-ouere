"""
Migration v3 — Ajout de type_activite dans biblio_activites.
Exécuter UNE SEULE FOIS : python migrate_v3.py
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'instance', 'pta_mairie.db')

conn = sqlite3.connect(DB)
cur = conn.cursor()
print("=== Migration v3 ===")

# Vérifier si la colonne existe déjà
cur.execute("PRAGMA table_info(biblio_activites)")
existing = [r[1] for r in cur.fetchall()]

if 'type_activite' not in existing:
    cur.execute(
        "ALTER TABLE biblio_activites ADD COLUMN type_activite TEXT "
        "DEFAULT 'Activité de fonctionnement'"
    )
    # Mettre à jour les lignes existantes avec la valeur par défaut
    cur.execute(
        "UPDATE biblio_activites SET type_activite = 'Activité de fonctionnement' "
        "WHERE type_activite IS NULL"
    )
    print("  + biblio_activites.type_activite")
else:
    print("  = biblio_activites.type_activite déjà présente, rien à faire.")

conn.commit()
conn.close()
print("✅ Migration v3 terminée.")
