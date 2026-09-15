import io
from flask import render_template, abort, request, jsonify, Response
from flask_login import login_required, current_user
from models import db, Programme, Projet, Activite, PaiActivite, PaiProgramme, PaiProjet
from pai import pai_bp
from utils import get_annee


# ─── Helpers format ───────────────────────────────────────────────────────────


def _fmt_mil(v):
    """Formate un montant en milliers (français : espace milliers, virgule décimale, 0–3 décimales)."""
    if v == 0:
        return '0'
    s = f'{v:.3f}'.rstrip('0').rstrip('.')
    # Séparer partie entière et décimale
    if '.' in s:
        entier, dec = s.split('.')
        dec_part = ',' + dec
    else:
        entier, dec_part = s, ''
    # Séparateurs de milliers
    entier_fmt = ''
    for i, c in enumerate(reversed(entier)):
        if i and i % 3 == 0:
            entier_fmt = ' ' + entier_fmt
        entier_fmt = c + entier_fmt
    return entier_fmt + dec_part


def _fadec_label(src_fa, src_fn):
    """Libellé FADeC automatique avec montants en milliers."""
    a_fa = src_fa / 1000
    a_fn = src_fn / 1000
    if src_fa > 0 and src_fn > 0:
        return f'FA ({_fmt_mil(a_fa)}) + FNA ({_fmt_mil(a_fn)})'
    if src_fa > 0:
        return f'FA ({_fmt_mil(a_fa)})'
    if src_fn > 0:
        return f'FNA ({_fmt_mil(a_fn)})'
    return ''


# ─── Helper commun ────────────────────────────────────────────────────────────

def _build_pai_data(annee):
    """Construit la structure PAI. Poids lus depuis la DB (PaiProgramme, PaiProjet, PaiActivite)."""
    programmes = (
        Programme.query
        .filter_by(annee_id=annee.id)
        .order_by(Programme.numero)
        .all()
    )
    pai_data = []
    total_fp = total_fadec = total_ptfs = total_global = 0.0
    total_nb = 0
    prog_num = 0

    for pg in programmes:
        pg_projets = []
        proj_num = 0
        for pj in pg.projets:
            inv_acts = [a for a in pj.activites
                        if a.type_activite and 'investissement' in a.type_activite.lower()
                        and a.inclure_dans_pai is not False]
            if inv_acts:
                proj_num += 1
                for a in inv_acts:
                    total_fp     += a.src_rp
                    total_fadec  += a.src_fa + a.src_fn
                    total_ptfs   += a.src_ap + a.src_af
                    total_global += a.budget_total
                    total_nb     += 1
                pj_extra = PaiProjet.query.filter_by(projet_id=pj.id).first()
                pg_projets.append({
                    'projet':    pj,
                    'activites': inv_acts,
                    'proj_num':  proj_num,
                    'poids':     int(pj_extra.poids_pai or 0) if pj_extra else 0,
                })
        if pg_projets:
            prog_num += 1
            pg_extra = PaiProgramme.query.filter_by(programme_id=pg.id).first()
            pai_data.append({
                'programme': pg,
                'projets':   pg_projets,
                'prog_num':  prog_num,
                'poids':     int(pg_extra.poids_pai or 0) if pg_extra else 0,
            })

    return pai_data, total_fp, total_fadec, total_ptfs, total_global, total_nb


# ─── Routes ──────────────────────────────────────────────────────────────────

