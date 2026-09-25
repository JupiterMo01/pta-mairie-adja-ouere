import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
os.environ.setdefault('SECRET_KEY', 'dev123')

from app import create_app
from models import db, Activite

app = create_app()
with app.app_context():

    def set_periodes(act_id, act_debut, act_fin, periodes_taches):
        a = db.session.get(Activite, act_id)
        a.periode_debut = act_debut
        a.periode_fin   = act_fin
        for t in a.taches:
            if t.numero in periodes_taches:
                t.periode_debut, t.periode_fin = periodes_taches[t.numero]

    # ── 1. Restaurer poids d'origine 557 et 558 (depuis biblio) ──
    poids_557 = {1:7,2:17,3:3,4:3,5:3,6:3,7:12,8:16,9:12,10:12,11:12}
    a557 = db.session.get(Activite, 557)
    for t in a557.taches:
        if t.numero in poids_557:
            t.poids = float(poids_557[t.numero])

    poids_558 = {1:5.0,2:19.25,3:19.25,4:19.25,5:19.25,6:9.0,7:9.0}
    a558 = db.session.get(Activite, 558)
    for t in a558.taches:
        if t.numero in poids_558:
            t.poids = float(poids_558[t.numero])

    # ── 2. Ikpinlè construction (560) — Juin → Décembre, 18 tâches ──
    set_periodes(560, 'Juin', 'Décembre', {
        1:  ('Juin',      'Juin'),
        2:  ('Juin',      'Juin'),
        3:  ('Juin',      'Juillet'),
        4:  ('Juillet',   'Juillet'),
        5:  ('Juillet',   'Août'),
        6:  ('Août',      'Août'),
        7:  ('Août',      'Août'),
        8:  ('Août',      'Septembre'),
        9:  ('Septembre', 'Septembre'),
        10: ('Septembre', 'Octobre'),
        11: ('Octobre',   'Octobre'),
        12: ('Octobre',   'Novembre'),
        13: ('Novembre',  'Novembre'),
        14: ('Novembre',  'Novembre'),
        15: ('Novembre',  'Décembre'),
        16: ('Décembre',  'Décembre'),
        17: ('Décembre',  'Décembre'),
        18: ('Novembre',  'Décembre'),
    })

    # ── 3. Ikpinlè suivi/contrôle (561) — Juin → Décembre, 14 tâches ──
    set_periodes(561, 'Juin', 'Décembre', {
        1:  ('Juin',      'Juin'),
        2:  ('Juin',      'Juin'),
        3:  ('Juin',      'Juillet'),
        4:  ('Juillet',   'Juillet'),
        5:  ('Juillet',   'Août'),
        6:  ('Août',      'Août'),
        7:  ('Août',      'Août'),
        8:  ('Août',      'Septembre'),
        9:  ('Septembre', 'Octobre'),
        10: ('Octobre',   'Octobre'),
        11: ('Octobre',   'Novembre'),
        12: ('Novembre',  'Novembre'),
        13: ('Novembre',  'Novembre'),
        14: ('Novembre',  'Décembre'),
    })

    # ── 4. Illoulofin construction (564) — Juillet → Décembre, 18 tâches ──
    set_periodes(564, 'Juillet', 'Décembre', {
        1:  ('Juillet',   'Juillet'),
        2:  ('Juillet',   'Juillet'),
        3:  ('Juillet',   'Août'),
        4:  ('Août',      'Août'),
        5:  ('Août',      'Août'),
        6:  ('Août',      'Septembre'),
        7:  ('Septembre', 'Septembre'),
        8:  ('Septembre', 'Septembre'),
        9:  ('Septembre', 'Octobre'),
        10: ('Octobre',   'Octobre'),
        11: ('Octobre',   'Novembre'),
        12: ('Novembre',  'Novembre'),
        13: ('Novembre',  'Novembre'),
        14: ('Novembre',  'Novembre'),
        15: ('Novembre',  'Décembre'),
        16: ('Décembre',  'Décembre'),
        17: ('Décembre',  'Décembre'),
        18: ('Novembre',  'Décembre'),
    })

    # ── 5. Illoulofin suivi/contrôle (565) — Juillet → Décembre, 14 tâches ──
    set_periodes(565, 'Juillet', 'Décembre', {
        1:  ('Juillet',   'Juillet'),
        2:  ('Juillet',   'Juillet'),
        3:  ('Juillet',   'Août'),
        4:  ('Août',      'Août'),
        5:  ('Août',      'Septembre'),
        6:  ('Septembre', 'Septembre'),
        7:  ('Septembre', 'Septembre'),
        8:  ('Septembre', 'Octobre'),
        9:  ('Octobre',   'Octobre'),
        10: ('Octobre',   'Novembre'),
        11: ('Novembre',  'Novembre'),
        12: ('Novembre',  'Novembre'),
        13: ('Novembre',  'Décembre'),
        14: ('Novembre',  'Décembre'),
    })

    # ── 6. Tables-bancs (568) — Mars → Août, 18 tâches ──
    set_periodes(568, 'Mars', 'Août', {
        1:  ('Mars',  'Mars'),
        2:  ('Mars',  'Mars'),
        3:  ('Mars',  'Avril'),
        4:  ('Avril', 'Avril'),
        5:  ('Avril', 'Avril'),
        6:  ('Avril', 'Mai'),
        7:  ('Mai',   'Mai'),
        8:  ('Mai',   'Mai'),
        9:  ('Mai',   'Juin'),
        10: ('Juin',  'Juin'),
        11: ('Juin',  'Juillet'),
        12: ('Juillet','Juillet'),
        13: ('Juillet','Août'),
        14: ('Août',  'Août'),
        15: ('Août',  'Août'),
        16: ('Août',  'Août'),
        17: ('Août',  'Août'),
        18: ('Juillet','Août'),
    })

    # ── 7. Igbo-Aidin construction (570) — Août → Décembre, 18 tâches ──
    set_periodes(570, 'Août', 'Décembre', {
        1:  ('Août',      'Août'),
        2:  ('Août',      'Août'),
        3:  ('Août',      'Septembre'),
        4:  ('Septembre', 'Septembre'),
        5:  ('Septembre', 'Septembre'),
        6:  ('Septembre', 'Octobre'),
        7:  ('Octobre',   'Octobre'),
        8:  ('Octobre',   'Octobre'),
        9:  ('Octobre',   'Novembre'),
        10: ('Novembre',  'Novembre'),
        11: ('Novembre',  'Novembre'),
        12: ('Novembre',  'Décembre'),
        13: ('Décembre',  'Décembre'),
        14: ('Décembre',  'Décembre'),
        15: ('Décembre',  'Décembre'),
        16: ('Décembre',  'Décembre'),
        17: ('Décembre',  'Décembre'),
        18: ('Novembre',  'Décembre'),
    })

    # ── 8. Igbo-Aidin suivi/contrôle (571) — Août → Décembre, 14 tâches ──
    set_periodes(571, 'Août', 'Décembre', {
        1:  ('Août',      'Août'),
        2:  ('Août',      'Août'),
        3:  ('Août',      'Septembre'),
        4:  ('Septembre', 'Septembre'),
        5:  ('Septembre', 'Septembre'),
        6:  ('Septembre', 'Octobre'),
        7:  ('Octobre',   'Octobre'),
        8:  ('Octobre',   'Octobre'),
        9:  ('Octobre',   'Novembre'),
        10: ('Novembre',  'Novembre'),
        11: ('Novembre',  'Décembre'),
        12: ('Décembre',  'Décembre'),
        13: ('Décembre',  'Décembre'),
        14: ('Novembre',  'Décembre'),
    })

    db.session.commit()

    # ── Résumé ──
    infos = [
        (557, 'EGBE achèvement — poids restaurés'),
        (558, 'EGBE contrôle — poids restaurés'),
        (560, 'Ikpinlè construction'),
        (561, 'Ikpinlè suivi'),
        (564, 'Illoulofin construction'),
        (565, 'Illoulofin suivi'),
        (568, 'Tables-bancs'),
        (570, 'Igbo-Aidin construction'),
        (571, 'Igbo-Aidin suivi'),
    ]
    for act_id, label in infos:
        a = db.session.get(Activite, act_id)
        taches = sorted(a.taches, key=lambda x: x.numero)
        print(f"\n{label}  —  {a.periode_debut} → {a.periode_fin}")
        for t in taches:
            print(f"  #{t.numero}  poids={t.poids}  [{t.periode_debut} → {t.periode_fin}]")

    print("\nOK")
