#!/bin/bash
# Adopt the pack in a project that already has code. No /init, no README
# rewrite, no Sonar credentials. Creates missing skeleton/templates only.
# If agents/skills/ already exists, use update-from-pack.sh instead.
#
# Usage: adopter-le-pack.sh [--with-suivi] [--with-docs]
set -euo pipefail

WITH_SUIVI=0
WITH_DOCS=0
for arg in "$@"; do
  case "$arg" in
    --with-suivi) WITH_SUIVI=1 ;;
    --with-docs) WITH_DOCS=1 ;;
    -h|--help)
      echo "Usage: $0 [--with-suivi] [--with-docs]" >&2
      exit 0
      ;;
    *)
      echo "Option inconnue : $arg (attendu : --with-suivi | --with-docs)" >&2
      exit 1
      ;;
  esac
done

PACK="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="$(pwd)"
REFS="$PACK/agents/skills/process/initialise-le-repo/references"

if [ -d "$TARGET/agents/skills" ]; then
  echo "Le pack est déjà là (agents/skills/). Utilise update-from-pack.sh pour une mise à jour." >&2
  exit 1
fi
if [ ! -d "$PACK/agents/skills" ] || [ ! -f "$PACK/agents/scripts/dispatch.py" ]; then
  echo "Pack incomplet : $PACK/agents introuvable." >&2
  exit 1
fi
if [ ! -d "$REFS" ]; then
  echo "Pack incomplet : $REFS introuvable." >&2
  exit 1
fi

echo "Cible : $TARGET"
if git -C "$PACK" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Pack  : $(git -C "$PACK" rev-parse --short HEAD) — $(git -C "$PACK" log -1 --format='%s')"
else
  echo "Pack  : $PACK"
fi

mkdir -p "$TARGET/agents"
# templates/ stays in the pack: scaffold-docs-site.sh reads it from $PACK.
rsync -a --exclude .DS_Store --exclude __pycache__ --exclude /templates/ \
  "$PACK/agents/" "$TARGET/agents/"
echo "copié  agents/ (sans templates/)"

if [ ! -f "$TARGET/docs/dev/feuille-de-route/feuille-de-route-dev.md" ]; then
  mkdir -p "$TARGET/docs/dev/feuille-de-route" "$TARGET/docs/dev/recherches"
  printf '%s\n' '# Feuille de route de dev' > "$TARGET/docs/dev/feuille-de-route/feuille-de-route-dev.md"
  echo "créé   docs/dev/feuille-de-route/feuille-de-route-dev.md"
fi
if [ ! -f "$TARGET/docs/dev/feuille-de-route/README.md" ] && [ -f "$REFS/feuille-de-route/README.md" ]; then
  mkdir -p "$TARGET/docs/dev/feuille-de-route"
  rsync -a "$REFS/feuille-de-route/README.md" "$TARGET/docs/dev/feuille-de-route/README.md"
  echo "créé   docs/dev/feuille-de-route/README.md"
fi
mkdir -p "$TARGET/docs/specs" "$TARGET/docs/adr"
if [ ! -f "$TARGET/docs/glossaire.md" ]; then
  mkdir -p "$TARGET/docs"
  printf '%s\n' '# Glossary' > "$TARGET/docs/glossaire.md"
  echo "créé   docs/glossaire.md"
fi

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
# Insert after roadmap block if present, else append under roles:
if "suivi-avancement:" in text:
    pass
elif "  roadmap:" in text:
    # after roadmap paths list — insert before next top-level role key under roles
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
else:
    path.write_text(text.rstrip() + "\n" + block)
PY
    echo "ajouté rôle suivi-avancement dans agents/roles.yml"
  fi
fi

if [ ! -f "$TARGET/AGENTS.md" ]; then
  rsync -a "$REFS/AGENTS.md" "$TARGET/AGENTS.md"
  echo "créé   AGENTS.md"
fi
if [ ! -f "$TARGET/.claude/CLAUDE.md" ]; then
  mkdir -p "$TARGET/.claude"
  rsync -a "$REFS/CLAUDE.md" "$TARGET/.claude/CLAUDE.md"
  echo "créé   .claude/CLAUDE.md"
fi

mkdir -p "$TARGET/.claude/hooks" "$TARGET/.cursor/hooks"
rsync -a "$PACK/agents/scripts/gate-code-review.py" "$TARGET/.claude/hooks/gate-code-review.py"
if [ -f "$PACK/.cursor/hooks/gate-code-review.sh" ]; then
  rsync -a "$PACK/.cursor/hooks/gate-code-review.sh" "$TARGET/.cursor/hooks/gate-code-review.sh"
  chmod +x "$TARGET/.cursor/hooks/gate-code-review.sh"
fi

python3 - "$REFS/settings-hooks.json" "$PACK/.cursor/hooks.json" "$TARGET" <<'PY'
import json
import sys
from pathlib import Path

claude_hooks_src = Path(sys.argv[1])
cursor_hooks_src = Path(sys.argv[2])
target = Path(sys.argv[3])


def merge_event_lists(existing: dict, incoming: dict) -> dict:
    out = dict(existing)
    for event, entries in incoming.items():
        dest = list(out.get(event) or [])
        for entry in entries:
            if entry not in dest:
                dest.append(entry)
        out[event] = dest
    return out


claude_path = target / ".claude" / "settings.json"
claude_src = json.loads(claude_hooks_src.read_text())
if claude_path.exists():
    claude = json.loads(claude_path.read_text() or "{}")
else:
    claude = {}
claude["hooks"] = merge_event_lists(claude.get("hooks") or {}, claude_src.get("hooks") or {})
claude_path.parent.mkdir(parents=True, exist_ok=True)
claude_path.write_text(json.dumps(claude, indent=2) + "\n")

cursor_path = target / ".cursor" / "hooks.json"
cursor_src = json.loads(cursor_hooks_src.read_text())
if cursor_path.exists():
    cursor = json.loads(cursor_path.read_text() or "{}")
else:
    cursor = {}
cursor.setdefault("version", cursor_src.get("version", 1))
cursor["hooks"] = merge_event_lists(cursor.get("hooks") or {}, cursor_src.get("hooks") or {})
cursor_path.parent.mkdir(parents=True, exist_ok=True)
cursor_path.write_text(json.dumps(cursor, indent=2) + "\n")
PY

echo "câblé  hooks Claude + Cursor (merge, rien d’autre écrasé)"

(
  cd "$TARGET"
  python3 agents/scripts/dispatch.py
  python3 agents/scripts/dispatch.py --check
)

if [ "$WITH_DOCS" -eq 1 ]; then
  bash "$PACK/agents/scripts/scaffold-docs-site.sh" "$TARGET"
fi

echo "Sonar : désactivé (pas de credentials). /qg skippe tant que SONAR_* n’est pas dans .env."
if [ "$WITH_SUIVI" -eq 1 ]; then
  echo "Suivi : activé (docs/suivi-avancement/ + rôle)."
else
  echo "Suivi : non activé (passe --with-suivi pour le scaffold). Finalise soft-skip /msa."
fi
if [ "$WITH_DOCS" -eq 1 ]; then
  echo "Docs : activé (docs-site/ + workflow Pages). Active GitHub Pages → Actions après push."
else
  echo "Docs : non activé (passe --with-docs, ou plus tard update-from-pack.sh --with-docs)."
fi
echo "Ne lance pas /init : le README du projet est inchangé."
echo "Pack adopté."
