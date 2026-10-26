#!/bin/bash
# Scaffold or refresh the generic Docusaurus docs-site in a target repo.
# Usage (from pack or via PATH):
#   scaffold-docs-site.sh <TARGET_REPO_ROOT> [--force-owned]
# --force-owned : when docs-site already exists, overwrite PACK_OWNED.txt paths only
# Without existing docs-site: full copy + stubs + workflow + roles.yml role.
# --force-owned also repairs known defects left by older templates (see
# repair_known_defects).
set -euo pipefail

TARGET="${1:-}"
MODE_FORCE_OWNED=0
shift || true
for arg in "$@"; do
  case "$arg" in
    --force-owned) MODE_FORCE_OWNED=1 ;;
    *)
      echo "Option inconnue : $arg" >&2
      exit 1
      ;;
  esac
done

if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
  echo "Usage: $0 <TARGET_REPO_ROOT> [--force-owned]" >&2
  exit 1
fi

PACK="$(cd "$(dirname "$0")/../.." && pwd)"
TMPL="$PACK/agents/templates/docs-site"
STUBS="$PACK/agents/templates/docs-stubs"
WF_SRC="$PACK/agents/templates/github/workflows/deploy-docs.yml"

if [ ! -d "$TMPL" ] || [ ! -f "$TMPL/package.json" ]; then
  echo "Template introuvable : $TMPL" >&2
  echo "Lance ce script depuis un clone du pack (bash <pack>/agents/scripts/scaffold-docs-site.sh <cible>)." >&2
  exit 1
fi

