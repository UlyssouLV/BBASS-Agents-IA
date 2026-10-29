#!/bin/sh
# Ancré à la racine du dépôt : le cwd Claude/Cursor peut être un sous-dossier.
# L'interpréteur est choisi avant de lancer le hook une seule fois : un
# `python3 … || py -3 …` relancerait le hook après un refus (exit 2) et le perdrait.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || ROOT="."
cd "$ROOT" || exit 1
if python3 -c "" </dev/null >/dev/null 2>&1; then
  exec python3 agents/hooks/bloque-up-ecarts-pack/hook.py
fi
exec py -3 agents/hooks/bloque-up-ecarts-pack/hook.py
