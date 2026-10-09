#!/usr/bin/env python3
"""Preuve que le hook refuse un POST Moduléo et laisse passer le reste."""

from __future__ import annotations

import unittest

from hook import doit_bloquer

_CLIENT = "vm-centrale/src/vm_centrale/moduleo/client.py"
_OUTIL = "vm-centrale/src/vm_centrale/outils/moduleo/devis/outil.py"


class TestBloqueEcritureModuleo(unittest.TestCase):
    def test_refuse_un_post_sur_le_client(self) -> None:
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "path": _CLIENT,
                "contents": "reponse = _http_client.post(url, json=corps)\n",
            },
        }
        self.assertTrue(doit_bloquer(payload))

    def test_laisse_passer_un_get_sur_le_client(self) -> None:
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "path": _CLIENT,
                "contents": "reponse = _http_client.get(url, params=params)\n",
            },
        }
        self.assertFalse(doit_bloquer(payload))

    def test_ignore_un_fichier_hors_moduleo(self) -> None:
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "path": "vm-centrale/src/vm_centrale/main.py",
                "contents": "client.post(url)\n",
            },
        }
        self.assertFalse(doit_bloquer(payload))

    def test_ignore_un_readme(self) -> None:
        payload = {
            "tool_name": "StrReplace",
            "tool_input": {
                "path": "vm-centrale/src/vm_centrale/moduleo/README.md",
                "new_string": "Jamais de POST vers Moduléo.\n",
            },
        }
        self.assertFalse(doit_bloquer(payload))

    def test_refuse_un_envoyer_post_dans_un_outil(self) -> None:
        payload = {
            "tool_name": "StrReplace",
            "tool_input": {
                "path": _OUTIL,
                "new_string": 'return client.envoyer("POST", route, params, droits)\n',
            },
        }
        self.assertTrue(doit_bloquer(payload))


if __name__ == "__main__":
    unittest.main()
