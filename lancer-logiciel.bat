@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Lancement du logiciel BBASS Agents IA
echo ============================================
echo.
if not exist "%~dp0.env" (
    echo Premiere utilisation : creation de .env a partir de .env.example...
    copy /y "%~dp0.env.example" "%~dp0.env" >nul
)

echo [1/5] Verification / demarrage de PostgreSQL (Docker)...
echo       (premier lancement : telechargement de l'image postgres, peut prendre quelques minutes)
docker compose up -d --wait
if errorlevel 1 (
    echo.
    echo [ERREUR] Docker n'a pas pu demarrer PostgreSQL.
    echo          Verifie que Docker Desktop est bien ouvert et demarre, puis relance ce script.
    pause
    exit /b 1
)
echo       PostgreSQL est demarre et pret ^(conteneur bbass-vm-centrale-postgres, port 5432^).
echo.

echo [2/5] Verification / creation du compte de test...
pushd "%~dp0vm-centrale"
set PYTHONPATH=src
.venv\Scripts\python.exe scripts\seed_compte_test.py
popd

echo [3/5] Ouverture de la fenetre VM centrale...
start "VM centrale" cmd /k "cd /d "%~dp0vm-centrale" && set PYTHONPATH=src && .venv\Scripts\python.exe -m vm_centrale.main"

echo [4/5] Ouverture de la fenetre Poste...
start "Poste" cmd /k "cd /d "%~dp0poste" && set PYTHONPATH=src && .venv\Scripts\python.exe -m poste.main"

echo [5/5] Attente du demarrage du poste puis ouverture du navigateur...
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8100"

echo.
echo Termine. Interface sur http://127.0.0.1:8100 ^(voir les fenetres "VM centrale" et "Poste" pour les logs^).
echo Identifiants du compte de test rappeles ci-dessus.
echo Si la page ne charge pas tout de suite, les serveurs sont peut-etre encore en train de demarrer : recharge dans quelques secondes.
echo Cette fenetre peut etre fermee.
echo.
pause

endlocal
