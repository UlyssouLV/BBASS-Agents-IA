#!/usr/bin/env python3
"""Refuse une écriture Moduléo (POST/PUT/PATCH/DELETE) dans le code de lecture.

Claude Code (PreToolUse) et Cursor (preToolUse). Deny = exit 2.
Ne se déclenche que sur Write/Edit/StrReplace vers le client ou les outils
Moduléo. Les docs, JSON de catalogue et tests hors src passent.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_MESSAGE_BLOCAGE = (
    "Écriture Moduléo refusée (ADR-0017) : le client et les outils restent "
    "en GET seul. Passe par ClientModuleo.lire(..., droits). "
    "Toute écriture (POST/PUT/PATCH/DELETE) exige une nouvelle décision "
    "et le serveur de test."
)

_OUTILS_ECRITURE = {"Write", "Edit", "StrReplace", "MultiEdit"}

_CHEMINS_PROD = (
    "vm-centrale/src/vm_centrale/moduleo/",
    "vm-centrale/src/vm_centrale/outils/moduleo/",
)

_SUFFIXES_IGNORER = (".md", ".json", ".png")

_APPEL_ECRITURE = re.compile(
    r"(?:"
    r"\.(?:post|put|patch|delete)\s*\("
    r"|httpx\.(?:post|put|patch|delete)"
    r"|requests\.(?:post|put|patch|delete)"
    r"|envoyer\s*\(\s*['\"](?:POST|PUT|PATCH|DELETE)"
    r"|method\s*=\s*['\"](?:POST|PUT|PATCH|DELETE)"
    r")",
    re.IGNORECASE,
)


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
    evenement = str(payload.get("hook_event_name") or "").lower()
    if evenement in {"pretooluse", "subagentstart"}:
        return True
    return bool(payload.get("cursor_version"))


def _entree(payload: dict) -> dict:
    entree = payload.get("tool_input") or payload.get("input") or {}
    return entree if isinstance(entree, dict) else {}


def _chemin(entree: dict) -> str:
    brut = entree.get("path") or entree.get("file_path") or entree.get("filePath") or ""
    return str(brut).replace("\\", "/")


def _dans_perimetre(chemin: str) -> bool:
    if not chemin or chemin.lower().endswith(_SUFFIXES_IGNORER):
        return False
    normalise = chemin if not Path(chemin).is_absolute() else chemin
    return any(fragment in normalise for fragment in _CHEMINS_PROD)


def _textes(entree: dict) -> list[str]:
    morceaux: list[str] = []
    for cle in ("contents", "content", "new_string", "newString"):
        valeur = entree.get(cle)
        if isinstance(valeur, str):
            morceaux.append(valeur)
    edits = entree.get("edits")
    if isinstance(edits, list):
        for piece in edits:
            if isinstance(piece, dict):
                for cle in ("new_string", "newString", "content"):
                    valeur = piece.get(cle)
                    if isinstance(valeur, str):
                        morceaux.append(valeur)
    return morceaux


def _ecriture_http(texte: str) -> bool:
    return _APPEL_ECRITURE.search(texte) is not None


def _bloquer(cursor: bool) -> int:
    if cursor:
        json.dump(
            {
                "permission": "deny",
                "user_message": _MESSAGE_BLOCAGE,
                "agent_message": _MESSAGE_BLOCAGE,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": _MESSAGE_BLOCAGE,
                },
            },
            sys.stdout,
            ensure_ascii=False,
        )
    else:
        json.dump(
            {
                "decision": "block",
                "reason": _MESSAGE_BLOCAGE,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": _MESSAGE_BLOCAGE,
                },
            },
            sys.stdout,
            ensure_ascii=False,
        )
    print(_MESSAGE_BLOCAGE, file=sys.stderr)
    return 2


def _autoriser(cursor: bool) -> int:
    if cursor:
        json.dump({"permission": "allow"}, sys.stdout)
    return 0


def doit_bloquer(payload: dict) -> bool:
    outil = str(payload.get("tool_name") or payload.get("tool") or "")
    if outil not in _OUTILS_ECRITURE:
        return False
    entree = _entree(payload)
    if not _dans_perimetre(_chemin(entree)):
        return False
    return any(_ecriture_http(texte) for texte in _textes(entree))


def main() -> int:
    payload = _charge()
    cursor = _est_cursor(payload)
    if doit_bloquer(payload):
        return _bloquer(cursor)
    return _autoriser(cursor)


if __name__ == "__main__":
    raise SystemExit(main())
