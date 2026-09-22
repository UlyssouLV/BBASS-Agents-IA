@echo off
rem Demarre PostgreSQL (conteneur bbass-vm-centrale-postgres). Reutilise le
rem conteneur s'il existe deja (autre clone, lancement precedent), sinon
rem docker compose up. A appeler depuis la racine du depot, Docker deja pret.
set "CONTAINER_NAME=bbass-vm-centrale-postgres"

docker inspect %CONTAINER_NAME% >nul 2>nul
if errorlevel 1 goto :compose_up

for /f "delims=" %%S in ('docker inspect -f "{{.State.Running}}" %CONTAINER_NAME%') do set "RUNNING=%%S"
if /i not "%RUNNING%"=="true" (
    echo       Conteneur %CONTAINER_NAME% existant mais arrete : demarrage...
    docker start %CONTAINER_NAME%
    if errorlevel 1 (
        echo [ERREUR] Impossible de demarrer le conteneur %CONTAINER_NAME%.
        exit /b 1
    )
) else (
    echo       Conteneur %CONTAINER_NAME% deja en cours : reutilisation.
)

setlocal EnableDelayedExpansion
set "TRIES=0"
:wait_ready
for /f "delims=" %%S in ('docker inspect -f "{{.State.Running}}" %CONTAINER_NAME% 2^>nul') do set "RUNNING=%%S"
for /f "delims=" %%H in ('docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}" %CONTAINER_NAME% 2^>nul') do set "HEALTH=%%H"
if /i "!RUNNING!"=="true" if /i "!HEALTH!"=="healthy" exit /b 0
if /i "!RUNNING!"=="true" if /i "!HEALTH!"=="none" exit /b 0
set /a TRIES+=1
if !TRIES! geq 60 (
    echo [ERREUR] Le conteneur %CONTAINER_NAME% n'est pas pret a temps.
    echo          Statut : running=!RUNNING! health=!HEALTH!
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_ready

:compose_up
echo       (premier lancement : telechargement de l'image postgres, peut prendre quelques minutes)
docker compose up -d --wait
if errorlevel 1 (
    echo [ERREUR] Docker n'a pas pu demarrer PostgreSQL.
    echo          Voir le message Docker ci-dessus.
    exit /b 1
)
exit /b 0
