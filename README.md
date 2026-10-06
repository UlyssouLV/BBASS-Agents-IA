# BBASS-Agents-IA

Logiciel d'agents IA pour le cabinet de géomètres-experts BBASS. L'objectif est de mettre à disposition des collaborateurs une interface unique donnant accès à plusieurs agents métiers, capables de les assister sur des tâches courantes du cabinet. Le moteur de langage retenu est Mistral AI, choix du cabinet pour des raisons de souveraineté et de sécurité : ce projet ne consiste pas à entraîner une IA, mais à construire les agents et l'application qui les exploite.

## État actuel

**V1.4.0** disponible : recherche web dans le chat ([#117](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/117)). L'IA peut appeler l'outil `rechercher_web` ; la VM interroge un SearXNG auto-hébergé ([ADR-0013](docs/adr/0013-recherche-web-searxng-auto-heberge.md)), lit les pages, les fait passer par un appel d'extraction isolé ([ADR-0014](docs/adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)), et n'autorise que les URL et chiffres issus de ces résultats. Les outils du modèle sont centralisés dans `vm_centrale/outils/` ; la boucle traite tous les appels sur 3 tours au plus ; l'inspecteur montre le déroulé chronologique (Mistral / local, ligne garde-fous). Bug connu à la livraison : quand la recherche ne trouve rien, l'IA invente encore parfois au lieu de le dire ([#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131), correction en **1.4.5**). Hérite de la **V1.3.1** : le chat ne fige plus ses inventions ([#110](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/110)) — pas de lien inventé, faits inventés refusés sans demande explicite, résumé glissant « proposé, non vérifié », profil réécrit en entier, garde-fous URL et chiffres. Hérite de la **V1.3.0** : Mode développeur (`Ctrl+Maj+D`, Clé d'administration VM, [ADR-0012](docs/adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)). Hérite aussi de la fluidité 1.2.3, du style 1.2.2 et de l'identité visuelle BBASS. Backend local **poste** (React/TypeScript/Vite) et API **VM centrale** (PostgreSQL, relais Mistral, conversations, pièces jointes, consommation, recherche web). Les agents métiers ne sont pas encore construits.

## Ce qu'on construit

Une application composée d'un backend Python et d'une interface web (HTML/CSS/JS), avec des comptes par collaborateur. L'interface prend la forme d'une fenêtre de discussion (type chatbot) servant de point d'entrée vers les différents agents métiers. Le logiciel est destiné à être déployé et mis à jour de façon centralisée, pour être utilisé directement sur les postes des agences.

## Agents prévus

- Administration
- Appels d'offres
- Foncier
- DAO
- Urbanisme
- Détection de réseaux

## Architecture

Le poste n’appelle jamais Mistral directement : tout passe par la VM centrale (réseau interne), qui détient aussi PostgreSQL, la clé API et le moteur de recherche SearXNG.

```mermaid
flowchart LR
  P["Poste<br/>UI locale"] -->|"jamais Mistral"| VM["VM Castries<br/>réseau interne"]
  VM --> PG[("PostgreSQL")]
  VM --> M["API Mistral"]
  VM --> S["SearXNG<br/>localhost"]
```

## Semaine du 05 au 09 octobre 2026

Point visé jeudi 8 octobre : **V1.5.0** (Moduléo lecture), puis **priorité V1.7.0** (déploiement postes / CI/CD), **V1.8.0** (n8n) si le temps le permet. **V1.4.0** livrée le 06/10 (recherche web ; bug connu [#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131) → **1.4.5**). Vendredi 9 : RTT.

```mermaid
flowchart LR
  L05["Lundi 5<br/>V1.2.3, V1.3.0 et V1.3.1 livrées"] --> V140["V1.4.0<br/>recherche web<br/>livrée le 06/10"]
  V140 --> V150["V1.5.0<br/>Moduléo lecture<br/>visé le 07/10"]
  V150 --> V170["V1.7.0<br/>déploiement · priorité"]
  V170 --> V180["V1.8.0<br/>n8n<br/>visé le 08/10"]
```

### Travail réalisé

- **Semaine du 14–18 septembre** — socle jusqu’à **V1.2.0** (comptes admin, persistance conversations, pièces jointes, consommation, front React/TypeScript/Vite).
- **Depuis** — **V1.2.1** (identité visuelle BBASS, disposition type ChatGPT) ; **V1.2.2** (prompt système de style sur le chat principal ; rendu Markdown borné côté poste).
- **Lundi 5 octobre** — **V1.2.3** (cache TanStack Query, pagination par curseur du détail de conversation, instrumentation de temps légère) ; **V1.3.0** (Mode développeur : inspecteur des échanges avec le modèle) ; **V1.3.1** (le chat ne fige plus ses inventions, [#110](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/110) : consignes, résumé glissant, profil de travail, garde-fous URL et chiffres).
- **Mardi 6 octobre** — **V1.4.0** (recherche web : SearXNG, `rechercher_web`, extraction isolée, outils centralisés, inspecteur Mistral / local ; bug connu [#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131) → 1.4.5).

### Reste à implémenter

- **V1.4.5** — dire « pas trouvé » plutôt qu’inventer après une recherche ([#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131)).
- **V1.5.0** — Moduléo en lecture (outil transverse), premier branchement via l’Agent Administration.
- **V1.6.0** — documentation : mémoire conversationnelle et souveraineté des données.
- **V1.7.0** — déploiement postes : CI/CD, conteneurisation, installateur / logiciel d’accès au chat (backend local obligatoire) — **priorité**.
- **V1.8.0** — workflows n8n, branchés sur Moduléo 1.5.0 — **proposé cette semaine** après la 1.7.0.

### Attendu pour la fin de semaine (V1.7.0 prioritaire, V1.8.0 visé)

- **Déjà en place** — poste + VM Castries, PostgreSQL, chat Mistral, conversations bornées + résumé + profil, pièces jointes, consommation, comptes administrateurs, UI React BBASS, style 1.2.2, fluidité 1.2.3, inspecteur 1.3.0, chat sans inventions figées 1.3.1, **recherche web 1.4.0** (SearXNG).
- **V1.5.0** — Q&A lecture Moduléo depuis le chat (pour usage collab pendant l’absence alternance).
- **V1.7.0** — pouvoir **installer / mettre à jour** le logiciel sur les postes (CI/CD, Docker si retenu, installateur ; UI pywebview et/ou navigateur — à trancher).
- **V1.8.0** — socle n8n branché sur Moduléo 1.5.0 (on tente de le livrer jeudi ; non bloquant si seule la 1.7.0 passe).

## Prérequis

- **Python 3.11** (série figée : pas 3.12 / 3.13 / 3.14).
  - Windows : dernier installeur officiel [Python 3.11.9](https://www.python.org/downloads/release/python-3119/) — prendre *Windows installer (64-bit)*. Cocher **Add python.exe to PATH**. Les correctifs 3.11.x plus récents n'ont plus d'installeur (source only).
  - macOS : `brew install python@3.11` (Homebrew), ou l'installeur officiel [Python 3.11.9](https://www.python.org/downloads/release/python-3119/) (*macOS 64-bit universal2 installer*).
- **Docker Desktop** pour le PostgreSQL local de la VM centrale ([ADR-0008](docs/adr/0008-postgresql-vm-centrale.md)) et le moteur de recherche SearXNG de l’outil `rechercher_web` ([ADR-0013](docs/adr/0013-recherche-web-searxng-auto-heberge.md) : image épinglée, `searxng/settings.yml` versionné, publié sur `http://localhost:8888` seulement). Les lanceurs le démarrent tout seuls s’il est installé mais pas lancé (attendre une à deux minutes le premier gel du moteur). Ils ne l’installent pas : Docker Desktop reste à installer une fois à la main.
- Une clé API Mistral (console [La Plateforme](https://console.mistral.ai)) pour un vrai chat

## Démarrer

Après avoir installé les prérequis ci-dessus (Python 3.11, Docker Desktop installé ; Docker Desktop est lancé par le lanceur s’il est arrêté), le parcours officiel est : cloner le dépôt, puis double-cliquer sur l'un des deux scripts à la racine correspondant à ton OS — aucune autre commande à taper.

**Windows** (`.bat`) :

- `lancer-vm.bat` : démarre PostgreSQL et SearXNG puis la VM centrale seule (2 fenêtres : logs Postgres, VM centrale) — utile pour développer/tester la VM seule.
- `lancer-logiciel.bat` : démarre PostgreSQL, SearXNG, la VM centrale et le poste (2 fenêtres : VM centrale, poste), puis ouvre le navigateur sur l'interface.

**macOS** (`.command`, équivalents des `.bat` ci-dessus) :

- `lancer-vm.command` : démarre PostgreSQL et SearXNG puis la VM centrale seule (2 fenêtres Terminal : logs Postgres, VM centrale).
- `lancer-logiciel.command` : démarre PostgreSQL, SearXNG, la VM centrale et le poste (2 fenêtres Terminal : VM centrale, poste), puis ouvre le navigateur sur l'interface.

  Premier lancement : si un clic droit → *Ouvrir* est nécessaire (Gatekeeper, seulement si le dépôt a été téléchargé en `.zip` plutôt que cloné avec `git clone`), ou si le double-clic ne fait rien, exécute une fois dans un Terminal (à la racine du dépôt) `chmod +x lancer-vm.command lancer-logiciel.command` puis retente le double-clic.

Les deux jeux de scripts sont autonomes : au besoin, ils installent [uv](https://docs.astral.sh/uv/) s’il manque ([ADR-0011](docs/adr/0011-gestion-dependances-python-avec-uv.md)), créent les environnements virtuels (`vm-centrale/.venv`, et `poste/.venv` pour `lancer-logiciel.*`), installent les dépendances (`uv sync`, versions figées par `uv.lock`) et créent les fichiers `.env` manquants à partir des `.env.example` correspondants (racine, `vm-centrale/`, `poste/`). Rien de manuel à faire au premier clone, ni après un `git pull` qui modifie un `pyproject.toml`/`uv.lock`. La logique commune aux deux scripts d'une même plateforme vit dans `scripts/` (`*.bat` pour Windows, `*.sh` pour macOS) afin d'éviter deux copies divergentes.

Pour un vrai chat (pas seulement le compte de test), colle ta clé API Mistral dans `MISTRAL_API_KEY` du fichier `vm-centrale/.env` — jamais dans Git.

Fermer les fenêtres arrête les processus correspondants (PostgreSQL et SearXNG continuent de tourner en arrière-plan tant que `docker compose down` n'a pas été lancé). La VM trouve SearXNG via `VM_CENTRALE_SEARXNG_URL` (`vm-centrale/.env`, `http://localhost:8888` par défaut) ; s'il ne répond pas, le chat fonctionne et l'IA indique que la recherche est indisponible. Les `.env` (racine, `vm-centrale/`, `poste/`) portent des identifiants/secrets locaux — ne jamais les commiter (déjà dans `.gitignore`).
