"""
backup_pta.py — Sauvegarde automatique quotidienne par email
Mairie d'Adja-Ouèrè — Système de Gestion du PTA

La base de données est envoyée en pièce jointe sur Gmail chaque nuit.
Aucune API payante, aucune carte bancaire — uniquement un mot de passe
d'application Gmail (myaccount.google.com > Sécurité > Mots de passe applis).

Configuration : fichier ~/.pta_backup_config (jamais versionné dans git)
    GMAIL_USER=votre@gmail.com
    GMAIL_APP_PASSWORD=motdepasseapp16caract
    DEST_EMAIL=destinataire@gmail.com

Planification : PythonAnywhere > Tasks > Daily 00:30 UTC
    python /home/jupi01/pta_mairie/backup_pta.py
"""

import os
import tempfile
import datetime
import gzip
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base       import MIMEBase
from email.mime.text       import MIMEText
from email                 import encoders

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_SOURCE  = os.path.join(BASE_DIR, 'instance', 'pta_mairie.db')
LOG_FILE   = os.path.join(BASE_DIR, 'backup_email.log')
CONFIG     = os.path.expanduser('~/.pta_backup_config')

# ── Utilitaires ───────────────────────────────────────────────────────────────
def log(message):
    horodatage = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ligne      = f"[{horodatage}] {message}"
    print(ligne)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(ligne + '\n')

def lire_config():
    """Lire GMAIL_USER, GMAIL_APP_PASSWORD, DEST_EMAIL depuis ~/.pta_backup_config"""
    if not os.path.exists(CONFIG):
        raise FileNotFoundError(f"Fichier de config introuvable : {CONFIG}")
    cfg = {}
    with open(CONFIG, encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip()
            if '=' in ligne and not ligne.startswith('#'):
                cle, val = ligne.split('=', 1)
                cfg[cle.strip()] = val.strip()
    for cle in ('GMAIL_USER', 'GMAIL_APP_PASSWORD', 'DEST_EMAIL'):
        if cle not in cfg:
            raise ValueError(f"Clé manquante dans config : {cle}")
    return cfg

LIMITE_GMAIL_MO = 20   # alerte si la DB compressée dépasse ce seuil (Mo)


def compresser_db(db_path, gz_path):
    """Compresse db_path en gzip → gz_path. Retourne la taille en Ko."""
    with open(db_path, 'rb') as f_in, gzip.open(gz_path, 'wb', compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    return os.path.getsize(gz_path) / 1024


def envoyer_backup(cfg, db_path, nom_fichier):
    """Compresse la DB en gzip dans un dossier temporaire système puis l'envoie
    par email. Retourne True si l'email a bien été envoyé, False sinon."""
    date_lisible = datetime.datetime.now().strftime('%d/%m/%Y à %Hh%M')
    taille_brute_ko = os.path.getsize(db_path) / 1024
    nom_gz = nom_fichier + '.gz'

    # Fichier temporaire dans /tmp (permissions garanties sur tous les OS)
    fd, gz_path = tempfile.mkstemp(suffix='.db.gz', prefix='pta_backup_')
    os.close(fd)
    try:
        taille_gz_ko = compresser_db(db_path, gz_path)

        # Alerte si fichier compressé > seuil Gmail
        if taille_gz_ko > LIMITE_GMAIL_MO * 1024:
            log(f"AVERTISSEMENT : fichier compressé trop volumineux "
                f"({taille_gz_ko/1024:.1f} Mo > {LIMITE_GMAIL_MO} Mo). Envoi annulé.")
            return False

        msg = MIMEMultipart()
        msg['From']    = cfg['GMAIL_USER']
        msg['To']      = cfg['DEST_EMAIL']
        msg['Subject'] = f"[PTA Mairie] Sauvegarde automatique — {date_lisible}"

        corps = (
            f"Bonjour,\n\n"
            f"Sauvegarde automatique de la base PTA de la Mairie d'Adja-Ouèrè.\n\n"
            f"  Fichier  : {nom_gz}\n"
            f"  Taille   : {taille_gz_ko:.1f} Ko (compressé) / {taille_brute_ko:.1f} Ko (brut)\n"
            f"  Date     : {date_lisible}\n\n"
            f"Pour restaurer : décompresser le fichier .gz avec 7-Zip ou gunzip.\n\n"
            f"Ce message est généré automatiquement — ne pas répondre.\n"
            f"Mairie d'Adja-Ouèrè · Système PTA"
        )
        msg.attach(MIMEText(corps, 'plain', 'utf-8'))

        # Pièce jointe (fichier compressé)
        with open(gz_path, 'rb') as f:
            part = MIMEBase('application', 'gzip')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{nom_gz}"')
        msg.attach(part)

        # Envoi via Gmail SMTP
        with smtplib.SMTP('smtp.gmail.com', 587) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(cfg['GMAIL_USER'], cfg['GMAIL_APP_PASSWORD'])
            srv.sendmail(cfg['GMAIL_USER'], cfg['DEST_EMAIL'], msg.as_string())

        return True

    finally:
        # Toujours supprimer le fichier temporaire
        try:
            os.remove(gz_path)
        except OSError:
            pass

# ── Sauvegarde principale ──────────────────────────────────────────────────────
def run():
    log("=" * 60)
    log("Démarrage sauvegarde PTA → Gmail")

    if not os.path.exists(DB_SOURCE):
        log(f"ERREUR : base de données introuvable → {DB_SOURCE}")
        return

    try:
        cfg          = lire_config()
        date_str     = datetime.datetime.now().strftime('%Y-%m-%d_%Hh%M')
        nom_fichier  = f'pta_mairie_{date_str}.db'
        taille_ko    = os.path.getsize(DB_SOURCE) / 1024

        log(f"Envoi en cours : {nom_fichier} ({taille_ko:.1f} Ko) → {cfg['DEST_EMAIL']}")
        envoye = envoyer_backup(cfg, DB_SOURCE, nom_fichier)
        if envoye:
            log("Email envoyé avec succès ✓")
        else:
            log("AVERTISSEMENT : email non envoyé (voir message ci-dessus)")
        log("Sauvegarde terminée")

    except FileNotFoundError as e:
        log(f"ERREUR config : {e}")
    except ValueError as e:
        log(f"ERREUR config : {e}")
    except Exception as e:
        log(f"ERREUR envoi : {e}")
        raise

if __name__ == '__main__':
    run()
