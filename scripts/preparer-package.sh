#!/usr/bin/env bash
# Prepare un package Python (venv + dependances + .env) avant de le lancer.
# Usage : scripts/preparer-package.sh "chemin/vers/le/package"
# Necessite que PYTHON_CMD ait deja ete determine et exporte (scripts/verifier-python.sh).
set -u
PKG_DIR="$1"

if [ -z "${PYTHON_CMD:-}" ]; then
    echo "[ERREUR interne] PYTHON_CMD n'est pas defini (verifier-python.sh doit etre appele avant)." >&2
    exit 1
fi

if [ ! -f "$PKG_DIR/pyproject.toml" ]; then
    echo "[ERREUR] \"$PKG_DIR\" ne contient pas de pyproject.toml." >&2
    exit 1
fi

if [ ! -f "$PKG_DIR/.venv/bin/python" ]; then
    echo "      Creation de l'environnement virtuel \"$PKG_DIR/.venv\"..."
    if ! "$PYTHON_CMD" -m venv "$PKG_DIR/.venv"; then
        echo "[ERREUR] Impossible de creer l'environnement virtuel dans \"$PKG_DIR\"." >&2
        exit 1
    fi
fi

if [ ! -f "$PKG_DIR/.env" ] && [ -f "$PKG_DIR/.env.example" ]; then
    echo "      Creation de \"$PKG_DIR/.env\" a partir de .env.example..."
    cp "$PKG_DIR/.env.example" "$PKG_DIR/.env"
fi

echo "      Installation des dependances (pip install -e) dans \"$PKG_DIR/.venv\"..."
if ! "$PKG_DIR/.venv/bin/python" -m pip install -e "$PKG_DIR"; then
    echo "[ERREUR] Echec de l'installation des dependances pour \"$PKG_DIR\"." >&2
    echo "         Verifie ta connexion internet et le message pip ci-dessus, puis relance ce script." >&2
    exit 1
fi

exit 0
