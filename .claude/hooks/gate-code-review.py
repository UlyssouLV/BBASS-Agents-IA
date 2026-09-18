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


def _est_identifiant_code_review(valeur: object) -> bool:
    # Comparaison sur l'identifiant de skill/agent lui-même (ex. "code-review",
    # "mattpocock-skills:code-review"), jamais sur un texte libre arbitraire :
    # un prompt ou un chemin de fichier qui contient juste la sous-chaîne
    # "code-review" (ex. docs/code-review-notes.md) ne doit pas déclencher le
    # blocage sur un tool call sans rapport.
    minuscule = str(valeur or "").strip().strip("/").lower()
    if not minuscule:
        return False
    if minuscule in {"code-review", "code_review"}:
        return True
    return minuscule.endswith(":code-review") or minuscule.endswith(":code_review")


def _est_code_review(payload: dict) -> bool:
    outil = str(payload.get("tool_name") or payload.get("tool") or "")
    # SubagentStart n'a pas toujours de tool_name (outil == "") : ne pas
    # l'exclure ici, seulement les tool calls clairement étrangers au trio
    # Skill/Agent/Task déjà filtré par le matcher PreToolUse.
    if outil and outil not in {"Skill", "Agent", "Task"}:
        return False
    entree = payload.get("tool_input") or payload.get("input") or {}
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
