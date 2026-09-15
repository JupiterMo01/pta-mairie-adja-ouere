"""
migrate_pai.py
──────────────
Migration : remplace les 3 tables PAI autonomes par une seule table
pai_activites liée directement à la table activites du PTA.

Usage :  python migrate_pai.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from models import db

def run():
    app = create_app()
    with app.app_context():
        print("Migration PAI : restructuration des tables...")

        with db.engine.connect() as conn:
            from sqlalchemy import text

            # Désactiver temporairement les contraintes FK (SQLite)
            conn.execute(text("PRAGMA foreign_keys = OFF"))
            conn.commit()

            # Supprimer les anciennes tables PAI
            for table in ('pai_activites', 'pai_projets', 'pai_programmes'):
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                    conn.commit()
                    print(f"  Table '{table}' supprimée.")
                except Exception as e:
                    print(f"  Avertissement pour '{table}' : {e}")

            # Réactiver les contraintes FK
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.commit()

        # Créer la nouvelle table pai_activites (via SQLAlchemy)
        db.create_all()
        print("  Nouvelle table 'pai_activites' créée.")
        print("\nMigration terminée. La table pai_activites est maintenant liée")
        print("directement aux activites d'investissement du PTA.")
        print("Accès : /pai/")

if __name__ == '__main__':
    run()
