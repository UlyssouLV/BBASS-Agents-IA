---
name: lire-moduleo-en-lecture-seule
description: >-
  Constrain Moduléo work to read-only tools behind the rights guard.
  Use when implementing or modifying a Moduléo tool, the HTTP client, or
  the rights guard (outils/moduleo/, moduleo/client.py, moduleo/droits/).
  Not for poste UI, feuille de route, human-test tickets, or non-Moduléo code.
---

# Moduléo : lecture seule, derrière le garde

Paths: **`agents/roles.yml`**. Decisions: ADR-0017, ADR-0018 (role **`adr`**).

## When this applies

A change under `vm-centrale/src/vm_centrale/outils/moduleo/` or
`vm-centrale/src/vm_centrale/moduleo/` (client, droits, fiches, routes).

**Do not** load this skill for poste UI, specs-only edits, human tests, or
unrelated Python.

## Done when (check yourself)

1. Every HTTP call goes through `ClientModuleo.lire(route, paramètres, droits)`
   — no default `droits`, no raw `httpx` / `requests` from a tool.
2. Each GET route used is classified in the versioned routes file (droit
   exigé or libre). An unclassified route must stay refused.
3. A missing right refuses **before** any network send (phrase fixe, inspecteur).
4. No POST / PUT / PATCH / DELETE toward Moduléo, even “to try”.

Stop when those four hold. Do not ask the human if they hold; the tests in
`vm-centrale/tests/test_garde_droits_moduleo.py` and
`vm-centrale/tests/test_client_moduleo.py` are the check.

## Why not an instruction-only reminder

If you only “ask” the model to respect rights, a new route or a POST can
ship. The client + guard + classified routes are the non-negotiable
(confidential cabinet data on a production Moduléo).
