import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
os.environ.setdefault('SECRET_KEY', 'dev123')

from app import create_app
from models import db, Activite

app = create_app()
with app.app_context():

    def process(act_id, engagement_num, paiement_num, poids_map):
        """
        - Transfère le montant de la tâche paiement vers tâche engagement
        - Supprime toutes les tâches après engagement_num
        - Applique les nouveaux poids (dict {numero: poids})
        """
        a = db.session.get(Activite, act_id)
        taches = {t.numero: t for t in a.taches}

        t_eng = taches[engagement_num]
        t_pay = taches[paiement_num]

        # Transférer montants de paiement vers engagement
        t_eng.ressources_propres   = (t_eng.ressources_propres   or 0) + (t_pay.ressources_propres   or 0)
        t_eng.fadec_affecte        = (t_eng.fadec_affecte        or 0) + (t_pay.fadec_affecte        or 0)
        t_eng.fadec_non_affecte    = (t_eng.fadec_non_affecte    or 0) + (t_pay.fadec_non_affecte    or 0)
        t_eng.autres_partenaires   = (t_eng.autres_partenaires   or 0) + (t_pay.autres_partenaires   or 0)
        t_eng.autres_fonds         = (t_eng.autres_fonds         or 0) + (t_pay.autres_fonds         or 0)

        # Supprimer toutes les tâches dont le numéro > engagement_num
        to_delete = [t for t in a.taches if t.numero > engagement_num]
        for t in to_delete:
            db.session.delete(t)
        db.session.flush()

        # Appliquer nouveaux poids
        for t in a.taches:
            if t.numero in poids_map:
                t.poids = float(poids_map[t.numero])

        # Vérification
        total = sum(t.poids for t in a.taches)
        print(f"\n[{act_id}] {a.code}  {a.nom[:70]}")
        print(f"  tâches conservées : {len(a.taches)}  |  total poids = {total}")
        for t in sorted(a.taches, key=lambda x: x.numero):
            rp = t.ressources_propres or 0
            fn = t.fadec_non_affecte or 0
            fa = t.fadec_affecte or 0
            print(f"  #{t.numero}  poids={t.poids}  rp={rp}  fn={fn}  {t.nom[:60]}")

    # ── 1.2.3 Ikpinlè boutiques construction (628) ──
    # engagement=#7, paiement=#19 (fn=6 473 462)
    # 7 tâches → poids objectifs
    process(628, engagement_num=7, paiement_num=19, poids_map={
        1: 5,   # Réservation de crédit
        2: 12,  # Élaboration des spécifications
        3: 12,  # Elaboration et diffusion demande de cotation
        4: 10,  # Réception des offres
        5: 18,  # Ouverture et analyse comparative
        6: 20,  # Notification et signature du contrat
        7: 23,  # Engagement du marché
    })  # total = 100

    # ── 1.2.4 Ikpinlè boutiques suivi (629) ──
    # engagement=#7, paiement=#18 (fn=500 000)
    process(629, engagement_num=7, paiement_num=18, poids_map={
        1: 5,   # Réservation de crédit
        2: 12,  # Élaboration des spécifications
        3: 12,  # Elaboration et diffusion dossier AO
        4: 10,  # Réception des offres
        5: 18,  # Ouverture et analyse comparative
        6: 20,  # Notification et signature du contrat
        7: 23,  # Engagement du marché
    })  # total = 100

    # ── 3.1.16 Etude faisabilité EPP (569) ──
    # engagement=#7, paiement=#18 (rp=7 255 689)
    process(569, engagement_num=7, paiement_num=18, poids_map={
        1: 4,   # Reservation de credit
        2: 12,  # Elaboration du TDR
        3: 10,  # Avis d'appel à manifestation d'intérêt
        4: 12,  # Demande de proposition de renseignement et de prix
        5: 20,  # Ouverture, Analyse, Evaluation et Sélection
        6: 18,  # Attribution et signature du marché
        7: 24,  # Engagement du marché
    })  # total = 100

    # ── 3.1.20 Construction EM Houédamè (632) ──
    # engagement=#9, paiement=#21 (fn=32 951 312)
    # 9 tâches conservées
    process(632, engagement_num=9, paiement_num=21, poids_map={
        1: 4,   # Réservation de crédit
        2: 9,   # Élaboration des spécifications
        3: 9,   # Elaboration et diffusion dossier AO ouvert
        4: 7,   # Réception des offres
        5: 10,  # Ouverture et analyse comparative
        6: 12,  # Contrôle et approbation CCMP
        7: 12,  # Contrôle et approbation DDCMP
        8: 16,  # Notification et signature du contrat
        9: 21,  # Engagement du marché
    })  # total = 100

    # ── 3.1.21 Suivi construction EM Houédamè (633) ──
    # engagement=#7, paiement=#18 (fn=1 500 000)
    process(633, engagement_num=7, paiement_num=18, poids_map={
        1: 5,   # Réservation de crédit
        2: 12,  # Élaboration des spécifications
        3: 12,  # Elaboration et diffusion dossier AO
        4: 10,  # Réception des offres
        5: 18,  # Ouverture et analyse comparative
        6: 20,  # Notification et signature du contrat
        7: 23,  # Engagement du marché
    })  # total = 100

    # ── 3.1.22 124 tables-bancs (634) ──
    # engagement=#7, paiement=#13 (fn=8 742 740)
    process(634, engagement_num=7, paiement_num=13, poids_map={
        1: 5,   # Reservation de credit
        2: 12,  # Elaboration des spécifications
        3: 12,  # Elaboration du dossier de demande de cotation
        4: 10,  # Lancement de la demande de cotation
        5: 20,  # Ouverture, Analyse, Evaluation et Sélection
        6: 18,  # Attribution et signature du marché
        7: 23,  # Engagement du marché
    })  # total = 100

    db.session.commit()
    print("\nOK — commit réussi")
