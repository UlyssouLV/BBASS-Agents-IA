#!/usr/bin/env python3
"""Refuse a Mistral client or key on the poste (ADR-0002).

The poste talks only to the VM centrale. A model that « simplifies » by
calling api.mistral.ai from poste/ would leak the shared cabinet key.

  py -3 .claude/hooks/gate-poste-sans-mistral.py --scan
  stdin JSON (Claude Code PreToolUse Write|Edit): deny if the written
  path is under poste/ and the new contents match a banned pattern.

Exit 2 + deny JSON when blocking a tool call; exit 1 when --scan finds a hit.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
_POSTE = _RACINE / "poste"

# Intentionally not the word "Mistral" (comments may mention the VM timeout).
_INTERDIT = re.compile(
    r"MISTRAL_API_KEY|api\.mistral\.ai|console\.mistral\.ai|mistralai",
    re.IGNORECASE,
)

_MESSAGE = (
    "Le poste n'appelle pas Mistral et ne détient pas MISTRAL_API_KEY "
    "(ADR-0002). Passe par la VM centrale."
)


def _est_sous_poste(chemin: Path) -> bool:
    try:
        chemin.resolve().relative_to(_POSTE.resolve())
    except ValueError:
        return False
    return True


def _fichiers_a_scanner() -> list[Path]:
    candidats: list[Path] = []
    for racine in (_POSTE / "src", _POSTE / "tests"):
        if not racine.is_dir():
            continue
        candidats.extend(
            p
            for p in racine.rglob("*")
            if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".js", ".env", ".toml"}
        )
    return candidats


def _premier_hit(texte: str) -> str | None:
    trouve = _INTERDIT.search(texte)
    return trouve.group(0) if trouve else None


def _scan() -> int:
    hits: list[str] = []
    for fichier in _fichiers_a_scanner():
        try:
            texte = fichier.read_text(encoding="utf-8")
        except OSError:
            continue
        motif = _premier_hit(texte)
        if motif:
            rel = fichier.relative_to(_RACINE)
            hits.append(f"{rel}: {motif}")
    if not hits:
        return 0
    print(_MESSAGE, file=sys.stderr)
    for ligne in hits:
        print(ligne, file=sys.stderr)
    return 1


def _bloquer() -> int:
    json.dump(
        {
            "decision": "block",
            "reason": _MESSAGE,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": _MESSAGE,
            },
        },
        sys.stdout,
        ensure_ascii=False,
    )
    print(_MESSAGE, file=sys.stderr)
    return 2


def _charge() -> dict:
    brut = sys.stdin.read()
    if not brut.strip():
        return {}
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        return {}


def _chemin_et_contenu(payload: dict) -> tuple[Path | None, str]:
    entree = payload.get("tool_input") or payload.get("input") or {}
    brut = (
        entree.get("file_path")
        or entree.get("path")
        or payload.get("file_path")
        or ""
    )
    contenu = entree.get("content") or entree.get("contents") or entree.get("new_string") or ""
    if not brut:
        return None, str(contenu)
    return Path(str(brut)), str(contenu)


def _outil_ecriture(payload: dict) -> bool:
    outil = str(payload.get("tool_name") or payload.get("tool") or "")
    return outil in {"Write", "Edit", "StrReplace"}


def main(argv: list[str]) -> int:
    if "--scan" in argv:
        return _scan()
    payload = _charge()
    if not _outil_ecriture(payload):
        return 0
    chemin, contenu = _chemin_et_contenu(payload)
    if chemin is None or not _est_sous_poste(chemin):
        return 0
    a_verifier = contenu if contenu else ""
    if not a_verifier and chemin.is_file():
        try:
            a_verifier = chemin.read_text(encoding="utf-8")
        except OSError:
            return 0
    if _premier_hit(a_verifier):
        return _bloquer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
