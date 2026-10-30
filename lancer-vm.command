#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"

# Cible de dev (vm-centrale/src/vm_centrale/cibles_dev.py) : test par defaut
# (serveur Moduleo de test, ecriture possible, port 8001) ou cabinet (serveur
# du cabinet, lecture seule, port 8000). Ex. : ./lancer-vm.command cabinet
CIBLE="${1:-test}"
case "$CIBLE" in
    test) PORT_VM=8001 ;;
    cabinet) PORT_VM=8000 ;;
    *) echo "[ERREUR] Cible inconnue : $CIBLE (test ou cabinet)."; exit 1 ;;
esac

echo "============================================"
echo " Lancement de la VM centrale (BBASS Agents IA) - cible $CIBLE"
echo "============================================"
echo

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "Premiere utilisation : creation de .env a partir de .env.example..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

echo "[1/5] Verification de Python 3.11..."
if ! PYTHON_CMD="$(scripts/verifier-python.sh)"; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
export PYTHON_CMD

echo "[2/5] Preparation de l'environnement vm-centrale (venv + dependances)..."
if ! scripts/preparer-package.sh "$ROOT_DIR/vm-centrale"; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi

echo "[3/5] Verification / demarrage de PostgreSQL et SearXNG (Docker)..."
if ! scripts/verifier-docker.sh; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
if ! scripts/demarrer-postgres.sh; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
echo "      PostgreSQL est demarre et pret (conteneur bbass-vm-centrale-postgres, port 5432)."
if ! scripts/demarrer-searxng.sh; then
    echo
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
echo "      SearXNG est demarre (conteneur bbass-vm-centrale-searxng, http://localhost:8888)."
echo

echo "[4/5] Cible $CIBLE et compte de test..."
if ! (cd "$ROOT_DIR/vm-centrale" && PYTHONPATH=src .venv/bin/python scripts/preparer_cible_dev.py "$CIBLE"); then
    read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
    echo
    exit 1
fi
(cd "$ROOT_DIR/vm-centrale" && BBASS_CIBLE_DEV="$CIBLE" PYTHONPATH=src .venv/bin/python scripts/seed_compte_test.py)

echo "[5/5] Ouverture des fenetres..."
source "scripts/ouvrir-fenetre-mac.sh"
ouvrir_fenetre_mac "docker logs -f bbass-vm-centrale-postgres" "$ROOT_DIR"
ouvrir_fenetre_mac "BBASS_CIBLE_DEV=$CIBLE PYTHONPATH=src .venv/bin/python -m vm_centrale.main" "$ROOT_DIR/vm-centrale"

echo
echo "Termine. VM centrale, cible $CIBLE, sur http://localhost:$PORT_VM (voir les fenetres Terminal ouvertes pour les logs)."
echo "Identifiants du compte de test rappeles ci-dessus."
echo "Cette fenetre peut etre fermee."
echo
read -n 1 -s -r -p "Appuie sur une touche pour fermer..."
echo
