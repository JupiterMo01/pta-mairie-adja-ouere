@echo off
title PTA Mairie d'Adja-Ouere - Serveur
color 2F
echo ============================================================
echo   DEMARRAGE DU SYSTEME PTA - MAIRIE D'ADJA-OUERE
echo ============================================================
echo.

:: Recuperer l'adresse IP locale
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

echo   Serveur en cours de demarrage...
echo.
echo   Acces local    : http://localhost:5000
echo   Acces reseau   : http://%IP%:5000
echo.
echo   Partagez l'adresse reseau avec les autres postes du WiFi.
echo   Pour arreter le serveur : appuyez sur Ctrl+C
echo ============================================================
echo.
python app.py
pause