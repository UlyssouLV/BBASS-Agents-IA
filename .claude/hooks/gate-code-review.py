#!/usr/bin/env python3
"""Bloque le skill /code-review sauf si le message utilisateur courant le demande.

Le plugin /implement finit toujours par « use /code-review ». Dans ce dépôt, la
fin d'un enfant est encadrer-implement. Exit 2 + JSON deny.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_MESSAGE_BLOCAGE = (
    "Fin de /implement = skill encadrer-implement (tests verts, commit, push, "
    "fermeture de l'enfant). /code-review seulement si le message utilisateur "
    "courant le demande explicitement."
)


def _charge() -> dict:
    brut = sys.stdin.read()
    if not brut.strip():
        return {}
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        return {}


def _dump(valeur: object) -> str:
    return json.dumps(valeur, ensure_ascii=False).lower()


def _est_code_review(payload: dict) -> bool:
    outil = str(payload.get("tool_name") or payload.get("tool") or "")
    entree = payload.get("tool_input") or payload.get("input") or {}
    texte = " ".join(
        [
            outil,
            str(payload.get("hook_event_name") or ""),
            str(payload.get("agent_type") or ""),
            str(payload.get("subagent_type") or ""),
            str(payload.get("skill") or ""),
            _dump(entree),
            str(payload.get("description") or ""),
        ]
    ).lower()
    return "code-review" in texte or "code_review" in texte


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


def _utilisateur_demande_review(texte: str) -> bool:
    minuscule = texte.lower()
    return "/code-review" in minuscule or "code-review" in minuscule


def _bloquer() -> int:
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


def main() -> int:
    payload = _charge()
    if not _est_code_review(payload):
        return 0
    if _utilisateur_demande_review(
        _dernier_message_utilisateur(str(payload.get("transcript_path") or ""))
    ):
        return 0
    return _bloquer()


if __name__ == "__main__":
    raise SystemExit(main())
