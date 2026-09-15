"""
import_pai_nouveau_format.py
─────────────────────────────
Crée les tables pai_programmes / pai_projets / pai_activites
et les remplit depuis le fichier Excel PAI_2026_Nouveau_Format.xlsx.

Usage :  python import_pai_nouveau_format.py
"""

import re
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from app import create_app
from models import db, Annee, PaiProgramme, PaiProjet, PaiActivite

EXCEL_PATH = (
    r"C:\Users\HP\Desktop\Jupiter\Documents basiques"
    r"\Evaluation\Format new\PAI_2026_Nouveau_Format.xlsx"
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def parse_poids(val):
    """Retourne le poids en pourcentage (ex. 0.3 → 30.0, '5%' → 5.0)."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        v = float(val)
        return round(v * 100, 2) if v <= 1.0 else round(v, 2)
    s = str(val).strip().replace('%', '').replace(',', '.')
    try:
        v = float(s)
        return round(v * 100, 2) if v <= 1.0 else round(v, 2)
    except ValueError:
        return 0.0


def parse_float(val):
    """Retourne un flottant ou 0.0."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def is_prog(code):
    """Code de type '1', '2', '3', '4'."""
    return bool(code and re.fullmatch(r'\d+', str(code).strip()))


def is_proj(code):
    """Code de type '1.1', '2.3'."""
    return bool(code and re.fullmatch(r'\d+\.\d+', str(code).strip()))


def is_act(code):
    """Code de type '1.1.1', '3.2.5'."""
    return bool(code and re.fullmatch(r'\d+\.\d+\.\d+', str(code).strip()))


# ─── Import principal ─────────────────────────────────────────────────────────

def run():
    app = create_app()
    with app.app_context():
        # Créer les tables si elles n'existent pas encore
        db.create_all()

        # Récupérer l'année active
        annee = Annee.query.filter_by(actif=True).first()
        if not annee:
            print("❌  Aucune année active trouvée en base. Créez d'abord une année.")
            return

        print(f"📅  Année active : {annee.annee} (id={annee.id})")

        # Supprimer les données existantes pour cette année (idempotent)
        existing = PaiProgramme.query.filter_by(annee_id=annee.id).all()
        for pg in existing:
            db.session.delete(pg)
        db.session.flush()
        print("🗑️   Données PAI précédentes supprimées pour cette année.")

        # Lire le fichier Excel
        wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
        ws = wb['PAI 2026']

        # Colonnes (0-indexed, la feuille commence à col B = index 1)
        # [1]=Code [2]=Nom [3]=Loc [4]=Poids [5]=Indicateurs [6]=Période
        # [7]=Struct.Resp [8]=Struct.Assoc [9]=FP [10]=FADeC type [11]=Montant FADeC
        # [12]=Autres PTFs [13]=Coût total [14]=Observations

        current_prog = None
        current_proj = None
        nb_prog = nb_proj = nb_act = 0

        for row in ws.iter_rows(min_row=11, values_only=True):
            code = row[1]
            if not code:
                continue
            code = str(code).strip()
            nom  = str(row[2]).strip() if row[2] else ''

            # ── Programme ──
            if is_prog(code):
                # Nettoyer le nom (ex. "Programme 1 : DEVELOPP..." → garder tel quel)
                # On extrait juste la partie après "Programme X : "
                clean_nom = re.sub(r'^Programme\s+\d+\s*:\s*', '', nom).strip() or nom
                poids = parse_poids(row[4])
                current_prog = PaiProgramme(
                    annee_id=annee.id,
                    numero=int(code),
                    nom=clean_nom,
                    poids=poids / 100,   # stocké en décimal
                )
                db.session.add(current_prog)
                db.session.flush()
                current_proj = None
                nb_prog += 1
                print(f"  [PG {code}] {clean_nom[:60]}")

            # ── Projet ──
            elif is_proj(code) and current_prog:
                clean_nom = re.sub(r'^Projet\s+[\d.]+\s*:\s*', '', nom).strip() or nom
                poids = parse_poids(row[4])
                parts = code.split('.')
                current_proj = PaiProjet(
                    programme_id=current_prog.id,
                    numero=int(parts[1]),
                    nom=clean_nom,
                    poids=poids / 100,
                )
                db.session.add(current_proj)
                db.session.flush()
                nb_proj += 1
                print(f"    [PJ {code}] {clean_nom[:60]}")

            # ── Activité ──
            elif is_act(code) and current_proj:
                parts = code.split('.')
                poids = parse_poids(row[4])

                fadec_type = str(row[10]).strip() if row[10] and str(row[10]).strip() not in ('-', 'None', '') else None

                act = PaiActivite(
                    projet_id=current_proj.id,
                    numero=int(parts[2]),
                    nom=nom,
                    localisation=str(row[3]).strip() if row[3] else None,
                    poids=poids,
                    indicateurs=str(row[5]).strip() if row[5] else None,
                    periode_execution=str(row[6]).strip() if row[6] else None,
                    structures_responsables=str(row[7]).strip() if row[7] else None,
                    structures_associees=str(row[8]).strip() if row[8] else None,
                    fp=parse_float(row[9]),
                    fadec_type=fadec_type,
                    montant_fadec=parse_float(row[11]),
                    autres_ptfs=parse_float(row[12]),
                    cout_total=parse_float(row[13]),
                    observations=str(row[14]).strip() if row[14] else None,
                )
                db.session.add(act)
                nb_act += 1
                print(f"      [ACT {code}] {nom[:60]}")

        db.session.commit()
        print(f"\n✅  Import terminé : {nb_prog} programmes, {nb_proj} projets, {nb_act} activités.")
        print(f"    → Accès : /pai/")


if __name__ == '__main__':
    run()
