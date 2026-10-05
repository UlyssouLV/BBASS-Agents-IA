#!/bin/bash
# From a project root that already has agents/skills/: refresh pack-owned
# skills and hooks from this checkout. Adds names that exist only in the
# pack. Never deletes a skill or hook that exists only in the project.
# Does not touch AGENTS.md, roles.yml, README, .env, or adapter settings.
set -euo pipefail

PACK="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="$(pwd)"

if [ ! -d "$TARGET/agents/skills" ]; then
  echo "À lancer à la racine d’un repo déjà initialisé (agents/skills/ introuvable)." >&2
  exit 1
fi
if [ ! -d "$PACK/agents/skills" ]; then
  echo "Pack incomplet : $PACK/agents/skills introuvable." >&2
  exit 1
fi

echo "Cible : $TARGET"
if git -C "$PACK" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Pack  : $(git -C "$PACK" rev-parse --short HEAD) — $(git -C "$PACK" log -1 --format='%s')"
else
  echo "Pack  : $PACK"
fi

updated=0
added=0

sync_skill() {
  local src="$1"
  local name bucket dest
  name="$(basename "$src")"
  bucket="$(basename "$(dirname "$src")")"
  dest=""
  if [ -d "$TARGET/agents/skills/meta/$name" ]; then
    dest="$TARGET/agents/skills/meta/$name"
  elif [ -d "$TARGET/agents/skills/process/$name" ]; then
    dest="$TARGET/agents/skills/process/$name"
  fi
  if [ -n "$dest" ]; then
    rsync -a --delete --exclude .DS_Store --exclude __pycache__ "$src"/ "$dest"/
    echo "skill  MAJ   $name"
    updated=$((updated + 1))
  else
    mkdir -p "$TARGET/agents/skills/$bucket"
    rsync -a --exclude .DS_Store --exclude __pycache__ "$src"/ "$TARGET/agents/skills/$bucket/$name"/
    echo "skill  AJOUT $name → agents/skills/$bucket/$name"
    added=$((added + 1))
  fi
}

sync_hook() {
  local src="$1"
  local name dest
  name="$(basename "$src")"
  dest="$TARGET/agents/hooks/$name"
  if [ -d "$dest" ]; then
    rsync -a --delete --exclude .DS_Store --exclude __pycache__ "$src"/ "$dest"/
    echo "hook   MAJ   $name"
    updated=$((updated + 1))
  else
    mkdir -p "$TARGET/agents/hooks"
    rsync -a --exclude .DS_Store --exclude __pycache__ "$src"/ "$dest"/
    echo "hook   AJOUT $name"
    added=$((added + 1))
  fi
}

for bucket in meta process; do
  pack_bucket="$PACK/agents/skills/$bucket"
  [ -d "$pack_bucket" ] || continue
  for skill in "$pack_bucket"/*/; do
    [ -d "$skill" ] || continue
    [ -f "${skill}SKILL.md" ] || continue
    sync_skill "$skill"
  done
done

if [ -d "$PACK/agents/hooks" ]; then
  for hook in "$PACK/agents/hooks"/*/; do
    [ -d "$hook" ] || continue
    sync_hook "$hook"
  done
fi

mkdir -p "$TARGET/agents/scripts"
for f in dispatch.py gate-code-review.py update-from-pack.sh adopter-le-pack.sh; do
  if [ -f "$PACK/agents/scripts/$f" ]; then
    rsync -a "$PACK/agents/scripts/$f" "$TARGET/agents/scripts/$f"
  fi
done

(
  cd "$TARGET"
  python3 agents/scripts/dispatch.py
  python3 agents/scripts/dispatch.py --check
)

echo "Pack à jour : $updated mis à jour, $added ajouté(s). Rien de local n’a été effacé."
