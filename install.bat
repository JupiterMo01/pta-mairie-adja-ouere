@echo off
title Installation PTA Mairie d'Adja-Ouere
color 1F
echo ============================================================
echo   INSTALLATION DU SYSTEME PTA - MAIRIE D'ADJA-OUERE
echo ============================================================
echo.

:: Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe.
    echo.
    echo Telechargez Python sur : https://www.python.org/downloads/
    echo Cochez "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)

echo [OK] Python detecte.
echo.
echo Installation des dependances...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] Echec de l'installation des dependances.
    pause
    exit /b 1
)

echo.
echo Initialisation de la base de donnees...
python init_db.py
if errorlevel 1 (
    echo [ERREUR] Echec de l'initialisation.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   INSTALLATION REUSSIE !
echo ============================================================
echo.
echo   Pour lancer l'application : double-cliquez sur run.bat
echo   Puis ouvrez votre navigateur sur : http://localhost:5000
echo.
echo   Identifiants par defaut :
echo     Login    : admin
echo     Mot de passe : admin2026
echo.
echo   IMPORTANT : Changez le mot de passe apres la premiere connexion.
echo ============================================================
pause