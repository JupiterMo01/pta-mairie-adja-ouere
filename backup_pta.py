"""
backup_pta.py — Sauvegarde automatique quotidienne de la base PTA
Mairie d'Adja-Ouèrè — Système de Gestion du PTA

Planifié via PythonAnywhere > Tasks (exécution quotidienne).
Conserve les 14 derniers fichiers (rotation automatique).
Journal dans backups/backup.log.
"""

import shutil
import os
import glob
import datetime

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_SOURCE   = os.path.join(BASE_DIR, 'instance', 'pta_mairie.db')
BACKUP_DIR  = os.path.join(BASE_DIR, 'backups')
LOG_FILE    = os.path.join(BACKUP_DIR, 'backup.log')
MAX_BACKUPS = 14   # jours de rétention

# ── Utilitaire log ─────────────────────────────────────────────────────────────
def log(message):
    horodatage = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ligne = f"[{horodatage}] {message}"
    print(ligne)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(ligne + '\n')

# ── Sauvegarde principale ──────────────────────────────────────────────────────
def run():
    log("=" * 60)
    log("Démarrage sauvegarde PTA")

    # 1. Vérifier que la base existe
    if not os.path.exists(DB_SOURCE):
        log(f"ERREUR : base de données introuvable → {DB_SOURCE}")
        return

    # 2. Copier avec nom horodaté
    date_str    = datetime.datetime.now().strftime('%Y-%m-%d_%Hh%M')
    destination = os.path.join(BACKUP_DIR, f'pta_mairie_{date_str}.db')
    shutil.copy2(DB_SOURCE, destination)
    taille_ko = os.path.getsize(destination) / 1024
    log(f"Copie réussie → {destination}  ({taille_ko:.1f} Ko)")

    # 3. Rotation : supprimer les sauvegardes excédentaires
    toutes = sorted(glob.glob(os.path.join(BACKUP_DIR, 'pta_mairie_*.db')))
    while len(toutes) > MAX_BACKUPS:
        ancien = toutes.pop(0)
        os.remove(ancien)
        log(f"Supprimé (rotation 14j) : {os.path.basename(ancien)}")

    log(f"Sauvegardes actives : {len(toutes)} / {MAX_BACKUPS}")
    log("Sauvegarde terminée avec succès")

if __name__ == '__main__':
    run()
