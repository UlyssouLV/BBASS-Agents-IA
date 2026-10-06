#!/usr/bin/env bash
# Demarre SearXNG (conteneur bbass-vm-centrale-searxng), moteur de l'outil
# rechercher_web. Toujours docker compose up --build : l'image (pinnee +
# searxng/settings.yml) est en cache, et compose ne recree le conteneur que
# si elle a change. Sans attente de disponibilite : la VM repond
# "recherche indisponible" tant qu'il demarre.
# A appeler depuis la racine du depot, Docker deja pret.
set -u

echo "      (premier lancement : telechargement de l'image searxng, peut prendre quelques minutes)"
if ! docker compose up -d --build searxng; then
    echo "[ERREUR] Docker n'a pas pu demarrer SearXNG." >&2
    echo "         Voir le message Docker ci-dessus." >&2
    exit 1
fi
exit 0
