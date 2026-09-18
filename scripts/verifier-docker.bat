@echo off
rem Verifie que le CLI docker est joignable. Si Docker Desktop est installe
rem mais pas lance, le demarre et attend que le moteur reponde.
rem Pas de setlocal en tete : un PATH enrichi doit survivre au call.

where docker >nul 2>nul
if errorlevel 1 (
    if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" (
        set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
    )
)

where docker >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Docker n'est pas installe ^(commande "docker" introuvable^).
    echo          Installe Docker Desktop ^(voir README.md, section Prerequis^), puis relance ce script.
    exit /b 1
)

docker info >nul 2>nul
if not errorlevel 1 exit /b 0

set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if not exist "%DOCKER_DESKTOP%" (
    echo [ERREUR] Docker est installe mais le moteur n'est pas demarre, et Docker Desktop.exe est introuvable.
    echo          Ouvre Docker Desktop a la main, attends qu'il soit pret, puis relance ce script.
    exit /b 1
)

echo       Docker Desktop est installe mais pas lance : demarrage...
echo       (le moteur peut mettre une a deux minutes a etre pret)
start "" "%DOCKER_DESKTOP%"

setlocal EnableDelayedExpansion
set "TRIES=0"
:wait_docker
docker info >nul 2>nul
if not errorlevel 1 exit /b 0
set /a TRIES+=1
if !TRIES! geq 90 (
    echo [ERREUR] Docker Desktop a ete lance mais le moteur n'est pas pret a temps.
    echo          Attends l'icone Docker dans la barre des taches, puis relance ce script.
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_docker
