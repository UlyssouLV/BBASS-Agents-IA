#!/usr/bin/env python3
"""Refuse /up tant qu'une modification locale n'est pas reportée dans le pack.

Claude Code (PreToolUse : Skill, Bash) et Cursor (preToolUse : Skill ;
beforeShellExecution). Deny = exit 2.
Lit agents/docs/ecarts-avec-le-pack.md : une ligne de tableau au statut
« à reporter » bloque le skill mettre-a-jour-le-pack et les scripts
update-from-pack.sh / adopter-le-pack.sh, qui écraseraient ces modifications.
Fichier absent ou sans ligne « à reporter » : tout passe.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ECARTS_PACK : autre fichier, pour les tests seulement.
_ECARTS = Path(
    os.environ.get("ECARTS_PACK")
    or Path(__file__).resolve().parents[3] / "agents" / "docs" / "ecarts-avec-le-pack.md"
)

_SKILL_UP = "mettre-a-jour-le-pack"

# Le script en position de commande : début de segment (après ; & | ( ou une
# nouvelle ligne), éventuellement derrière bash / sh / env. Une simple mention
# (grep, cat, texte d'un heredoc, chaîne entre guillemets) passe.
_SCRIPTS_PACK = re.compile(
    r"(?:^|[;&|(\n])\s*(?:(?:env|bash|sh|exec)\s+(?:-\S+\s+)*)*"
    r"[^\s;&|()'\"]*(?:update-from-pack|adopter-le-pack)\.sh(?=$|[\s;&|)])"
)
_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\s*(?:\n|$)", re.S)
_GUILLEMETS = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")


def _sans_texte(commande: str) -> str:
    """Retire corps de heredoc et chaînes entre guillemets : seules les commandes restent."""
    return _GUILLEMETS.sub("''", _HEREDOC.sub("\n", commande))

_STATUT_A_REPORTER = "à reporter"


def _charge() -> dict:
    brut = sys.stdin.buffer.read()
    if brut.startswith(b"\xef\xbb\xbf"):
        brut = brut[3:]
    texte = brut.decode("utf-8", errors="replace").strip()
    if not texte:
        return {}
    try:
        return json.loads(texte)
    except json.JSONDecodeError:
        return {}


def _est_cursor(payload: dict) -> bool:
    # Cursor : camelCase (preToolUse, beforeShellExecution) ou cursor_version.
    # Claude Code : PascalCase (PreToolUse). Ne pas lower().
    if payload.get("cursor_version"):
        return True
    evenement = str(payload.get("hook_event_name") or "")
    return evenement in {"preToolUse", "beforeShellExecution"}


def _entree(payload: dict) -> dict:
    entree = payload.get("tool_input") or payload.get("input") or {}
    return entree if isinstance(entree, dict) else {}


def lance_up(payload: dict) -> bool:
    """Vrai si l'appel lance /up : le skill, ou un script du pack dans le shell."""
    entree = _entree(payload)
    outil = str(payload.get("tool_name") or payload.get("tool") or "")
    if outil == "Skill":
        nom = str(entree.get("skill") or entree.get("name") or "")
        return nom.split(":")[-1].lstrip("/") == _SKILL_UP
    commande = str(payload.get("command") or entree.get("command") or "")
    return _SCRIPTS_PACK.search(_sans_texte(commande)) is not None


def sujets_a_reporter(texte: str) -> list[str]:
    """Sujets (2e colonne) des lignes de tableau dont une cellule vaut « à reporter »."""
    sujets: list[str] = []
    for ligne in texte.splitlines():
        if not ligne.lstrip().startswith("|"):
            continue
        cellules = [cellule.strip() for cellule in ligne.strip().strip("|").split("|")]
        if any(cellule.lower() == _STATUT_A_REPORTER for cellule in cellules):
            sujets.append(cellules[1] if len(cellules) > 1 else cellules[0])
    return sujets


def _lire_ecarts() -> str:
    try:
        return _ECARTS.read_text(encoding="utf-8")
    except OSError:
        return ""


def _message(sujets: list[str]) -> str:
    liste = " ; ".join(f"« {sujet} »" for sujet in sujets)
    return (
        "/up refusé : des modifications locales ne sont pas encore reportées dans le pack "
        f"(agents/docs/ecarts-avec-le-pack.md : {liste}). Reporte-les dans "
        "workflow-agents-pack, passe leur statut à « reporté », puis relance /up."
    )


def _bloquer(cursor: bool, message: str) -> int:
    if cursor:
        json.dump(
            {
                "permission": "deny",
                "user_message": message,
                "agent_message": message,
            },
            sys.stdout,
            ensure_ascii=False,
        )
    else:
        json.dump(
            {
                "decision": "block",
                "reason": message,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": message,
                },
            },
            sys.stdout,
            ensure_ascii=False,
        )
    print(message, file=sys.stderr)
    return 2


def _autoriser(cursor: bool) -> int:
    if cursor:
        json.dump({"permission": "allow"}, sys.stdout)
    return 0


def main() -> int:
    payload = _charge()
    cursor = _est_cursor(payload)
    if lance_up(payload):
        sujets = sujets_a_reporter(_lire_ecarts())
        if sujets:
            return _bloquer(cursor, _message(sujets))
    return _autoriser(cursor)


if __name__ == "__main__":
    raise SystemExit(main())
