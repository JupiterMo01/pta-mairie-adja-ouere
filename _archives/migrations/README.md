# Scripts de migration SQLite — archivés

Ces scripts ont été exécutés **une seule fois** sur la base de données de production
pour faire évoluer le schéma au fil des versions du projet.

Ils sont conservés ici **uniquement pour la traçabilité historique**.
Ne jamais les ré-exécuter : tous leurs changements sont déjà présents dans `models.py`
et dans la base de données `instance/pta_mairie.db`.

| Fichier | Description |
|---------|-------------|
| migrate_db.py | v2 — colonnes financement, objectifs, associations direction |
| migrate_se.py | Structures externes |
| migrate_v3.py | v3 — évolution schéma |
| migrate_v4.py | v4 — évolution schéma |
| migrate_v5.py | v5 — évolution schéma |
| migrate_v6.py | v6 — évolution schéma |
| migrate_v7.py | v7 — évolution schéma |
| migrate_v8.py | v8 — évolution schéma |
