#!/bin/sh
# Ancré à la racine du dépôt : le cwd Claude/Cursor peut être un sous-dossier.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || ROOT="."
cd "$ROOT" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 agents/hooks/bloque-ecriture-moduleo/hook.py
fi
exec py -3 agents/hooks/bloque-ecriture-moduleo/hook.py
