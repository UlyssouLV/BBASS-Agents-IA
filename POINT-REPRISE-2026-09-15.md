# Point de reprise — 15 septembre 2026


Repo : [UlyssouLV/BBASS-Agents-IA](https://github.com/UlyssouLV/BBASS-Agents-IA)  
Branche : **`feat/v1-socle`**  
PR Draft : [**#12 — titre V1.0.0**](https://github.com/UlyssouLV/BBASS-Agents-IA/pull/12) → `main` (**ne pas merger** tant que #9 n’est pas propre).  
Auteur Git / GitHub : UlyssouLV.

---

## Demain matin (ordre)

1. **Ne pas** relancer un `/code-review` multi-agents d’emblée (ça a vidé la jauge **session** Claude Code à 100 % ; reset **20h** Europe/Paris le 14/09). Quota **semaine** ~17 % jusqu’au **21 sept. 9h**. pytest = local, **0 token**.
2. **Supprimer** à la racine s’ils sont encore là : `committed.diff.txt`, `uncommitted.diff.txt` (artefacts `/code-review`, pas produit).
3. **Finir #9** : corriger les 2 bugs de la review (voir ci-dessous), pytest poste + VM, puis skill `apres-implement-awaiting-merge` (demander avant de labeller).
4. **Committer / pousser** par lots cohérents (voir « Working tree ») — **jamais** `.env` / `.db`.
5. Quand #9 est sur la branche + `awaiting-merge` : #1 n’est plus bloqué **côté code** (reste essai Mistral live + merge PR + release).

Autre PC : le **quota** Claude suit le **compte** ; le **fil de chat** de cette machine **non**. Reprendre le repo (`git pull` + `.env` local). Prompt type : *issue #9, 2 bugs review (clé admin vide, identifiant VM au démarrage)*.

---

## Ce qu’on a tranché / livré le 14/09

### Produit V1 (#1)

- Socle : poste local (HTML/CSS/JS) + VM FastAPI, relais Mistral, jeton `/relais`, timeouts, ADR-0004 (modèle décidé par la VM).
- US #3 : **session Windows** (grilling → option B) : keyring poste + jetons persistés VM + révocation. **Code #9 présent en working tree, bugs review non patchés.**
- US #5 : prénom/nom obligatoires, affichage `Prénom Nom (identifiant)` — **#10 et #11 commités** (`2ef1990`, `d7cb79b`).
- US #9 : appel Mistral réel via relais ; **clé dans `vm-centrale/.env` seulement** (gitignoré). Relancer la VM après édition `.env`.
- Python **3.11** figé (`>=3.11,<3.12`) ; installeur Windows [3.11.9](https://www.python.org/downloads/release/python-3119/). Deps **directes** en `==` dans les `pyproject.toml`.
- README : section **Lancer en local** **après Suite**. Compte démo local `j.dupont` / `azerty` (seed manuel, pas Git). Recréer `vm_centrale.db` si le schéma a changé (`create_all` n’ajoute pas de colonnes).

### Process

- Cycle : branche → issues Open → implement → PR → **merge `main`** → close issues (`Fixes`) → **supprimer la branche** → **GitHub Release semver** sur le commit `main`.
- Label **`awaiting-merge`** = développé sur la branche, **pas** Closed. Retirer `ready-for-agent`.
- Skills : `demander-avant-commit`, `fermer-issues-apres-merge-main` (release + awaiting-merge), **`apres-implement-awaiting-merge`** (demander avant le label).
- #7 et #8 **rouvertes** + `awaiting-merge` (fermées trop tôt).
- Mistral : **un compte Studio / API**, **une clé sur la VM**, deux *modèles* plus tard (discussion vs code) — **pas** Le Chat Pro par collab. Hors V1 : #6 profils.

### PR vs release

La PR s’appelle V1.0.0 = **titre**. La **release `v1.0.0`** = tag **après merge** sur `main`. Supprimer `feat/v1-socle` après merge ne casse pas le tag.

---

## Issues GitHub (ne pas closer avant merge `main`)

| # | État | Label | Code |
|---|------|--------|------|
| 1 | Open | `ready-for-agent` | Parente V1 — **pas** `awaiting-merge` tant que #9 n’est pas fini |
| 2–5, 7, 8, 10, 11 | Open | `awaiting-merge` | Sur la branche (10/11 commités ; 2–5/7/8 plus tôt) |
| **9** | Open | **`ready-for-agent`** | **À finir** (bugs review) |
| 6 | Open | `needs-triage` | **Hors V1** — pas dans `Fixes` de la PR |

`Fixes` PR #12 : `#1 #2 #3 #4 #5 #7 #8 #9 #10 #11` (pas #6). GitHub ne ferme qu’**au merge**.

---

## Ce qui reste pour **finir #1 proprement**

### A. Code bloquant — #9

Review Claude (session coupée avant le patch) :

1. **`VM_ADMIN_KEY` vide** (`.env` : `VM_ADMIN_KEY=`) : `get()` renvoie `""`, pas `None` → `compare_digest` peut accepter une clé admin vide. Traiter `""` comme non configuré → **401**. Tests.
2. **`verifier_session_au_demarrage`** : après `client.verifier(jeton)`, réouvrir avec **`identifiant_verifie` (VM)**, pas `donnees.identifiant` (keyring). Éviter le `ouvrir()` qui **réécrit** le keyring pour rien. Remettre **`persistance_degradee = False`** si `set_password` réussit (aujourd’hui le flag ne redescend jamais).

Puis : pytest `vm-centrale` + `poste` ; awaiting-merge #9 ; commit #9 seul (ou avec tests jetons / révocation déjà dans le WT).

Fichiers #9 typiques (WT au 14/09 soir) : `session.py`, `main.py`, `vm_centrale_client.py`, `jetons.py`, `auth.py`, `config.py`, tests `test_session_persistee.py`, `test_verification_au_demarrage.py`, `test_jetons.py`, `test_verification_et_revocation.py`, etc.

### B. Commits / push (pas encore Git)

Mélanger **plusieurs sujets** dans un commit = à éviter.

Lots possibles :

- **#9** (poste + VM session / jetons / admin) — après les 2 bugs.
- **Docs process** : `AGENTS.md`, `docs/agents/triage-labels.md`, `.claude/skills/fermer-issues-apres-merge-main/`, **nouveau** `.claude/skills/apres-implement-awaiting-merge/`.
- **README + freeze** : `README.md`, `poste/pyproject.toml`, `vm-centrale/pyproject.toml` (`requires-python` + `==` deps).

**Ne pas committer :** `.env`, `*.db`, `committed.diff.txt`, `uncommitted.diff.txt`.

Pousser `feat/v1-socle` : la PR #12 se met à jour toute seule.

### C. Validation humaine #1 (hors tickets)

- Recréer SQLite + seed prénom/nom si besoin.
- VM depuis `vm-centrale` (`PYTHONPATH=src`, `.venv`).
- Poste idem, [http://127.0.0.1:8100](http://127.0.0.1:8100).
- Chat **réel** Mistral (US #9).
- Session : relancer le process poste → toujours connecté (#9) ; déconnexion explicite.

### D. Clôturer V1 (plus tard, pas demain matin)

- Sortir le **Draft** PR #12 quand #9 est dessus.
- Merge `main` → issues `Fixes` se ferment.
- Supprimer `feat/v1-socle`.
- **Release GitHub `v1.0.0`** sur le commit mergé (notes : résumé, liste, hors #6). **Demander** avant `gh release` (skill).

---

## Commandes utiles

```powershell
cd vm-centrale
.\.venv\Scripts\python.exe -m pytest

cd ..\poste
.\.venv\Scripts\python.exe -m pytest
```

Lancer : README, section finale. Relancer la VM après `.env`.

---

## Ce qu’on ne fait pas dans #1

- #6 profils Mistral.
- Agents métiers, satellites, launcher, historique persisté.
- Fermer des issues parce que « c’est codé sur la branche ».
- Merger `main` avec les bugs #9 encore ouverts.

---

## Prompt pour Claude demain (#9)

> Branche `feat/v1-socle`, issue #9 déjà majoritairement implémentée (working tree). Ne pas closer d’issues. Ne pas committer sans OK.
>
> Corrige uniquement les findings `/code-review` :
> 1. `VM_ADMIN_KEY` vide / absente → révocation admin toujours 401 (`""` ≠ unset aujourd’hui).
> 2. Au démarrage poste, utiliser l’identifiant renvoyé par `verifier` (VM), pas celui du keyring ; ne pas réécrire le keyring inutilement ; reset `persistance_degradee` si la persistance réussit.
>
> Tests pytest. Puis demande awaiting-merge #9 (skill). Supprime committed.diff.txt / uncommitted.diff.txt s’ils restent.
>
> Hors scope : #6, merge PR #12, README déjà traité ailleurs dans le WT.

---

*Rédigé le 14/09/2026 en fin de journée. Claude Code session limitée ; reprise prévue le 15/09.*
