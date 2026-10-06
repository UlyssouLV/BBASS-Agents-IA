@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Lancement de la VM centrale (BBASS Agents IA)
echo ============================================
echo.

if not exist "%~dp0.env" (
    echo Premiere utilisation : creation de .env a partir de .env.example...
    copy /y "%~dp0.env.example" "%~dp0.env" >nul
)

echo [1/5] Verification de Python 3.11...
call "%~dp0scripts\verifier-python.bat"
if errorlevel 1 goto :erreur

echo [2/5] Preparation de l'environnement vm-centrale ^(venv + dependances^)...
call "%~dp0scripts\preparer-package.bat" "%~dp0vm-centrale"
if errorlevel 1 goto :erreur

echo [3/5] Verification / demarrage de PostgreSQL et SearXNG (Docker)...
call "%~dp0scripts\verifier-docker.bat"
if errorlevel 1 goto :erreur
call "%~dp0scripts\demarrer-postgres.bat"
if errorlevel 1 goto :erreur
echo       PostgreSQL est demarre et pret ^(conteneur bbass-vm-centrale-postgres, port 5432^).
call "%~dp0scripts\demarrer-searxng.bat"
if errorlevel 1 goto :erreur
echo       SearXNG est demarre ^(conteneur bbass-vm-centrale-searxng, http://localhost:8888^).
echo.

echo [4/5] Verification / creation du compte de test...
pushd "%~dp0vm-centrale"
set PYTHONPATH=src
.venv\Scripts\python.exe scripts\seed_compte_test.py
popd

echo [5/5] Ouverture des fenetres...
start "PostgreSQL - logs" cmd /k "docker logs -f bbass-vm-centrale-postgres"
start "VM centrale" cmd /k "cd /d "%~dp0vm-centrale" && set PYTHONPATH=src && .venv\Scripts\python.exe -m vm_centrale.main"

echo.
echo Termine. VM centrale sur http://localhost:8000 ^(voir la fenetre "VM centrale" pour les logs^).
echo Identifiants du compte de test rappeles ci-dessus.
echo Cette fenetre peut etre fermee.
echo.
pause
goto :fin

:erreur
echo.
echo Le lancement a echoue ^(voir le message ci-dessus^). Aucune fenetre serveur n'a ete ouverte.
pause
exit /b 1

:fin
endlocal