@pai_bp.route('/')
@login_required
def index():
    """Vue écran du PAI. Tous les utilisateurs pour l'année active ; admins seulement pour une année non active."""
    annee = get_annee()
    if not annee:
        abort(404)
    if not annee.actif and current_user.role not in ('admin_editeur', 'admin_lecteur'):
        abort(403)

    pai_data, total_fp, total_fadec, total_ptfs, total_global, total_nb = _build_pai_data(annee)

    # Création automatique des enregistrements pour les nouvelles activités/projets/programmes.
    # Poids importés depuis le PTA par défaut (modifiables ensuite).
    changed = False
    for pg_d in pai_data:
        pg = pg_d['programme']
        if not PaiProgramme.query.filter_by(programme_id=pg.id).first():
            db.session.add(PaiProgramme(programme_id=pg.id, poids_pai=0))
            changed = True
        for pj_d in pg_d['projets']:
            pj = pj_d['projet']
            if not PaiProjet.query.filter_by(projet_id=pj.id).first():
                db.session.add(PaiProjet(projet_id=pj.id, poids_pai=0))
                changed = True
            for act in pj_d['activites']:
                if not act.pai_extra:
                    extra = PaiActivite(activite_id=act.id)
                    extra.poids_pai = act.poids or 0.0
                    db.session.add(extra)
                    changed = True
    if changed:
        db.session.commit()
        pai_data, total_fp, total_fadec, total_ptfs, total_global, total_nb = _build_pai_data(annee)

    return render_template(
        'pai/index.html',
        annee=annee,
        pai_data=pai_data,
        total_fp=total_fp,
        total_fadec=total_fadec,
        total_ptfs=total_ptfs,
        total_global=total_global,
        total_nb=total_nb,
        can_edit=(current_user.role == 'admin_editeur'),
    )


@pai_bp.route('/print')
@login_required
def print_view():
    """Vue impression A4 paysage du PAI. Tous pour l'année active ; admins pour années non actives."""
    annee = get_annee()
    if not annee:
        abort(404)
    if not annee.actif and current_user.role not in ('admin_editeur', 'admin_lecteur'):
        abort(403)

    pai_data, total_fp, total_fadec, total_ptfs, total_global, total_nb = _build_pai_data(annee)

    return render_template(
        'pai/print.html',
        annee=annee,
        pai_data=pai_data,
        total_fp=total_fp,
        total_fadec=total_fadec,
        total_ptfs=total_ptfs,
        total_global=total_global,
    )


