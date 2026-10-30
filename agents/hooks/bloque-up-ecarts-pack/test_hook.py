#!/usr/bin/env python3
"""Preuve que le hook refuse /up tant qu'un écart avec le pack est à reporter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from hook import lance_up, sujets_a_reporter

_HOOK = Path(__file__).resolve().parent / "hook.py"

_ECARTS_A_REPORTER = """| Date | Sujet | Fichiers du dépôt | Où dans le pack | Statut |
| --- | --- | --- | --- | --- |
| 2026-10-29 | Numéro produit | voir ci-dessous | voir ci-dessous | à reporter |
| 2026-10-01 | Ancien écart | x | y | reporté |
"""


class TestBloqueUpEcartsPack(unittest.TestCase):
    def test_reconnait_le_skill_up(self) -> None:
        payload = {"tool_name": "Skill", "tool_input": {"skill": "mettre-a-jour-le-pack"}}
        self.assertTrue(lance_up(payload))

    def test_reconnait_le_script_dans_bash(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "bash ../workflow-agents-pack/agents/scripts/update-from-pack.sh --with-docs"},
        }
        self.assertTrue(lance_up(payload))

    def test_reconnait_le_script_dans_le_shell_cursor(self) -> None:
        payload = {"hook_event_name": "beforeShellExecution", "command": "sh adopter-le-pack.sh"}
        self.assertTrue(lance_up(payload))

    def test_reconnait_le_script_apres_cd(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "cd /depot && ./agents/scripts/update-from-pack.sh"}}
        self.assertTrue(lance_up(payload))

    def test_ignore_une_simple_mention_du_script(self) -> None:
        mentions = [
            "grep -n update-from-pack.sh agents/README.md",
            "cat >> guide.md <<'EOF'\nscripts update-from-pack.sh / adopter-le-pack.sh\nEOF\ntail -2 guide.md",
            'git commit -m "Bloque update-from-pack.sh tant que le pack est en retard"',
        ]
        for commande in mentions:
            with self.subTest(commande=commande):
                self.assertFalse(lance_up({"tool_name": "Bash", "tool_input": {"command": commande}}))

    def test_ignore_un_autre_skill_ou_commande(self) -> None:
        self.assertFalse(lance_up({"tool_name": "Skill", "tool_input": {"skill": "commit"}}))
        self.assertFalse(lance_up({"tool_name": "Bash", "tool_input": {"command": "git status"}}))

    def test_liste_seulement_les_ecarts_a_reporter(self) -> None:
        self.assertEqual(sujets_a_reporter(_ECARTS_A_REPORTER), ["Numéro produit"])

    def test_rien_a_reporter_quand_tout_est_reporte(self) -> None:
        texte = _ECARTS_A_REPORTER.replace("| à reporter |", "| reporté |")
        self.assertEqual(sujets_a_reporter(texte), [])

    def _lancer(self, skill: str, ecarts: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as dossier:
            fichier = Path(dossier) / "ecarts.md"
            fichier.write_text(ecarts, encoding="utf-8")
            payload = {"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {"skill": skill}}
            return subprocess.run(
                [sys.executable, str(_HOOK)],
                input=json.dumps(payload).encode("utf-8"),
                capture_output=True,
                env={**os.environ, "ECARTS_PACK": str(fichier)},
            )

    def test_le_hook_refuse_up_avec_un_ecart_a_reporter(self) -> None:
        resultat = self._lancer("mettre-a-jour-le-pack", _ECARTS_A_REPORTER)
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("« Numéro produit »", resultat.stderr.decode("utf-8"))

    def test_le_hook_laisse_passer_up_quand_tout_est_reporte(self) -> None:
        resultat = self._lancer("mettre-a-jour-le-pack", _ECARTS_A_REPORTER.replace("| à reporter |", "| reporté |"))
        self.assertEqual(resultat.returncode, 0)

    def test_le_hook_laisse_passer_un_autre_skill(self) -> None:
        resultat = self._lancer("commit", _ECARTS_A_REPORTER)
        self.assertEqual(resultat.returncode, 0)

if __name__ == "__main__":
    unittest.main()
