#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"

echo "============================================"
echo " Lancement du logiciel BBASS Agents IA"
echo "============================================"
echo

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "Premiere utilisation : creation de .env a partir de .env.example..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

echo "[1/7] Verification de Python 3.11..."
if ! PYTHON_CMD="$(scripts/verifier-python.sh)"; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
export PYTHON_CMD

echo "[2/7] Preparation de l'environnement vm-centrale (venv + dependances)..."
if ! scripts/preparer-package.sh "$ROOT_DIR/vm-centrale"; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi

echo "[3/7] Preparation de l'environnement poste (venv + dependances)..."
if ! scripts/preparer-package.sh "$ROOT_DIR/poste"; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi

echo "[4/7] Verification / demarrage de PostgreSQL (Docker)..."
if ! scripts/verifier-docker.sh; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
echo "      (premier lancement : telechargement de l'image postgres, peut prendre quelques minutes)"
if ! docker compose up -d --wait; then
    echo
    echo "[ERREUR] Docker n'a pas pu demarrer PostgreSQL."
    echo "         Verifie que Docker Desktop est bien pret, puis relance ce script."
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
echo "      PostgreSQL est demarre et pret (conteneur bbass-vm-centrale-postgres, port 5432)."
echo

echo "[5/7] Verification / creation du compte de test..."
(cd "$ROOT_DIR/vm-centrale" && PYTHONPATH=src .venv/bin/python scripts/seed_compte_test.py)

echo "[6/7] Ouverture des fenetres VM centrale et Poste..."
source "scripts/ouvrir-fenetre-mac.sh"
ouvrir_fenetre_mac "PYTHONPATH=src .venv/bin/python -m vm_centrale.main" "$ROOT_DIR/vm-centrale"
ouvrir_fenetre_mac "PYTHONPATH=src .venv/bin/python -m poste.main" "$ROOT_DIR/poste"

echo "[7/7] Attente du demarrage du poste puis ouverture du navigateur..."
sleep 4
open "http://127.0.0.1:8100"

echo
echo "Termine. Interface sur http://127.0.0.1:8100 (voir les fenetres Terminal ouvertes pour les logs)."
echo "Identifiants du compte de test rappeles ci-dessus."
echo "Si la page ne charge pas tout de suite, les serveurs sont peut-etre encore en train de demarrer : recharge dans quelques secondes."
echo "Cette fenetre peut etre fermee."
echo
read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
echo
