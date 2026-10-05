#!/usr/bin/env bash
# Verifie que le CLI docker est joignable. Si Docker Desktop est installe
# mais pas lance, le demarre et attend que le moteur reponde.
set -u

if ! command -v docker >/dev/null 2>&1; then
    echo "[ERREUR] Docker n'est pas installe (commande \"docker\" introuvable)." >&2
    echo "         Installe Docker Desktop (voir README.md, section Prerequis), puis relance ce script." >&2
    exit 1
fi

if docker info >/dev/null 2>&1; then
    exit 0
fi

if [[ ! -d "/Applications/Docker.app" ]]; then
    echo "[ERREUR] Docker est installe mais le moteur n'est pas demarre, et Docker.app est introuvable." >&2
    echo "         Ouvre Docker Desktop a la main, attends qu'il soit pret, puis relance ce script." >&2
    exit 1
fi

echo "      Docker Desktop est installe mais pas lance : demarrage..."
echo "      (le moteur peut mettre une a deux minutes a etre pret)"
open -a Docker

tries=0
while true; do
    if docker info >/dev/null 2>&1; then
        exit 0
    fi
    tries=$((tries + 1))
    if [[ "$tries" -ge 90 ]]; then
        echo "[ERREUR] Docker Desktop a ete lance mais le moteur n'est pas pret a temps." >&2
        echo "         Attends l'icone Docker dans la barre de menus, puis relance ce script." >&2
        exit 1
    fi
    sleep 2
done
