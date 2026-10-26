#!/bin/sh
# Ancré à la racine : le cwd peut être un sous-dossier. python3 (macOS/Linux)
# puis py -3 (Windows) — même logique que .cursor/hooks.json.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || ROOT="."
cd "$ROOT" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 agents/hooks/gate-code-review/hook.py
fi
exec py -3 agents/hooks/gate-code-review/hook.py
