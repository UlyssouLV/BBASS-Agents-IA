#!/bin/bash
# From a project root that already has agents/skills/: refresh pack-owned
# skills and hooks from this checkout. Adds names that exist only in the
# pack. Never deletes a skill or hook that exists only in the project.
# Does not touch AGENTS.md, README, .env, or adapter settings by default.
#
# Usage: update-from-pack.sh [--with-docs] [--with-suivi]
#   --with-docs   scaffold docs-site if missing; else refresh PACK_OWNED paths
#                 and repair known defects left by older templates
#   --with-suivi  scaffold suivi-avancement if missing (role + README + template)
set -euo pipefail

WITH_DOCS=0
WITH_SUIVI=0
for arg in "$@"; do
  case "$arg" in
    --with-docs) WITH_DOCS=1 ;;
    --with-suivi) WITH_SUIVI=1 ;;
    -h|--help)
      echo "Usage: $0 [--with-docs] [--with-suivi]" >&2
      exit 0
      ;;
    *)
      echo "Option inconnue : $arg (attendu : --with-docs | --with-suivi)" >&2
      exit 1
      ;;
  esac
done

PACK="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="$(pwd)"
REFS="$PACK/agents/skills/process/initialise-le-repo/references"

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
for f in dispatch.py gate-code-review.py update-from-pack.sh adopter-le-pack.sh scaffold-docs-site.sh enchainer-implement.sh; do
  if [ -f "$PACK/agents/scripts/$f" ]; then
    rsync -a "$PACK/agents/scripts/$f" "$TARGET/agents/scripts/$f"
    chmod +x "$TARGET/agents/scripts/$f" 2>/dev/null || true
  fi
done

# Adapter copies actually executed by Claude Code / Cursor (same as adopter-le-pack.sh).
mkdir -p "$TARGET/.claude/hooks" "$TARGET/.cursor/hooks"
if [ -f "$PACK/agents/scripts/gate-code-review.py" ]; then
  rsync -a "$PACK/agents/scripts/gate-code-review.py" "$TARGET/.claude/hooks/gate-code-review.py"
fi
if [ -f "$PACK/.cursor/hooks/gate-code-review.sh" ]; then
  rsync -a "$PACK/.cursor/hooks/gate-code-review.sh" "$TARGET/.cursor/hooks/gate-code-review.sh"
  chmod +x "$TARGET/.cursor/hooks/gate-code-review.sh"
fi

# Templates stay in the pack: scaffold-docs-site.sh reads them from $PACK.
# Drop a copy left by an older update (duplicates docs-site/ for Sonar).
if [ "$TARGET" != "$PACK" ] && [ -d "$TARGET/agents/templates" ]; then
  rm -rf "$TARGET/agents/templates"
  echo "retiré agents/templates/ (lu depuis le pack, plus copié)"
fi

# --- docs-site ---
if [ "$WITH_DOCS" -eq 1 ]; then
  if [ -d "$TARGET/docs-site" ] && [ -f "$TARGET/docs-site/package.json" ]; then
    bash "$PACK/agents/scripts/scaffold-docs-site.sh" "$TARGET" --force-owned
  else
    bash "$PACK/agents/scripts/scaffold-docs-site.sh" "$TARGET"
  fi
else
  if [ ! -d "$TARGET/docs-site" ]; then
    echo "Astuce : pour ajouter Docusaurus + GitHub Pages → $0 --with-docs"
  fi
fi

# --- suivi ---
if [ "$WITH_SUIVI" -eq 1 ]; then
  mkdir -p "$TARGET/docs/suivi-avancement"
  if [ ! -f "$TARGET/docs/suivi-avancement/README.md" ] && [ -f "$REFS/suivi-avancement/README.md" ]; then
    rsync -a "$REFS/suivi-avancement/README.md" "$TARGET/docs/suivi-avancement/README.md"
    echo "créé   docs/suivi-avancement/README.md"
  fi
  if [ ! -f "$TARGET/docs/suivi-avancement/template-semaine.html" ] && [ -f "$REFS/suivi-avancement/template-semaine.html" ]; then
    rsync -a "$REFS/suivi-avancement/template-semaine.html" "$TARGET/docs/suivi-avancement/template-semaine.html"
    echo "créé   docs/suivi-avancement/template-semaine.html"
  fi
  if [ -f "$TARGET/agents/roles.yml" ] && ! grep -q 'suivi-avancement:' "$TARGET/agents/roles.yml"; then
    python3 - "$TARGET/agents/roles.yml" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
block = """  suivi-avancement:
    paths:
      - docs/suivi-avancement/
"""
if "suivi-avancement:" in text:
    raise SystemExit(0)
lines = text.splitlines(keepends=True)
out = []
i = 0
inserted = False
while i < len(lines):
    out.append(lines[i])
    if not inserted and lines[i].startswith("  roadmap:"):
        i += 1
        while i < len(lines) and (lines[i].startswith("    ") or lines[i].strip() == ""):
            out.append(lines[i])
            i += 1
        out.append(block if block.endswith("\n") else block + "\n")
        inserted = True
        continue
    i += 1
if not inserted:
    out.append(block if block.endswith("\n") else block + "\n")
path.write_text("".join(out))
PY
    echo "ajouté rôle suivi-avancement dans agents/roles.yml"
  fi
fi

(
  cd "$TARGET"
  python3 agents/scripts/dispatch.py
  python3 agents/scripts/dispatch.py --check
)

echo "Pack à jour : $updated mis à jour, $added ajouté(s). Rien de local n’a été effacé (hors agents/templates/ et chemins docs PACK_OWNED si --with-docs)."
