#!/bin/sh
# Ancré à la racine du dépôt : le cwd Claude/Cursor peut être un sous-dossier (ex. vm-centrale/).
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || ROOT="."
cd "$ROOT" || exit 1
exec python3 agents/hooks/gate-code-review/hook.py