# Resolve owner/repo from git remote
OWNER="OWNER"
REPO="REPO"
TITLE="Documentation"
TAGLINE="Documentation du projet — produit, features et décisions"
if git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  remote="$(git -C "$TARGET" remote get-url origin 2>/dev/null || true)"
  if [[ "$remote" =~ github.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    OWNER="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
  fi
  # Prefer README H1 or package name later — default to repo name
  TITLE="$REPO"
fi

apply_placeholders() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return
  fi
  OWNER="$OWNER" REPO="$REPO" TITLE="$TITLE" TAGLINE="$TAGLINE" python3 - "$file" <<'PY'
import os, sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
for key in ("OWNER", "REPO", "TITLE", "TAGLINE"):
    text = text.replace(f"__{key}__", os.environ[key])
path.write_text(text)
PY
}

add_docs_site_role() {
  local roles="$TARGET/agents/roles.yml"
  if [ ! -f "$roles" ]; then
    echo "avertissement : agents/roles.yml absent — rôle docs-site non ajouté" >&2
    return
  fi
  if grep -q 'docs-site:' "$roles"; then
    return
  fi
  python3 - "$roles" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
block = """  docs-site:
    paths:
      - docs-site/
"""
if "docs-site:" in text:
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
  echo "ajouté rôle docs-site dans agents/roles.yml"
}

copy_stubs() {
  mkdir -p "$TARGET/docs/changelog" "$TARGET/docs/bugs" "$TARGET/docs/feuille-de-route" "$TARGET/docs/features" "$TARGET/docs/adr"
  for pair in \
    "changelog/README.md:docs/changelog/README.md" \
    "bugs/README.md:docs/bugs/README.md" \
    "feuille-de-route/README.md:docs/feuille-de-route/README.md" \
    "features/index.md:docs/features/index.md"
  do
    src="${pair%%:*}"
    dest="${pair##*:}"
    if [ ! -f "$TARGET/$dest" ] && [ -f "$STUBS/$src" ]; then
      mkdir -p "$(dirname "$TARGET/$dest")"
      rsync -a "$STUBS/$src" "$TARGET/$dest"
      echo "créé   $dest"
    fi
  done
  # An empty docs/adr/ leaves adrSidebar with nothing to link to: build fails.
  if [ -z "$(find "$TARGET/docs/adr" -maxdepth 1 \( -name '*.md' -o -name '*.mdx' \) -print -quit)" ]; then
    rsync -a "$STUBS/adr/index.md" "$TARGET/docs/adr/index.md"
    echo "créé   docs/adr/index.md"
  fi
  if [ ! -f "$TARGET/docs/glossaire.md" ]; then
    printf '%s\n' '# Glossary' > "$TARGET/docs/glossaire.md"
    echo "créé   docs/glossaire.md"
  fi
}

copy_workflow() {
  mkdir -p "$TARGET/.github/workflows"
  if [ ! -f "$TARGET/.github/workflows/deploy-docs.yml" ]; then
    rsync -a "$WF_SRC" "$TARGET/.github/workflows/deploy-docs.yml"
    echo "créé   .github/workflows/deploy-docs.yml"
  elif [ "$MODE_FORCE_OWNED" -eq 1 ]; then
    rsync -a "$WF_SRC" "$TARGET/.github/workflows/deploy-docs.yml"
    echo "MAJ    .github/workflows/deploy-docs.yml"
  fi
}

sync_owned_only() {
  local owned="$TMPL/PACK_OWNED.txt"
  if [ ! -f "$owned" ]; then
    echo "PACK_OWNED.txt introuvable" >&2
    exit 1
  fi
  while IFS= read -r rel || [ -n "$rel" ]; do
    [[ -z "$rel" || "$rel" =~ ^# ]] && continue
    if [ -e "$TMPL/$rel" ]; then
      mkdir -p "$(dirname "$TARGET/docs-site/$rel")"
      rsync -a "$TMPL/$rel" "$TARGET/docs-site/$rel"
      echo "MAJ    docs-site/$rel"
    fi
  done < "$owned"
  # Always refresh workflow when syncing owned
  rsync -a "$WF_SRC" "$TARGET/.github/workflows/deploy-docs.yml"
  echo "MAJ    .github/workflows/deploy-docs.yml"
}

# Known defects left by older templates in a project's docs-site/ (files
# outside PACK_OWNED): tsconfig pointing outside docs-site or not extending
# @docusaurus/tsconfig, data stubs with the wrong JSON shape, @font-face
# reading a file outside docs-site, static/ without any file. Valid project
# content is left alone.
repair_known_defects() {
  python3 - "$TARGET/docs-site" "$TMPL" <<'PY'
import json, re, shutil, sys
from pathlib import Path
site, tmpl = Path(sys.argv[1]), Path(sys.argv[2])

def report(rel):
    print(f"réparé docs-site/{rel}")

rel = "tsconfig.json"
cfg = site / rel
text = cfg.read_text() if cfg.exists() else ""
if '"../' in text or "@docusaurus/tsconfig" not in text:
    shutil.copyfile(tmpl / rel, cfg)
    report(rel)

shapes = {
    "src/data/bugs.json": lambda d: isinstance(d, dict) and isinstance(d.get("bugs"), list),
    "src/data/changelog.json": lambda d: isinstance(d, list),
    "src/data/feuille-de-route.json": lambda d: isinstance(d, dict)
        and isinstance(d.get("versions"), list) and isinstance(d.get("plusTard"), list),
}
for rel, valid in shapes.items():
    data = site / rel
    try:
        ok = valid(json.loads(data.read_text()))
    except (OSError, ValueError):
        ok = False
    if not ok:
        data.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tmpl / rel, data)
        report(rel)

# Docusaurus fails the build on a static/ without any file (git drops
# empty dirs, so older scaffolds from a pack clone had none).
static = site / "static"
if not static.is_dir() or not any(p.is_file() for p in static.rglob("*")):
    static.mkdir(exist_ok=True)
    (static / ".nojekyll").touch()
    report("static/.nojekyll")

rel = "src/css/custom.css"
css = site / rel
if css.exists():
    text = css.read_text()
    cleaned = re.sub(r"@font-face\s*\{[^}]*url\(\s*[\"']?\.\./\.\./\.\./[^}]*\}\s*", "", text)
    if cleaned != text:
        css.write_text(cleaned)
        report(rel)
PY
}

print_next_steps() {
  echo "Étapes suivantes :"
  echo "  cd docs-site && npm install && npm run typecheck"
  echo "  GitHub → Settings → Pages → Source : GitHub Actions (après le premier push)"
}

if [ -d "$TARGET/docs-site" ] && [ -f "$TARGET/docs-site/package.json" ]; then
  if [ "$MODE_FORCE_OWNED" -eq 1 ]; then
    echo "docs-site présent — sync chemins PACK_OWNED uniquement"
    sync_owned_only
    repair_known_defects
    add_docs_site_role
    copy_stubs
    print_next_steps
  else
    echo "docs-site déjà présent — rien (passe --force-owned pour rafraîchir les fichiers pack)"
  fi
  exit 0
fi

echo "Scaffold docs-site → $TARGET (owner=$OWNER repo=$REPO)"
mkdir -p "$TARGET/docs-site"
rsync -a --exclude .DS_Store --exclude node_modules --exclude build --exclude .docusaurus \
  "$TMPL"/ "$TARGET/docs-site/"
apply_placeholders "$TARGET/docs-site/docusaurus.config.ts"
copy_stubs
copy_workflow
add_docs_site_role
echo "docs-site prêt."
print_next_steps
