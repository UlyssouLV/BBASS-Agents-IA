# Recherche — HTTPS sur tous les échanges BBASS, y compris internes

Date de la recherche : 2026-10-29

## Périmètre

Inventaire des échanges en HTTP au moment de la 1.6.2, puis méthodes possibles pour passer chacun en HTTPS. Préparation de l’entrée **HTTPS partout** de la feuille de route (**Plus tard**). Rien n’est tranché ici : le choix se fait au grilling, et une décision figée deviendra un ADR (elle révisera la ligne « pas de HTTPS (LAN) » de l’[ADR-0021](../../adr/0021-cd-vm-centrale-staging-prod.md)).

Déclencheur : le quality gate Sonar de la 1.6.2 (PR #248) a levé `python:S5332` sur la construction de l’adresse du Serveur BBASS. L’alerte est acceptée pour l’instant par un `# NOSONAR` dans `poste/src/poste/config.py` (`adresse_http`). Ce `# NOSONAR` disparaît avec cette version.

## Inventaire

| # | Échange | Où dans le code | Passe par | Contenu |
| --- | --- | --- | --- | --- |
| 1 | Backend poste → Serveur BBASS | `poste/src/poste/config.py` (`adresse_http`), `routers/*.py` | **LAN du cabinet** | Identifiant et mot de passe (`/auth`), jeton de session, messages, pièces jointes, données Moduléo (`/moduleo/...`), mot de passe généré (`/comptes/.../reinitialiser`), inspecteur |
| 2 | Lanceur → Serveur BBASS (`/sante`, version à installer) | `lanceur/coeur/src/configuration.rs` (`adresse`) | LAN | Version attendue (le Paquet poste, lui, vient de GitHub en HTTPS et est signé ed25519) |
| 3 | Setup → Serveur BBASS (pastille de test) | `lanceur/src/installateur.rs` | LAN | `/sante` seulement |
| 4 | Fenêtre WebView2 / navigateur → backend poste | `lanceur/src/main.rs` (`http://127.0.0.1:8100/`) | Boucle locale du poste | Tout ce que voit le collaborateur |
| 5 | VM → SearXNG | `VM_CENTRALE_SEARXNG_URL` (`http://searxng:8080` en prod, `127.0.0.1:8888` en dev) | Réseau Docker interne | Requêtes de recherche web |
| 6 | VM → Postgres | `VM_CENTRALE_DATABASE_URL` (`postgresql+psycopg://…@postgres:5432`) | Réseau Docker interne | Toute la base (comptes, conversations, clés chiffrées) |
| 7 | Script `mettre-a-jour` → `/sante` | `vm-centrale/src/vm_centrale/mise_a_jour.py` (`http://localhost:<port>/sante`) | Boucle locale de la VM | État de santé |

Déjà en HTTPS, vérification active (pas de `verify=False` dans le code) : Mistral, Moduléo (Kipaware), GitHub Releases (mises à jour), pages web lues par les outils.

Seul le **#1** (et dans une moindre mesure **#2–#3**) expose des données sur un réseau partagé : n’importe quel appareil du LAN peut lire les mots de passe et les conversations, ou se faire passer pour le Serveur BBASS. Les #4 à #7 ne sortent pas de la machine ou du réseau Docker ; les chiffrer protège surtout contre un processus déjà présent sur la machine, et répond à une exigence « tout en HTTPS ».

## A. Poste ↔ Serveur BBASS (#1, #2, #3) — la priorité

### A1. Où terminer le TLS

**Option 1 — reverse proxy devant la VM (recommandé).** Un conteneur de plus dans `compose.yml` (Caddy, ou Traefik / nginx) publie le port LAN en HTTPS et relaie vers `vm-centrale:8000` sur le réseau Docker. Le port 8000 du conteneur VM n’est plus publié sur le LAN. Staging et prod gardent chacun leur port (8001 / 8000) côté proxy.

- Caddy : configuration courte, renouvellement des certificats intégré, autorité interne intégrée (`tls internal`), le flux SSE (1.4.4) passe sans réglage particulier.
- nginx : connu, mais renouvellement à scripter et réglages SSE à poser (`proxy_buffering off`).
- Traefik : utile surtout avec beaucoup de services découverts dynamiquement ; surdimensionné ici.

**Option 2 — TLS directement dans uvicorn** (`--ssl-certfile`, `--ssl-keyfile`). Pas de conteneur en plus, mais renouvellement du certificat et redémarrage du serveur à notre charge, et logique TLS mêlée au service applicatif.

### A2. D’où vient le certificat

**a. Autorité de certification interne, épinglée dans les clients BBASS (recommandé).**
Une autorité propre au cabinet (CA interne de Caddy, ou `step-ca` de Smallstep si on veut aussi signer pour Postgres et SearXNG, voir D) signe les certificats de la VM. Tous les clients du Serveur BBASS sont **à nous** (backend poste en Python / httpx, Lanceur et Setup en Rust) : la fenêtre WebView2 ne parle jamais directement à la VM, elle passe par le backend du poste. On peut donc faire confiance à la CA **dans nos clients seulement** (`httpx.Client(verify="<ca.pem>")`, `reqwest::Certificate` ajouté comme racine), sans toucher au magasin de certificats Windows ni demander de droits administrateur.

- Distribution de la CA au poste : le Setup la récupère au premier contact et affiche son empreinte, que l’admin compare à celle affichée par l’installateur de la VM (confiance au premier usage, vérifiée). Elle est rangée à côté de `configuration.json` dans `%LOCALAPPDATA%\BBASS`.
- Alternative : l’admin copie le fichier de la CA sur chaque poste (pénible, mais aucune confiance au premier usage).
- Durée : racine longue (10 ans), certificat serveur court renouvelé seul par le proxy. Changer la racine demande de repasser par chaque poste : à documenter dans le guide admin.

**b. Certificat public (Let’s Encrypt) sur un nom du domaine du cabinet.**
Un nom comme `bbass.castries.<domaine-du-cabinet>` résolu vers l’IP privée de la VM par le DNS interne, certificat obtenu par défi **DNS-01** (la VM n’a pas à être joignable depuis Internet). Avantage : reconnu partout sans rien installer, y compris dans un navigateur. Contraintes : accès API au DNS du domaine (jeton stocké sur la VM), un **nom** obligatoire au lieu d’une IP dans la Configuration du poste, renouvellement automatique indispensable (les durées de validité publiques raccourcissent d’année en année), dépendance à Internet pour renouveler.

**c. Certificat auto-signé épinglé par empreinte.** Le plus simple à poser, mais chaque renouvellement casse tous les postes jusqu’à ce que la nouvelle empreinte soit acceptée. Déconseillé au-delà d’un essai.

**d. Certificat émis par une PKI du cabinet (Active Directory Certificate Services)**, si le cabinet en a une : les postes du domaine lui font déjà confiance. À vérifier auprès du cabinet ; ne concerne que des postes joints au domaine.

### A3. Passage de HTTP à HTTPS sans casser les postes installés

La version du poste est dictée par la VM ([ADR-0022](../../adr/0022-poste-application-windows-version-dictee-par-la-vm.md)) et les postes 1.6.2 lisent `/sante` en HTTP. Ordre proposé :

1. La VM de la version HTTPS sert **les deux** : HTTPS sur le port habituel ou un nouveau port, HTTP gardé le temps de la transition.
2. Les postes lisent `/sante` en HTTP, installent la nouvelle version, qui passe en HTTPS (champ `schema` ou port HTTPS ajouté dans `configuration.json`, la CA récupérée et confirmée).
3. Une fois tous les postes passés, l’admin ferme l’HTTP (réglage de l’installateur de la VM).

L’intégrité des mises à jour ne dépend pas de ce chantier : le Paquet poste vient de GitHub en HTTPS et sa signature ed25519 est vérifiée.

### A4. Plus loin (hors de cette version)

- **TLS mutuel** : chaque poste présente un certificat client ; la VM refuse tout appareil inconnu du LAN. Demande une émission et une révocation par poste.
- **VPN / WireGuard** vers la VM : surtout utile à l’ouverture aux satellites ou à Internet ([ADR-0003](../../adr/0003-v1-scope-castries-seule.md)).

## B. Fenêtre / navigateur ↔ backend poste (#4, `127.0.0.1:8100`)

Le trafic ne sort pas du poste. Les navigateurs traitent `http://127.0.0.1` comme un contexte sécurisé. Le TLS ne protège pas contre un autre programme du poste qui se connecte au port 8100 : c’est l’authentification du backend qui le fait (session gardée dans le gestionnaire d’identifiants Windows, `poste/src/poste/session.py`).

**Option 1 — garder HTTP en boucle locale, décision écrite dans un ADR (recommandé si le cabinet n’exige pas « tout HTTPS »).** Coût nul.

**Option 2 — HTTPS en boucle locale avec un certificat par poste.** Le Setup génère une paire de clés et un certificat pour `127.0.0.1` / `localhost`.
- Fenêtre BBASS : WebView2 peut accepter ce certificat précis par son événement d’erreur de certificat serveur (accès au contrôleur WebView2 natif depuis Tauri), sans toucher au magasin Windows.
- « Ouvrir dans le navigateur » : Edge et Chrome lisent le magasin Windows ; ajouter un certificat racine au magasin de l’utilisateur fait apparaître une confirmation Windows ; le magasin machine demande des droits administrateur, que le Setup n’a pas. Firefox a son propre magasin. Sinon le navigateur affiche un avertissement.
- uvicorn sert alors en TLS (`ssl_certfile`, `ssl_keyfile`) ; le Lanceur et `test-fumee.ps1` passent à `https://127.0.0.1:8100`.

**Option 3 — plus de port TCP du tout** : la fenêtre parle au backend par le protocole personnalisé ou l’IPC de Tauri, ou par un tube nommé. Supprime la question, mais refonte du lien front / backend et perte de « Ouvrir dans le navigateur ».

## C. Setup → `/sante` (#3)

Même client et même confiance que A. L’étape « Serveur BBASS » du Setup gagne l’affichage de l’empreinte de la CA à confirmer (A2a). La pastille de test passe en vert seulement si la connexion TLS est vérifiée.

## D. Échanges internes de la VM (#5, #6, #7)

Tous dans le réseau Docker de la stack ou en boucle locale. Les chiffrer protège contre un conteneur compromis qui écoute le réseau Docker, et répond à « tout en HTTPS ».

**Postgres (#6).** Postgres sait servir en TLS (`ssl=on`, `ssl_cert_file`, `ssl_key_file`, clé lisible par l’utilisateur `postgres` seul) ; la VM se connecte avec `sslmode=verify-full` et `sslrootcert=<ca>` dans `VM_CENTRALE_DATABASE_URL`. Certificat signé par la CA interne (A2a). Postgres ne renouvelle pas seul : un certificat de durée moyenne renouvelé par une tâche planifiée (`taches-planifiees.conf`, convention 1.6.1), ou un client ACME de `step-ca`.

**SearXNG (#5).** Le conteneur SearXNG sert en HTTP. Deux voies : le même reverse proxy (A1) publie aussi SearXNG en HTTPS sur le réseau interne seulement, ou un petit proxy TLS dédié devant lui. La VM passe à `https://searxng…` avec `verify=<ca>`.

**Script `mettre-a-jour` (#7).** Appelle `/sante` à travers le proxy en HTTPS (`https://localhost:<port>/sante` avec la CA), ou reste en boucle locale vers le conteneur, documenté dans l’ADR.

**Option globale — maillage de services** (sidecars qui chiffrent tout automatiquement, type Istio / Linkerd) : prévu pour Kubernetes, surdimensionné pour une stack Docker Compose de quatre conteneurs. Déconseillé.

## Recommandation de départ (à confirmer au grilling)

1. Caddy en reverse proxy devant la VM, CA interne, CA épinglée dans le backend poste et le Lanceur, empreinte confirmée au Setup (A1-1 + A2a). Couvre #1, #2, #3.
2. Même CA pour Postgres (`verify-full`) et SearXNG derrière le proxy (D). Couvre #5, #6, #7.
3. Boucle locale du poste (#4) : décision explicite au grilling entre B1 (ADR) et B2 si le cabinet exige « tout HTTPS ».
4. Transition en deux temps (A3), puis fermeture de l’HTTP et retrait du `# NOSONAR` de `adresse_http`.

## Questions à poser au cabinet

- Exige-t-il le HTTPS jusque dans la boucle locale du poste et dans la VM, ou seulement sur le réseau ?
- Les postes sont-ils joints à un domaine Active Directory avec une PKI (A2d) ?
- A-t-il un nom de domaine et un accès API à son DNS (A2b) ?
- Un serveur DNS interne peut-il résoudre un nom pour la VM ?
