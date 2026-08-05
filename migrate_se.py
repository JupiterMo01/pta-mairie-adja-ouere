"""Migration : création des tables structures_externes et associations."""
import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), 'instance', 'pta_mairie.db')

conn = sqlite3.connect(DB)
c = conn.cursor()

c.executescript('''
CREATE TABLE IF NOT EXISTS structures_externes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom VARCHAR(200) NOT NULL,
    type_org VARCHAR(100),
    description TEXT
);

CREATE TABLE IF NOT EXISTS activite_struct_ext (
    activite_id INTEGER NOT NULL,
    struct_ext_id INTEGER NOT NULL,
    PRIMARY KEY (activite_id, struct_ext_id),
    FOREIGN KEY (activite_id) REFERENCES activites(id) ON DELETE CASCADE,
    FOREIGN KEY (struct_ext_id) REFERENCES structures_externes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tache_struct_ext (
    tache_id INTEGER NOT NULL,
    struct_ext_id INTEGER NOT NULL,
    PRIMARY KEY (tache_id, struct_ext_id),
    FOREIGN KEY (tache_id) REFERENCES taches(id) ON DELETE CASCADE,
    FOREIGN KEY (struct_ext_id) REFERENCES structures_externes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS biblio_act_struct_ext (
    biblio_act_id INTEGER NOT NULL,
    struct_ext_id INTEGER NOT NULL,
    PRIMARY KEY (biblio_act_id, struct_ext_id),
    FOREIGN KEY (biblio_act_id) REFERENCES biblio_activites(id) ON DELETE CASCADE,
    FOREIGN KEY (struct_ext_id) REFERENCES structures_externes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS biblio_tache_struct_ext (
    biblio_tache_id INTEGER NOT NULL,
    struct_ext_id INTEGER NOT NULL,
    PRIMARY KEY (biblio_tache_id, struct_ext_id),
    FOREIGN KEY (biblio_tache_id) REFERENCES biblio_taches(id) ON DELETE CASCADE,
    FOREIGN KEY (struct_ext_id) REFERENCES structures_externes(id) ON DELETE CASCADE
);
''')

conn.commit()
conn.close()
print("Migration terminée — tables structures_externes et associations créées.")