@pai_bp.route('/export')
@login_required
def export_excel():
    """Exporte le PAI en fichier Excel (.xlsx). Tous pour l'année active ; admins pour années non actives."""
    annee = get_annee()
    if not annee:
        abort(404)
    if not annee.actif and current_user.role not in ('admin_editeur', 'admin_lecteur'):
        abort(403)

    pai_data, total_fp, total_fadec, total_ptfs, total_global, _ = _build_pai_data(annee)

    import openpyxl
    import os as _os
    from flask import current_app
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'PAI {annee.annee}'

    def fill(hex_color):
        return PatternFill('solid', fgColor=hex_color)

    thin = Side(style='thin')
    bord = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left   = Alignment(horizontal='left',  vertical='center', wrap_text=True)

    # ── Lignes 1-3 : En-tête institutionnel (conforme PTA) ───────────────────
    # Gauche  A1:D3 : bandeau.png
    # Centre  E1:I3 : coordonnées (BP, Tél, Email)
    # Droite  J1:N3 : logo commune
    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 8
    ws.row_dimensions[3].height = 22

    ws.merge_cells('A1:D3')

    ws.merge_cells('E1:I3')
    _cc = ws['E1']
    _cc.value = "BP 02 Adja-Ouèrè\nTél : +229 01 61 91 96 12\nEmail : contact.adjaouere@mairie.bj"
    _cc.font = Font(bold=True, size=9)
    _cc.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    ws.merge_cells('J1:N3')

    _static_img = _os.path.join(current_app.root_path, 'static', 'img')
    try:
        from openpyxl.drawing.image import Image as _XLImg
        from PIL import Image as _PILImg
        import io as _imgio
        _band_path = _os.path.join(_static_img, 'bandeau.png')
        _logo_path = _os.path.join(_static_img, 'logo_commune.png')
        _H = 52
        if _os.path.exists(_band_path):
            _buf = _imgio.BytesIO()
            with _PILImg.open(_band_path) as _pil:
                _ow, _oh = _pil.size
                _pil.save(_buf, format='PNG')
            _buf.seek(0)
            _i = _XLImg(_buf)
            _i.height = _H
            _i.width = int(_ow * _H / _oh)
            ws.add_image(_i, 'A1')
        if _os.path.exists(_logo_path):
            _buf2 = _imgio.BytesIO()
            with _PILImg.open(_logo_path) as _pil2:
                _ow2, _oh2 = _pil2.size
                _pil2.save(_buf2, format='PNG')
            _buf2.seek(0)
            _i2 = _XLImg(_buf2)
            _lw = int(_ow2 * _H / _oh2)
            _i2.height = _H
            _i2.width = _lw
            try:
                from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
                from openpyxl.drawing.xdr import XDRPositiveSize2D
                _lw_emu = int(_lw * 9525)
                _lh_emu = int(_H * 9525)
                _anch2 = OneCellAnchor()
                _anch2._from = AnchorMarker(col=14, colOff=-_lw_emu, row=0, rowOff=0)
                _anch2.ext = XDRPositiveSize2D(_lw_emu, _lh_emu)
                _i2.anchor = _anch2
                ws.add_image(_i2)
            except Exception:
                ws.add_image(_i2, 'M1')
    except Exception:
        pass

    # ── Ligne 4 : Titre PAI ───────────────────────────────────────────────────
    ws.merge_cells('A4:N4')
    ws['A4'].value = f"PLAN ANNUEL D'INVESTISSEMENT (PAI) — Exercice {annee.annee}"
    ws['A4'].font = Font(bold=True, size=14)
    ws['A4'].alignment = Alignment(horizontal='center', vertical='center')
    ws['A4'].fill = fill('D6EAF8')
    _med = Side(style='medium')
    for _tc in range(1, 15):
        ws.cell(row=4, column=_tc).border = Border(
            left=_med  if _tc == 1  else Side(style=None),
            right=_med if _tc == 14 else Side(style=None),
            top=_med, bottom=_med,
        )
    ws.row_dimensions[4].height = 28

    # ── Lignes 5-6 : En-têtes colonnes (2 niveaux, identiques au tableau HTML) ──
    ws.row_dimensions[5].height = 24
    ws.row_dimensions[6].height = 22

    # Colonnes sans sous-groupe : merge sur 2 lignes (rowspan=2)
    simple_headers = [
        (1,  'Code PAI'),
        (2,  'Programmes / Projets / Activités'),
        (3,  'Localisation'),
        (4,  'Poids (%)'),
        (5,  'Indicateurs'),
        (6,  "Période d'exécution"),
        (7,  'Struct. Resp.'),
        (8,  'Structures associées'),
        (14, 'Observations'),
    ]
    for col, h in simple_headers:
        ws.merge_cells(start_row=5, start_column=col, end_row=6, end_column=col)
        c = ws.cell(row=5, column=col, value=h)
        c.font = Font(bold=True, size=9)
        c.fill = fill('BDD7EE')
        c.alignment = center
        c.border = bord
        ws.cell(row=6, column=col).border = bord

    # Groupe "Sources de Financement" : cols 9-13, ligne 5 fusionnée
    ws.merge_cells(start_row=5, start_column=9, end_row=5, end_column=13)
    c = ws.cell(row=5, column=9, value='SOURCES DE FINANCEMENT (en milliers de F CFA)')
    c.font = Font(bold=True, size=9)
    c.fill = fill('BDD7EE')
    c.alignment = center
    c.border = bord

    # Sous-en-têtes financiers ligne 6 (FP | FADeC | Montant FADeC | Autres PTFs | Coût Total)
    fin_sub = [
        (9,  'FP'),
        (10, 'FADeC'),
        (11, 'Montant FADeC'),
        (12, 'Autres PTFs'),
        (13, 'Coût Total'),
    ]
    for col, h in fin_sub:
        c = ws.cell(row=6, column=col, value=h)
        c.font = Font(bold=True, size=9)
        c.fill = fill('BDD7EE')
        c.alignment = center
        c.border = bord

    r = 7  # les données commencent à la ligne 7

    def _periode(act):
        if act.periode_debut and act.periode_fin and act.periode_debut != act.periode_fin:
            return f'{act.periode_debut} – {act.periode_fin}'
        return act.periode_debut or act.periode_fin or ''

    def _assoc(act):
        codes = [d.code for d in act.directions_associees] + [s.code for s in act.services_intervenants]
        return ', '.join(codes)

    for pg_d in pai_data:
        pg = pg_d['programme']
        pn = pg_d['prog_num']
        poids_pg = pg_d['poids']
        ws.cell(row=r, column=1, value=str(pn))
        ws.cell(row=r, column=2, value=f'Programme {pn} : {pg.nom}')
        ws.cell(row=r, column=4, value=poids_pg if poids_pg else 0)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=14)
        for col in range(1, 15):
            c = ws.cell(row=r, column=col)
            c.fill = fill('F4B183'); c.font = Font(bold=True, size=9); c.border = bord
        ws.cell(row=r, column=1).alignment = center
        ws.cell(row=r, column=2).alignment = left
        ws.cell(row=r, column=4).alignment = center
        r += 1

        for pj_d in pg_d['projets']:
            pj = pj_d['projet']
            pjn = pj_d['proj_num']
            poids_pj = pj_d['poids']
            ws.cell(row=r, column=1, value=f'{pn}.{pjn}')
            ws.cell(row=r, column=2, value=f'Projet {pn}.{pjn} : {pj.nom}')
            ws.cell(row=r, column=4, value=poids_pj if poids_pj else 0)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
            ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=14)
            for col in range(1, 15):
                c = ws.cell(row=r, column=col)
                c.fill = fill('FFFF00'); c.font = Font(bold=True, size=9); c.border = bord
            ws.cell(row=r, column=1).alignment = center
            ws.cell(row=r, column=2).alignment = left
            ws.cell(row=r, column=4).alignment = center
            r += 1

            pj_fp = pj_fadec = pj_ptfs = pj_total = 0.0
            for act_i, act in enumerate(pj_d['activites'], 1):
                extra = act.pai_extra
                a_fp    = act.src_rp / 1000
                a_fa    = act.src_fa / 1000
                a_fn    = act.src_fn / 1000
                a_fadec = a_fa + a_fn
                a_ptfs  = (act.src_ap + act.src_af) / 1000
                a_total = act.budget_total / 1000
                pj_fp += a_fp; pj_fadec += a_fadec; pj_ptfs += a_ptfs; pj_total += a_total
                a_poids = int(extra.poids_pai or 0) if extra else 0
                fadec_lbl = _fadec_label(act.src_fa, act.src_fn)

                row_data = [
                    f'{pn}.{pjn}.{act_i}',
                    act.nom,
                    extra.localisation     if extra and extra.localisation     else '',
                    a_poids,
                    extra.indicateurs      if extra and extra.indicateurs      else '',
                    _periode(act),
                    act.direction_responsable.code if act.direction_responsable else '',
                    _assoc(act),
                    a_fp,
                    fadec_lbl,
                    a_fadec,
                    a_ptfs,
                    a_total,
                    extra.observations_pai if extra and extra.observations_pai else '',
                ]
                for col, val in enumerate(row_data, 1):
                    c = ws.cell(row=r, column=col, value=val)
                    c.fill = fill('C5DEB5'); c.font = Font(size=9); c.border = bord
                    if col in (9, 11, 12, 13):
                        c.number_format = '#,##0.000'
                    c.alignment = left if col == 2 else center
                r += 1

            st = ['', f'Sous-Total {pn}.{pjn}', '', '', '', '', '', '',
                  pj_fp, 'Total FADeC', pj_fadec, pj_ptfs, pj_total, '']
            for col, val in enumerate(st, 1):
                c = ws.cell(row=r, column=col, value=val)
                c.fill = fill('EAF0FB'); c.font = Font(bold=True, italic=True, size=9); c.border = bord
                if col in (9, 11, 12, 13):
                    c.number_format = '#,##0.000'
                c.alignment = Alignment(horizontal='right', vertical='center') if col == 2 else center
            r += 1

    tot = ['', f'TOTAL PAI {annee.annee}', '', '', '', '', '', '',
           total_fp / 1000, '', total_fadec / 1000, total_ptfs / 1000, total_global / 1000, '']
    for col, val in enumerate(tot, 1):
        c = ws.cell(row=r, column=col, value=val)
        c.fill = fill('1A3A5C'); c.font = Font(bold=True, size=9, color='FFFFFF'); c.border = bord
        if col in (9, 11, 12, 13):
            c.number_format = '#,##0.000'
        c.alignment = Alignment(horizontal='right', vertical='center') if col == 2 else center

    r += 1
    legende = ws.cell(row=r, column=1,
        value="FP = Fonds Propres  |  FA = FADeC Affecté  |  FNA = FADeC Non Affecté  |  PTFs = Partenaires Techniques et Financiers  |  Montants en milliers de F CFA")
    legende.font = Font(italic=True, size=8, color='444444')
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    legende.alignment = Alignment(horizontal='left', vertical='center')

    dir_cell = ws.cell(row=r, column=10, value='Direction du Développement Local et de la Planification (DDLP)')
    dir_cell.font = Font(bold=True, size=8)
    ws.merge_cells(start_row=r, start_column=10, end_row=r, end_column=14)
    dir_cell.alignment = Alignment(horizontal='right', vertical='center')

    for i, w in enumerate([8, 35, 18, 8, 25, 12, 12, 20, 16, 16, 16, 16, 16, 22], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename=PAI_{annee.annee}.xlsx'},
    )


