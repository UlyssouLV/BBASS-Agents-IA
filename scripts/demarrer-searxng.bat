@echo off
rem Demarre SearXNG (conteneur bbass-vm-centrale-searxng), moteur de l'outil
rem rechercher_web. Toujours docker compose up --build : l'image (pinnee +
rem searxng/settings.yml) est en cache, et compose ne recree le conteneur que
rem si elle a change. Sans attente de disponibilite : la VM repond
rem "recherche indisponible" tant qu'il demarre.
rem A appeler depuis la racine du depot, Docker deja pret.
echo       (premier lancement : telechargement de l'image searxng, peut prendre quelques minutes)
docker compose up -d --build searxng
if errorlevel 1 (
    echo [ERREUR] Docker n'a pas pu demarrer SearXNG.
    echo          Voir le message Docker ci-dessus.
    exit /b 1
)
exit /b 0
