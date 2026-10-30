@echo off
setlocal
cd /d "%~dp0"

rem Cible de dev (vm-centrale/src/vm_centrale/cibles_dev.py) : test par defaut
rem (serveur Moduleo de test, ecriture possible, port 8001) ou cabinet (serveur
rem du cabinet, lecture seule, port 8000). Ex. : lancer-logiciel.bat cabinet
set "CIBLE=%~1"
if "%CIBLE%"=="" set "CIBLE=test"
if /i "%CIBLE%"=="test" (
    set "PORT_VM=8001"
) else if /i "%CIBLE%"=="cabinet" (
    set "PORT_VM=8000"
) else (
    echo [ERREUR] Cible inconnue : %CIBLE% ^(test ou cabinet^).
    goto :erreur
)

echo ============================================
echo  Lancement du logiciel BBASS Agents IA - cible %CIBLE%
echo ============================================
echo.

if not exist "%~dp0.env" (
    echo Premiere utilisation : creation de .env a partir de .env.example...
    copy /y "%~dp0.env.example" "%~dp0.env" >nul
)

echo [1/8] Verification de Python 3.11...
call "%~dp0scripts\verifier-python.bat"
if errorlevel 1 goto :erreur

echo [2/8] Preparation de l'environnement vm-centrale ^(venv + dependances^)...
call "%~dp0scripts\preparer-package.bat" "%~dp0vm-centrale"
if errorlevel 1 goto :erreur

echo [3/8] Preparation de l'environnement poste ^(venv + dependances^)...
call "%~dp0scripts\preparer-package.bat" "%~dp0poste"
if errorlevel 1 goto :erreur

echo [4/8] Verification / demarrage de PostgreSQL et SearXNG (Docker)...
call "%~dp0scripts\verifier-docker.bat"
if errorlevel 1 goto :erreur
call "%~dp0scripts\demarrer-postgres.bat"
if errorlevel 1 goto :erreur
echo       PostgreSQL est demarre et pret ^(conteneur bbass-vm-centrale-postgres, port 5432^).
call "%~dp0scripts\demarrer-searxng.bat"
if errorlevel 1 goto :erreur
echo       SearXNG est demarre ^(conteneur bbass-vm-centrale-searxng, http://localhost:8888^).
echo.

echo [5/8] Cible %CIBLE% et compte de test...
pushd "%~dp0vm-centrale"
set PYTHONPATH=src
.venv\Scripts\python.exe scripts\preparer_cible_dev.py %CIBLE%
if errorlevel 1 (
    popd
    goto :erreur
)
set "BBASS_CIBLE_DEV=%CIBLE%"
.venv\Scripts\python.exe scripts\seed_compte_test.py
popd

echo [6/8] Liberation des ports %PORT_VM% (VM centrale) et 8100 (Poste) si deja occupes par une precedente instance...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PORT_VM% " ^| findstr "LISTENING"') do (
    for /f "tokens=1 delims=," %%N in ('tasklist /fi "PID eq %%P" /fo csv /nh 2^>nul') do (
        if /i "%%~N"=="python.exe" (
            echo       Port %PORT_VM% deja utilise par python.exe ^(PID %%P^) : arret de ce processus...
            taskkill /F /PID %%P >nul 2>&1
        ) else (
            echo       [ATTENTION] Port %PORT_VM% est deja utilise par %%~N ^(PID %%P^), pas un processus de ce logiciel.
            echo                   Ferme-le manuellement puis relance ce script.
        )
    )
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8100 " ^| findstr "LISTENING"') do (
    for /f "tokens=1 delims=," %%N in ('tasklist /fi "PID eq %%P" /fo csv /nh 2^>nul') do (
        if /i "%%~N"=="python.exe" (
            echo       Port 8100 deja utilise par python.exe ^(PID %%P^) : arret de ce processus...
            taskkill /F /PID %%P >nul 2>&1
        ) else (
            echo       [ATTENTION] Port 8100 est deja utilise par %%~N ^(PID %%P^), pas un processus de ce logiciel.
            echo                   Ferme-le manuellement puis relance ce script.
        )
    )
)

echo [7/8] Ouverture des fenetres VM centrale et Poste...
start "VM centrale (%CIBLE%)" cmd /k "cd /d "%~dp0vm-centrale" && set PYTHONPATH=src && set "BBASS_CIBLE_DEV=%CIBLE%" && .venv\Scripts\python.exe -m vm_centrale.main"
start "Poste (%CIBLE%)" cmd /k "cd /d "%~dp0poste" && set PYTHONPATH=src && set "VM_CENTRALE_BASE_URL=http://localhost:%PORT_VM%" && .venv\Scripts\python.exe -m poste.main"

echo [8/8] Attente du demarrage du poste puis ouverture du navigateur...
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8100"

echo.
echo Termine. Interface sur http://127.0.0.1:8100, cible %CIBLE% ^(VM sur le port %PORT_VM%, voir les fenetres "VM centrale" et "Poste" pour les logs^).
echo Identifiants du compte de test rappeles ci-dessus.
echo Si la page ne charge pas tout de suite, les serveurs sont peut-etre encore en train de demarrer : recharge dans quelques secondes.
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
