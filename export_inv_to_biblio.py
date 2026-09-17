"""
export_inv_to_biblio.py
Exporte TOUTES les activités d'investissement du PTA actif vers la bibliothèque.
Utilise exactement la même logique que le bouton « Exporter vers biblio » du PTA.
Les entrées existantes (même nom) sont REMPLACÉES (suppression + recréation).
Usage : python export_inv_to_biblio.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
os.environ.setdefault('SECRET_KEY', 'dev123')

from app import create_app
from models import db, Annee, Programme, Activite, BiblioActivite, BiblioTache

app = create_app()

with app.app_context():

    annee = Annee.query.filter_by(actif=True).first()
    if not annee:
        print("❌  Aucune année active trouvée.")
        sys.exit(1)
    print(f"📅  Année active : {annee.annee}\n")

    # Collect investment activities
    inv_acts = []
    for pg in Programme.query.filter_by(annee_id=annee.id).order_by(Programme.numero).all():
        for pj in pg.projets:
            for act in pj.activites:
                if (act.type_activite
                        and 'investissement' in act.type_activite.lower()
                        and act.inclure_dans_pai is not False):
                    inv_acts.append(act)

    print(f"🔍  {len(inv_acts)} activité(s) d'investissement trouvée(s).\n")

    remplacees = 0
    crees = 0

    for a in inv_acts:
        nom = a.nom

        # Supprimer l'entrée existante si elle existe
        existing = BiblioActivite.query.filter_by(nom=nom).first()
        if existing:
            db.session.delete(existing)
            db.session.flush()
            remplacees += 1
            tag = "🔄  REMPLACÉ"
        else:
            crees += 1
            tag = "✅  CRÉÉ    "

        # Même code que activite_export_biblio dans pta/routes.py
        ba = BiblioActivite(
            nom                      = nom,
            description              = a.description,
            direction_responsable_id = a.direction_responsable_id,
            mode_execution           = a.mode_execution or 'Direct',
            type_activite            = a.type_activite or 'Activité de fonctionnement',
            imputation_budgetaire    = a.imputation_budgetaire,
            periode_debut            = a.periode_debut,
            periode_fin              = a.periode_fin,
            poids                    = a.poids or 0.0,
            ressources_propres       = a.ressources_propres or 0,
            fadec_affecte            = a.fadec_affecte or 0,
            fadec_non_affecte        = a.fadec_non_affecte or 0,
            autres_partenaires       = a.autres_partenaires or 0,
            autres_fonds             = a.autres_fonds or 0,
            details_financement      = a.details_financement,
            acteurs_externes         = a.acteurs_externes,
        )
        ba.services_associes    = list(a.services_intervenants)
        ba.directions_associees = list(a.directions_associees)
        ba.structures_externes  = list(a.structures_externes)
        db.session.add(ba)
        db.session.flush()

        for t in sorted(a.taches, key=lambda x: x.numero):
            bt = BiblioTache(
                biblio_activite_id       = ba.id,
                numero                   = t.numero,
                nom                      = t.nom,
                description              = t.description,
                poids                    = t.poids or 0.0,
                service_responsable_id   = t.service_responsable_id,
                direction_responsable_id = t.direction_responsable_id,
                imputation_budgetaire    = t.imputation_budgetaire or 'NÉANT',
                mode_execution           = t.mode_execution or 'Direct',
                periode_debut            = t.periode_debut,
                periode_fin              = t.periode_fin,
                ressources_propres       = t.ressources_propres or 0,
                fadec_affecte            = t.fadec_affecte or 0,
                fadec_non_affecte        = t.fadec_non_affecte or 0,
                autres_partenaires       = t.autres_partenaires or 0,
                autres_fonds             = t.autres_fonds or 0,
                details_financement      = t.details_financement,
                acteurs_externes         = t.acteurs_externes,
            )
            bt.services_concernes   = list(t.services_concernes)
            bt.directions_associees = list(t.directions_associees)
            bt.structures_externes  = list(t.structures_externes)
            db.session.add(bt)

        print(f"  {tag} : {a.code} — {a.nom}  ({len(a.taches)} tâche(s))")

    db.session.commit()
    print(f"\n{'─'*60}")
    print(f"✅  Export terminé : {crees} créée(s), {remplacees} remplacée(s).")
