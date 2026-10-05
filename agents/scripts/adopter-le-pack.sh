#!/bin/bash
# Adopt the pack in a project that already has code. No /init, no README
# rewrite, no Sonar credentials. Creates missing skeleton/templates only.
# If agents/skills/ already exists, use update-from-pack.sh instead.
set -euo pipefail

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
rsync -a --exclude .DS_Store --exclude __pycache__ "$PACK/agents/" "$TARGET/agents/"
echo "copié  agents/"

if [ ! -f "$TARGET/docs/dev/feuille-de-route-dev.md" ]; then
  mkdir -p "$TARGET/docs/dev"
  printf '%s\n' '# Feuille de route de dev' > "$TARGET/docs/dev/feuille-de-route-dev.md"
  echo "créé   docs/dev/feuille-de-route-dev.md"
fi
mkdir -p "$TARGET/docs/specs" "$TARGET/docs/adr"
if [ ! -f "$TARGET/CONTEXT.md" ]; then
  printf '%s\n' '# Glossary' > "$TARGET/CONTEXT.md"
  echo "créé   CONTEXT.md"
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

echo "Sonar : désactivé (pas de credentials). /qg et le wrap /implement skippent tant que SONAR_* n’est pas dans .env."
echo "Ne lance pas /init : le README du projet est inchangé."
echo "Pack adopté."
