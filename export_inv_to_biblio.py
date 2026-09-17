"""
export_inv_to_biblio.py
Exporte toutes les activités d'investissement du PTA actif vers la bibliothèque.
- Saute les activités dont le nom existe déjà en biblio (idempotent).
- Copie aussi toutes les tâches de chaque activité.
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

    # ── Année active ──────────────────────────────────────────────────────────
    annee = Annee.query.filter_by(actif=True).first()
    if not annee:
        print("❌  Aucune année active trouvée.")
        sys.exit(1)
    print(f"📅  Année active : {annee.annee}\n")

    # ── Activités d'investissement de cette année ─────────────────────────────
    programmes = Programme.query.filter_by(annee_id=annee.id).all()
    inv_acts = []
    for pg in programmes:
        for pj in pg.projets:
            for act in pj.activites:
                if (act.type_activite
                        and 'investissement' in act.type_activite.lower()
                        and act.inclure_dans_pai is not False):
                    inv_acts.append(act)

    print(f"🔍  {len(inv_acts)} activité(s) d'investissement trouvée(s).\n")

    crees = 0
    ignores = 0

    for act in inv_acts:
        # Doublon par nom exact ?
        existing = BiblioActivite.query.filter_by(nom=act.nom).first()
        if existing:
            print(f"  ⏭  IGNORÉ (déjà en biblio) : {act.code} — {act.nom}")
            ignores += 1
            continue

        # ── Créer BiblioActivite ──────────────────────────────────────────────
        ba = BiblioActivite(
            nom                    = act.nom,
            description            = act.description,
            direction_responsable_id = act.direction_responsable_id,
            mode_execution         = act.mode_execution,
            type_activite          = act.type_activite,
            imputation_budgetaire  = act.imputation_budgetaire,
            periode_debut          = act.periode_debut,
            periode_fin            = act.periode_fin,
            poids                  = act.poids or 0.0,
            ressources_propres     = act.ressources_propres or 0.0,
            fadec_affecte          = act.fadec_affecte or 0.0,
            fadec_non_affecte      = act.fadec_non_affecte or 0.0,
            autres_partenaires     = act.autres_partenaires or 0.0,
            autres_fonds           = act.autres_fonds or 0.0,
            details_financement    = act.details_financement,
            acteurs_externes       = act.acteurs_externes,
        )
        # Relations many-to-many
        ba.services_associes    = list(act.services_intervenants)
        ba.directions_associees = list(act.directions_associees)

        db.session.add(ba)
        db.session.flush()  # obtenir ba.id avant de créer les tâches

        # ── Créer BiblioTache pour chaque tâche ──────────────────────────────
        for t in act.taches:
            bt = BiblioTache(
                biblio_activite_id     = ba.id,
                numero                 = t.numero,
                nom                    = t.nom,
                description            = t.description,
                poids                  = t.poids or 0.0,
                service_responsable_id = t.service_responsable_id,
                imputation_budgetaire  = t.imputation_budgetaire,
                ressources_propres     = t.ressources_propres or 0.0,
                fadec_affecte          = t.fadec_affecte or 0.0,
                fadec_non_affecte      = t.fadec_non_affecte or 0.0,
                autres_partenaires     = t.autres_partenaires or 0.0,
                autres_fonds           = t.autres_fonds or 0.0,
                details_financement    = t.details_financement,
                acteurs_externes       = t.acteurs_externes,
                mode_execution         = t.mode_execution,
                periode_debut          = t.periode_debut,
                periode_fin            = t.periode_fin,
                observations           = t.observations,
                direction_responsable_id = t.direction_responsable_id,
            )
            bt.services_concernes    = list(t.services_concernes)
            bt.directions_associees  = list(t.directions_associees)
            db.session.add(bt)

        print(f"  ✅  {act.code} — {act.nom}  ({len(act.taches)} tâche(s))")
        crees += 1

    db.session.commit()

    print(f"\n{'─'*60}")
    print(f"✅  Export terminé : {crees} activité(s) créée(s), {ignores} ignorée(s) (déjà en biblio).")
