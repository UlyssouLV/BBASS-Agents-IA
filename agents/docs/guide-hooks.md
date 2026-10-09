# Guide des hooks

Hooks **projet** seulement (`agents/hooks/`, jamais `~/.claude` / `~/.cursor`).

Un hook = un dossier `agents/hooks/<nom>/` (script canonique `hook.py`). `/ch` le câble vers Claude Code **et** Cursor. `dispatch.py` ne copie **pas** les hooks.

| Adapter | Câblage |
|---|---|
| Claude Code | `.claude/settings.json` (`PreToolUse`, …) → souvent un wrapper `.claude/hooks/` |
| Cursor | `.cursor/hooks.json` (`version: 1`, `preToolUse` / `subagentStart`, …) |

Nouveau hook : skill **`creer-hook`** (`/ch`). Il ajoute (ou remplace) une section ici, même forme que les pairs.

---

### gate-code-review

**Source :** `agents/hooks/gate-code-review/hook.py`

**Claude :** `PreToolUse`, matcher `Skill\|Agent\|Task` (`.claude/settings.json` → `.claude/hooks/gate-code-review.py`)

**Cursor :** `preToolUse` matcher `Task\|Skill\|Agent` ; `subagentStart` (`.cursor/hooks.json`)

**Fait :** refuse `/code-review` tant que le message utilisateur du tour ne le demande pas, **sauf** « Finalise la version ». Message : enchaîner sur `encadrer-implement`.

### bloque-ecriture-moduleo

**Source :** `agents/hooks/bloque-ecriture-moduleo/hook.py`

**Claude :** `PreToolUse`, matcher `Write\|Edit\|MultiEdit` (`.claude/settings.json` → `.claude/hooks/bloque-ecriture-moduleo.py`)

**Cursor :** `preToolUse` matcher `Write\|StrReplace` (`.cursor/hooks.json`)

**Fait :** refuse d’écrire un appel HTTP POST/PUT/PATCH/DELETE dans le client ou les outils Moduléo (ADR-0017, GET seul). Docs, JSON et fichiers hors de ces dossiers passent.

**Preuve :** `python3 agents/hooks/bloque-ecriture-moduleo/test_hook.py`
