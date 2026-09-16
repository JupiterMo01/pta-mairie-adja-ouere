from flask import render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import (db, Programme, PaiActivite, PaiProgramme, PaiProjet,
                    PeiActivite, SuiviTache)
from utils import get_annee, log_audit
from . import pei_bp


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _peut_editer():
    if current_user.role == 'admin_editeur':
        return True
    if current_user.role == 'direction' and current_user.direction \
            and current_user.direction.code == 'DAAF':
        return True
    if current_user.role == 'service' and current_user.service \
            and current_user.service.code == 'SBFC':
        return True
    return False


def _taux_sv(sv):
    if sv is None:             return 0.0
    if sv.statut == 'execute': return 100.0
    if sv.statut == 'en_cours': return float(sv.taux_execution or 0)
    return 0.0


def _load_suivi_global(annee_id):
    """Taux le plus récent par tâche (trimestre le plus élevé)."""
    suivis = (SuiviTache.query
              .filter_by(annee_id=annee_id)
              .order_by(SuiviTache.trimestre.desc())
              .all())
    result = {}
    for s in suivis:
        ex = result.get(s.tache_id)
        if ex is None:
            result[s.tache_id] = s
        elif (s.trimestre == ex.trimestre
              and s.service_id is not None
              and ex.service_id is None):
            result[s.tache_id] = s
    return result


def _wavg(pairs):
    """Moyenne pondérée [(valeur, poids)]. Renvoie 0.0 si poids total nul."""
    p = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / p, 1) if p else 0.0


def _build_pei_data(annee):
    suivi_map = _load_suivi_global(annee.id)

    # Toutes observations de l'année (tous trimestres)
    all_svs = SuiviTache.query.filter(
        SuiviTache.annee_id == annee.id,
        SuiviTache.observation.isnot(None)
    ).all()
    obs_map = {}
    for sv in all_svs:
        txt = (sv.observation or '').strip()
        if txt:
            obs_map.setdefault(sv.tache_id, []).append(txt)

    programmes = (Programme.query
                  .filter_by(annee_id=annee.id)
                  .order_by(Programme.numero)
                  .all())
    data = []
    gl_budget = gl_engage = gl_mandate = gl_paye = 0.0
    prog_num = 0

    for pg in programmes:
        pg_projets = []
        proj_num = 0

        for pj in pg.projets:
            inv_acts = [a for a in pj.activites
                        if a.type_activite
                        and 'investissement' in a.type_activite.lower()
                        and a.inclure_dans_pai is not False]
            if not inv_acts:
                continue

            proj_num += 1
            act_num = 0
            act_datas = []

            for act in inv_acts:
                act_num += 1

                # Taux physique : moyenne pondérée des tâches (poids PTA)
                task_pairs = []
                for t in act.taches:
                    task_pairs.append((_taux_sv(suivi_map.get(t.id)), t.poids or 0))
                taux_phys = _wavg(task_pairs) if task_pairs else 0.0

                # Observations compilées
                obs_parts = []
                for t in act.taches:
                    obs_parts.extend(obs_map.get(t.id, []))
                obs_compiled = ', '.join(obs_parts)

                # PeiActivite (crée si absent)
                pei = PeiActivite.query.filter_by(activite_id=act.id).first()
                if not pei:
                    pei = PeiActivite(activite_id=act.id)
                    db.session.add(pei)

                budget   = act.budget_total
                engage   = pei.montant_engage  or 0.0
                mandate  = pei.montant_mandate or 0.0
                paye     = pei.montant_paye    or 0.0

                taux_eng  = round(engage  / budget  * 100, 1) if budget  else 0.0
                taux_mand = round(mandate / engage  * 100, 1) if engage  else 0.0
                taux_pay  = round(paye    / engage  * 100, 1) if engage  else 0.0

                pai_extra = act.pai_extra
                poids = int(pai_extra.poids_pai or 0) if pai_extra else 0

                gl_budget  += budget
                gl_engage  += engage
                gl_mandate += mandate
                gl_paye    += paye

                act_datas.append({
                    'activite':  act,
                    'act_num':   act_num,
                    'poids':     poids,
                    'taux_phys': taux_phys,
                    'budget':    budget,
                    'engage':    engage,
                    'mandate':   mandate,
                    'paye':      paye,
                    'taux_eng':  taux_eng,
                    'taux_mand': taux_mand,
                    'taux_pay':  taux_pay,
                    'obs':       obs_compiled,
                    'pei':       pei,
                })

            # Projet — agrégation par poids PAI activités
            pj_extra = PaiProjet.query.filter_by(projet_id=pj.id).first()
            pj_poids = int(pj_extra.poids_pai or 0) if pj_extra else 0

            pj_budget  = sum(ad['budget']  for ad in act_datas)
            pj_engage  = sum(ad['engage']  for ad in act_datas)
            pj_mandate = sum(ad['mandate'] for ad in act_datas)
            pj_paye    = sum(ad['paye']    for ad in act_datas)

            pj_taux_phys = _wavg([(ad['taux_phys'], ad['poids']) for ad in act_datas])
            pj_taux_eng  = _wavg([(ad['taux_eng'],  ad['poids']) for ad in act_datas])
            pj_taux_mand = _wavg([(ad['taux_mand'], ad['poids']) for ad in act_datas])
            pj_taux_pay  = _wavg([(ad['taux_pay'],  ad['poids']) for ad in act_datas])

            pg_projets.append({
                'projet':     pj,
                'proj_num':   proj_num,
                'poids':      pj_poids,
                'activites':  act_datas,
                'budget':     pj_budget,
                'engage':     pj_engage,
                'mandate':    pj_mandate,
                'paye':       pj_paye,
                'taux_phys':  pj_taux_phys,
                'taux_eng':   pj_taux_eng,
                'taux_mand':  pj_taux_mand,
                'taux_pay':   pj_taux_pay,
            })

        if not pg_projets:
            continue

        prog_num += 1
        pg_extra = PaiProgramme.query.filter_by(programme_id=pg.id).first()
        pg_poids = int(pg_extra.poids_pai or 0) if pg_extra else 0

        pg_budget  = sum(pjd['budget']  for pjd in pg_projets)
        pg_engage  = sum(pjd['engage']  for pjd in pg_projets)
        pg_mandate = sum(pjd['mandate'] for pjd in pg_projets)
        pg_paye    = sum(pjd['paye']    for pjd in pg_projets)

        pg_taux_phys = _wavg([(pjd['taux_phys'], pjd['poids']) for pjd in pg_projets])
        pg_taux_eng  = _wavg([(pjd['taux_eng'],  pjd['poids']) for pjd in pg_projets])
        pg_taux_mand = _wavg([(pjd['taux_mand'], pjd['poids']) for pjd in pg_projets])
        pg_taux_pay  = _wavg([(pjd['taux_pay'],  pjd['poids']) for pjd in pg_projets])

        data.append({
            'programme':  pg,
            'prog_num':   prog_num,
            'poids':      pg_poids,
            'projets':    pg_projets,
            'budget':     pg_budget,
            'engage':     pg_engage,
            'mandate':    pg_mandate,
            'paye':       pg_paye,
            'taux_phys':  pg_taux_phys,
            'taux_eng':   pg_taux_eng,
            'taux_mand':  pg_taux_mand,
            'taux_pay':   pg_taux_pay,
        })

    db.session.commit()

    gl_taux_phys = _wavg([(pd['taux_phys'], pd['poids']) for pd in data]) if data else 0.0
    gl_taux_eng  = _wavg([(pd['taux_eng'],  pd['poids']) for pd in data]) if data else 0.0
    gl_taux_mand = _wavg([(pd['taux_mand'], pd['poids']) for pd in data]) if data else 0.0
    gl_taux_pay  = _wavg([(pd['taux_pay'],  pd['poids']) for pd in data]) if data else 0.0

    totaux = {
        'budget':     gl_budget,
        'engage':     gl_engage,
        'mandate':    gl_mandate,
        'paye':       gl_paye,
        'taux_phys':  gl_taux_phys,
        'taux_eng':   gl_taux_eng,
        'taux_mand':  gl_taux_mand,
        'taux_pay':   gl_taux_pay,
    }
    return data, totaux


