#!/usr/bin/env bash
# Demarre SearXNG (conteneur bbass-vm-centrale-searxng), moteur de l'outil
# rechercher_web. Meme logique que demarrer-postgres.sh : reutilise le
# conteneur s'il existe deja, sinon docker compose up. Sans attente de
# disponibilite : la VM repond "recherche indisponible" tant qu'il demarre.
# A appeler depuis la racine du depot, Docker deja pret.
set -u
CONTAINER_NAME="bbass-vm-centrale-searxng"

if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" == "true" ]]; then
        echo "      Conteneur $CONTAINER_NAME deja en cours : reutilisation."
        exit 0
    fi
    echo "      Conteneur $CONTAINER_NAME existant mais arrete : demarrage..."
    if ! docker start "$CONTAINER_NAME"; then
        echo "[ERREUR] Impossible de demarrer le conteneur $CONTAINER_NAME." >&2
        exit 1
    fi
    exit 0
fi

echo "      (premier lancement : telechargement de l'image searxng, peut prendre quelques minutes)"
if ! docker compose up -d searxng; then
    echo "[ERREUR] Docker n'a pas pu demarrer SearXNG." >&2
    echo "         Voir le message Docker ci-dessus." >&2
    exit 1
fi
exit 0
