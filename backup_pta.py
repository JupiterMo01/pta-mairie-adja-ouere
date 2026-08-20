"""
backup_pta.py — Sauvegarde automatique quotidienne vers Google Drive
Mairie d'Adja-Ouèrè — Système de Gestion du PTA

Pré-requis (sur PythonAnywhere) :
    pip install --user google-api-python-client google-auth

Configuration :
    1. Placer drive_key.json dans le même dossier que ce fichier
    2. Renseigner DRIVE_FOLDER_ID ci-dessous (ID du dossier Drive)

Planification :
    PythonAnywhere > Tasks > Daily à 00:30 UTC (01h30 heure Bénin)
    Commande : python /home/jupi01/pta_mairie/backup_pta.py
"""

import os
import datetime

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
DB_SOURCE       = os.path.join(BASE_DIR, 'instance', 'pta_mairie.db')
KEY_FILE        = os.path.join(BASE_DIR, 'drive_key.json')
LOG_FILE        = os.path.join(BASE_DIR, 'backup_drive.log')

DRIVE_FOLDER_ID = 'REMPLACER_PAR_ID_DU_DOSSIER_DRIVE'  # ← à remplir
MAX_BACKUPS     = 14   # jours de rétention

# ── Utilitaires ────────────────────────────────────────────────────────────────
def log(message):
    horodatage = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ligne = f"[{horodatage}] {message}"
    print(ligne)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(ligne + '\n')

def get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(service, local_path, filename):
    from googleapiclient.http import MediaFileUpload
    metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media    = MediaFileUpload(local_path, mimetype='application/x-sqlite3')
    f = service.files().create(body=metadata, media_body=media, fields='id').execute()
    return f.get('id')

def rotation_drive(service):
    """Supprimer les sauvegardes excédentaires (les plus anciennes en premier)."""
    res = service.files().list(
        q=(f"'{DRIVE_FOLDER_ID}' in parents "
           f"and name contains 'pta_mairie_' "
           f"and trashed=false"),
        orderBy='createdTime',
        fields='files(id, name)'
    ).execute()
    fichiers = res.get('files', [])
    while len(fichiers) > MAX_BACKUPS:
        ancien = fichiers.pop(0)
        service.files().delete(fileId=ancien['id']).execute()
        log(f"Supprimé Drive (rotation) : {ancien['name']}")
    return len(fichiers)

# ── Sauvegarde principale ──────────────────────────────────────────────────────
def run():
    log("=" * 60)
    log("Démarrage sauvegarde PTA → Google Drive")

    # Vérifications
    if not os.path.exists(DB_SOURCE):
        log(f"ERREUR : base de données introuvable → {DB_SOURCE}")
        return
    if not os.path.exists(KEY_FILE):
        log(f"ERREUR : clé service account introuvable → {KEY_FILE}")
        return
    if DRIVE_FOLDER_ID == 'REMPLACER_PAR_ID_DU_DOSSIER_DRIVE':
        log("ERREUR : DRIVE_FOLDER_ID non configuré dans backup_pta.py")
        return

    try:
        service  = get_drive_service()
        date_str = datetime.datetime.now().strftime('%Y-%m-%d_%Hh%M')
        filename = f'pta_mairie_{date_str}.db'
        taille   = os.path.getsize(DB_SOURCE) / 1024

        file_id = upload_to_drive(service, DB_SOURCE, filename)
        log(f"Envoyé sur Drive : {filename}  ({taille:.1f} Ko)  ID={file_id}")

        nb = rotation_drive(service)
        log(f"Sauvegardes Drive actives : {nb} / {MAX_BACKUPS}")
        log("Sauvegarde terminée avec succès ✓")

    except Exception as e:
        log(f"ERREUR inattendue : {e}")
        raise

if __name__ == '__main__':
    run()
