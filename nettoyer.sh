#!/bin/bash
# Nettoyage des fichiers temporaires Python sur PythonAnywhere
# Usage : bash nettoyer.sh  (depuis le dossier du projet)

echo "=== Nettoyage démarré ==="

# Taille avant
AVANT=$(du -sh . 2>/dev/null | cut -f1)
echo "Taille avant : $AVANT"

# Supprimer tous les dossiers __pycache__
NB_CACHE=$(find . -type d -name "__pycache__" | wc -l)
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "Dossiers __pycache__ supprimés : $NB_CACHE"

# Supprimer tous les fichiers .pyc / .pyo / .pyd
NB_PYC=$(find . -type f -name "*.py[cod]" | wc -l)
find . -type f -name "*.py[cod]" -delete 2>/dev/null
echo "Fichiers .pyc/.pyo supprimés   : $NB_PYC"

# Supprimer les fichiers .log
NB_LOG=$(find . -type f -name "*.log" | wc -l)
find . -type f -name "*.log" -delete 2>/dev/null
echo "Fichiers .log supprimés        : $NB_LOG"

# Supprimer les fichiers .tmp
NB_TMP=$(find . -type f -name "*.tmp" | wc -l)
find . -type f -name "*.tmp" -delete 2>/dev/null
echo "Fichiers .tmp supprimés        : $NB_TMP"

# Taille après
APRES=$(du -sh . 2>/dev/null | cut -f1)
echo ""
echo "=== Nettoyage terminé ==="
echo "Taille avant : $AVANT"
echo "Taille après : $APRES"
