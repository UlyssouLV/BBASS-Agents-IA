#!/usr/bin/env bash
# Prepare un package Python (venv + dependances + .env) avant de le lancer.
# Usage : scripts/preparer-package.sh "chemin/vers/le/package"
# Le package doit contenir un uv.lock (source de verite des versions installees) ;
# uv resout la version de Python via son propre .python-version (3.11).
set -u
PKG_DIR="$1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=verifier-uv.sh
. "$SCRIPT_DIR/verifier-uv.sh"
if ! ensure_uv; then
    exit 1
fi

if [[ ! -f "$PKG_DIR/pyproject.toml" ]]; then
    echo "[ERREUR] \"$PKG_DIR\" ne contient pas de pyproject.toml." >&2
    exit 1
fi

if [[ ! -f "$PKG_DIR/uv.lock" ]]; then
    echo "[ERREUR] \"$PKG_DIR\" ne contient pas de uv.lock." >&2
    exit 1
fi

if [[ ! -f "$PKG_DIR/.env" && -f "$PKG_DIR/.env.example" ]]; then
    echo "      Creation de \"$PKG_DIR/.env\" a partir de .env.example..."
    cp "$PKG_DIR/.env.example" "$PKG_DIR/.env"
fi

echo "      Installation des dependances (uv sync, versions figees par uv.lock) dans \"$PKG_DIR/.venv\"..."
if ! uv sync --directory "$PKG_DIR" --extra test --python 3.11 --locked; then
    echo "[ERREUR] Echec de l'installation des dependances pour \"$PKG_DIR\"." >&2
    echo "         Verifie ta connexion internet et le message uv ci-dessus, puis relance ce script." >&2
    exit 1
fi

exit 0
