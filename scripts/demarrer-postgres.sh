#!/usr/bin/env bash
# Demarre PostgreSQL (conteneur bbass-vm-centrale-postgres). Reutilise le
# conteneur s'il existe deja (autre clone, lancement precedent), sinon
# docker compose up. A appeler depuis la racine du depot, Docker deja pret.
set -u
CONTAINER_NAME="bbass-vm-centrale-postgres"

wait_ready() {
    local tries=0
    while true; do
        local running health
        running="$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || echo false)"
        health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER_NAME" 2>/dev/null || echo none)"
        if [[ "$running" == "true" && ( "$health" == "healthy" || "$health" == "none" ) ]]; then
            return 0
        fi
        tries=$((tries + 1))
        if [[ "$tries" -ge 60 ]]; then
            echo "[ERREUR] Le conteneur $CONTAINER_NAME n'est pas pret a temps." >&2
            echo "         Statut : running=$running health=$health" >&2
            return 1
        fi
        sleep 2
    done
}

if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]]; then
        echo "      Conteneur $CONTAINER_NAME existant mais arrete : demarrage..."
        if ! docker start "$CONTAINER_NAME"; then
            echo "[ERREUR] Impossible de demarrer le conteneur $CONTAINER_NAME." >&2
            exit 1
        fi
    else
        echo "      Conteneur $CONTAINER_NAME deja en cours : reutilisation."
    fi
    wait_ready
    exit $?
fi

echo "      (premier lancement : telechargement de l'image postgres, peut prendre quelques minutes)"
if ! docker compose up -d --wait; then
    echo "[ERREUR] Docker n'a pas pu demarrer PostgreSQL." >&2
    echo "         Voir le message Docker ci-dessus." >&2
    exit 1
fi
exit 0
