#!/usr/bin/env bash
# Affiche sur stdout la commande Python 3.11 a utiliser ("python3.11" ou "python3"),
# ou un message d'erreur sur stderr avec un code de sortie non nul si Python 3.11 est introuvable.
set -u

if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    exit 0
fi

if command -v python3 >/dev/null 2>&1 && python3 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >/dev/null 2>&1; then
    echo "python3"
    exit 0
fi

echo "[ERREUR] Python 3.11 est requis mais n'a pas ete trouve (ni python3.11, ni python3 en 3.11.x)." >&2
echo "         Installe Python 3.11 (voir README.md, section Prerequis), par exemple avec 'brew install python@3.11', puis relance ce script." >&2
exit 1