# ─── Routes ──────────────────────────────────────────────────────────────────

@pei_bp.route('/')
@login_required
def index():
    annee = get_annee()
    if not annee:
        abort(404)
    if not annee.actif and current_user.role not in ('admin_editeur', 'admin_lecteur'):
        abort(403)

    data, totaux = _build_pei_data(annee)
    go = request.args.get('go', '')

    return render_template(
        'pei/index.html',
        annee=annee,
        data=data,
        totaux=totaux,
        peut_editer=_peut_editer(),
        go=go,
    )


@pei_bp.route('/edit/<int:activite_id>', methods=['POST'])
@login_required
def edit_montants(activite_id):
    if not _peut_editer():
        abort(403)

    annee = get_annee()
    if not annee:
        abort(404)

    pei = PeiActivite.query.filter_by(activite_id=activite_id).first()
    if not pei:
        abort(404)

    budget = pei.activite.budget_total

    try:
        engage  = float(request.form.get('montant_engage',  0) or 0)
        mandate = float(request.form.get('montant_mandate', 0) or 0)
        paye    = float(request.form.get('montant_paye',    0) or 0)
    except ValueError:
        flash("Valeurs invalides.", 'danger')
        return redirect(url_for('pei.index'))

    # Contraintes
    if engage > budget:
        flash(f"Le montant engagé ({engage:,.0f}) ne peut pas dépasser le coût total ({budget:,.0f}).", 'warning')
        return redirect(url_for('pei.index', go=f'act-{activite_id}'))
    if mandate > engage:
        flash(f"Le montant mandaté ({mandate:,.0f}) ne peut pas dépasser le montant engagé ({engage:,.0f}).", 'warning')
        return redirect(url_for('pei.index', go=f'act-{activite_id}'))
    if paye > engage:
        flash(f"Le montant payé ({paye:,.0f}) ne peut pas dépasser le montant engagé ({engage:,.0f}).", 'warning')
        return redirect(url_for('pei.index', go=f'act-{activite_id}'))

    pei.montant_engage  = engage
    pei.montant_mandate = mandate
    pei.montant_paye    = paye
    db.session.commit()

    log_audit('pei_edit',
              f"Activité {pei.activite.code} — Engagé {engage:,.0f} / "
              f"Mandaté {mandate:,.0f} / Payé {paye:,.0f} F CFA")

    return redirect(url_for('pei.index', go=f'act-{activite_id}'))
