#!/usr/bin/env python3
"""Bloque /code-review sauf demande utilisateur ou « Finalise la version ».

Claude Code (PreToolUse) et Cursor (preToolUse / subagentStart).
Deny = exit 2. Ne pas inventer un path. Ne pas dumper de secrets.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_MESSAGE_BLOCAGE = (
    "Fin de /implement = skill encadrer-implement (tests verts, commit, push, "
    "fermeture de l'enfant). /code-review seulement si le message utilisateur "
    "courant le demande explicitement, ou lors de « Finalise la version »."
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


def _est_identifiant_code_review(valeur: object) -> bool:
    minuscule = str(valeur or "").strip().strip("/").lower()
    if not minuscule:
        return False
    if minuscule in {"code-review", "code_review"}:
        return True
    return minuscule.endswith(":code-review") or minuscule.endswith(":code_review")


def _est_code_review(payload: dict) -> bool:
    outil = str(payload.get("tool_name") or payload.get("tool") or "")
    if outil and outil not in {"Skill", "Agent", "Task"}:
        return False
    entree = payload.get("tool_input") or payload.get("input") or {}
    if not isinstance(entree, dict):
        entree = {}
    candidats = [
        entree.get("skill"),
        entree.get("subagent_type"),
        payload.get("skill"),
        payload.get("subagent_type"),
        payload.get("agent_type"),
    ]
    return any(_est_identifiant_code_review(candidat) for candidat in candidats)


def _dernier_message_utilisateur(chemin: str) -> str:
    if not chemin:
        return ""
    path = Path(chemin)
    if not path.is_file():
        return ""
    dernier = ""
    try:
        with path.open(encoding="utf-8") as flux:
            for ligne in flux:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    evenement = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                role = str(evenement.get("type") or evenement.get("role") or "")
                if role not in {"user", "human"}:
                    continue
                message = evenement.get("message") or evenement.get("content") or ""
                if isinstance(message, dict):
                    parties = message.get("content") or []
                    if isinstance(parties, str):
                        dernier = parties
                    elif isinstance(parties, list):
                        morceaux = []
                        for partie in parties:
                            if isinstance(partie, dict) and partie.get("type") == "text":
                                morceaux.append(str(partie.get("text") or ""))
                            elif isinstance(partie, str):
                                morceaux.append(partie)
                        dernier = "\n".join(morceaux)
                elif isinstance(message, str):
                    dernier = message
                elif isinstance(message, list):
                    dernier = " ".join(str(p) for p in message)
    except OSError:
        return ""
    return dernier


def _chemin_transcript(payload: dict) -> str:
    return str(
        payload.get("transcript_path")
        or os.environ.get("CURSOR_TRANSCRIPT_PATH")
        or ""
    )


def _utilisateur_demande_review(texte: str) -> bool:
    minuscule = texte.lower()
    if "/code-review" in minuscule or "code-review" in minuscule:
        return True
    return (
        "finalise la version" in minuscule
        or "finalize the version" in minuscule
        or "clôture la version" in minuscule
        or "cloture la version" in minuscule
    )


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


def main() -> int:
    payload = _charge()
    cursor = _est_cursor(payload)
    if not _est_code_review(payload):
        return _autoriser(cursor)
    if _utilisateur_demande_review(_dernier_message_utilisateur(_chemin_transcript(payload))):
        return _autoriser(cursor)
    return _bloquer(cursor)


if __name__ == "__main__":
    raise SystemExit(main())