@pai_bp.route('/edit_prog/<int:programme_id>', methods=['POST'])
@login_required
def edit_prog(programme_id):
    """Sauvegarde le poids PAI d'un programme."""
    if current_user.role != 'admin_editeur':
        abort(403)
    programme = db.session.get(Programme, programme_id)
    if not programme:
        abort(404)
    extra = PaiProgramme.query.filter_by(programme_id=programme_id).first()
    if not extra:
        extra = PaiProgramme(programme_id=programme_id)
        db.session.add(extra)
    try:
        extra.poids_pai = float(request.form.get('poids_pai', 0) or 0)
    except (ValueError, TypeError):
        extra.poids_pai = 0.0
    db.session.commit()
    return jsonify({'ok': True})


@pai_bp.route('/edit_proj/<int:projet_id>', methods=['POST'])
@login_required
def edit_proj(projet_id):
    """Sauvegarde le poids PAI d'un projet."""
    if current_user.role != 'admin_editeur':
        abort(403)
    projet = db.session.get(Projet, projet_id)
    if not projet:
        abort(404)
    extra = PaiProjet.query.filter_by(projet_id=projet_id).first()
    if not extra:
        extra = PaiProjet(projet_id=projet_id)
        db.session.add(extra)
    try:
        extra.poids_pai = float(request.form.get('poids_pai', 0) or 0)
    except (ValueError, TypeError):
        extra.poids_pai = 0.0
    db.session.commit()
    return jsonify({'ok': True})


@pai_bp.route('/edit/<int:activite_id>', methods=['POST'])
@login_required
def edit(activite_id):
    """Sauvegarde les champs PAI-spécifiques d'une activité (admin éditeur uniquement)."""
    if current_user.role != 'admin_editeur':
        abort(403)

    activite = db.session.get(Activite, activite_id)
    if not activite:
        abort(404)

    extra = PaiActivite.query.filter_by(activite_id=activite_id).first()
    if not extra:
        extra = PaiActivite(activite_id=activite_id)
        db.session.add(extra)

    extra.localisation     = request.form.get('localisation', '').strip() or None
    extra.indicateurs      = request.form.get('indicateurs', '').strip() or None
    extra.observations_pai = request.form.get('observations_pai', '').strip() or None
    try:
        extra.poids_pai = float(request.form.get('poids_pai', 0) or 0)
    except (ValueError, TypeError):
        pass

    db.session.commit()
    return jsonify({'ok': True})
