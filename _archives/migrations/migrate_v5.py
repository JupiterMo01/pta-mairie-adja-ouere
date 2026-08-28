"""
migrate_v5.py
=============
Crée la table audit_log (journal d'audit).

Usage :
    python migrate_v5.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'pta_mairie.db')

SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    horodatage  DATETIME NOT NULL DEFAULT (datetime('now')),
    user_id     INTEGER  REFERENCES users(id) ON DELETE SET NULL,
    user_nom    VARCHAR(150),
    user_role   VARCHAR(30),
    action      VARCHAR(80) NOT NULL,
    details     TEXT,
    ip          VARCHAR(45)
);
"""

INDEX = "CREATE INDEX IF NOT EXISTS ix_audit_log_horodatage ON audit_log (horodatage DESC);"

def main():
    print(f"Base : {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("ERREUR : base introuvable.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute(SQL)
    cur.execute(INDEX)
    conn.commit()
    conn.close()

    print("Table audit_log créée (ou déjà existante). Migration v5 terminée.")

if __name__ == '__main__':
    main()
