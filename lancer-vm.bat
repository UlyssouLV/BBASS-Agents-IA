@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Lancement de la VM centrale (BBASS Agents IA)
echo ============================================
echo.
echo [1/4] Verification / demarrage de PostgreSQL (Docker)...
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

echo [2/4] Verification / creation du compte de test...
pushd "%~dp0vm-centrale"
set PYTHONPATH=src
.venv\Scripts\python.exe scripts\seed_compte_test.py
popd

echo [3/4] Ouverture de la fenetre de logs PostgreSQL...
start "PostgreSQL - logs" cmd /k "docker compose logs -f postgres"

echo [4/4] Ouverture de la fenetre VM centrale...
start "VM centrale" cmd /k "cd /d "%~dp0vm-centrale" && set PYTHONPATH=src && .venv\Scripts\python.exe -m vm_centrale.main"

echo.
echo Termine. VM centrale sur http://localhost:8000 ^(voir la fenetre "VM centrale" pour les logs^).
echo Identifiants du compte de test rappeles ci-dessus.
echo Cette fenetre peut etre fermee.
echo.
pause

endlocal
