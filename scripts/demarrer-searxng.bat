@echo off
rem Demarre SearXNG (conteneur bbass-vm-centrale-searxng), moteur de l'outil
rem rechercher_web. Meme logique que demarrer-postgres.bat : reutilise le
rem conteneur s'il existe deja, sinon docker compose up. Sans attente de
rem disponibilite : la VM repond "recherche indisponible" tant qu'il demarre.
rem A appeler depuis la racine du depot, Docker deja pret.
set "CONTAINER_NAME=bbass-vm-centrale-searxng"

docker inspect %CONTAINER_NAME% >nul 2>nul
if errorlevel 1 goto :compose_up

for /f "delims=" %%S in ('docker inspect -f "{{.State.Running}}" %CONTAINER_NAME%') do set "RUNNING=%%S"
if /i "%RUNNING%"=="true" (
    echo       Conteneur %CONTAINER_NAME% deja en cours : reutilisation.
    exit /b 0
)
echo       Conteneur %CONTAINER_NAME% existant mais arrete : demarrage...
docker start %CONTAINER_NAME%
if errorlevel 1 (
    echo [ERREUR] Impossible de demarrer le conteneur %CONTAINER_NAME%.
    exit /b 1
)
exit /b 0

:compose_up
echo       (premier lancement : telechargement de l'image searxng, peut prendre quelques minutes)
docker compose up -d searxng
if errorlevel 1 (
    echo [ERREUR] Docker n'a pas pu demarrer SearXNG.
    echo          Voir le message Docker ci-dessus.
    exit /b 1
)
exit /b 0
