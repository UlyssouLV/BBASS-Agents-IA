# Lanceur BBASS

Application Windows du poste (ADR-0022) : `BBASS.exe` (Rust / Tauri v2) démarre le backend poste figé par PyInstaller (`poste-backend\`, mode dossier), attend sa réponse sur `127.0.0.1:8100`, puis l'affiche dans sa fenêtre WebView2. Quitter le Lanceur arrête le backend (Job Object Windows).

## Fenêtre et fond

- Fermer la fenêtre la cache : BBASS reste dans la zone de notification (« Ouvrir BBASS », « Ouvrir dans le navigateur », « Quitter ») et le chat reste ouvert sur `http://127.0.0.1:8100`. Seul « Quitter » arrête le Lanceur et le backend.
- Instance unique : relancer `BBASS.exe` rouvre la fenêtre existante.
- `BBASS.exe --demarrage-windows` (lancement avec Windows) démarre en fond, sans fenêtre.
- Journaux dans `%LOCALAPPDATA%\BBASS\journaux\` : `lanceur.log` et `poste-backend.log`, 3 fichiers de 1 Mo au plus chacun, sans secret ni jeton.

- `coeur/` : logique pure, testée par `cargo test` (test-root `lanceur`).
- `src/` : application Tauri (fenêtre, sidecar).
- `ecran/` : écran « Démarrage… » affiché avant le poste ; `ecran/installateur/` : assistant du Setup (build committé).
- `sidecar/poste-backend.py` : point d'entrée PyInstaller du backend.

## Construire et essayer le paquet

Prérequis : Node 20+, Python 3.11, Rust avec la chaîne MSVC (Visual Studio Build Tools). Depuis la racine du dépôt :

```powershell
powershell -ExecutionPolicy Bypass -File lanceur\scripts\construire-paquet.ps1
powershell -ExecutionPolicy Bypass -File lanceur\scripts\test-fumee.ps1
```

Le paquet est dans `lanceur\target\paquet\BBASS\` ; il tourne sans Python ni git. `-Version X.Y.Z` fixe la version annoncée par `BBASS.exe` (sinon celle de `Cargo.toml`).

## Mise à jour au lancement

À chaque lancement (fenêtre ou `--demarrage-windows`, jamais pendant que BBASS tourne en fond), le Lanceur lit la version sur `GET /sante` du Serveur BBASS. Si elle diffère de la sienne, il télécharge `bbass-poste-vX.Y.Z-windows-x64.zip` et sa signature depuis la GitHub Release, vérifie la signature, décompresse dans `versions\vX.Y.Z\`, renomme `BBASS.exe` en `BBASS.old.exe`, pose le nouveau `BBASS.exe` et redémarre dessus (`--attendre-fin <pid>`). Le nouveau Lanceur démarre son backend : réponse locale, la version est confirmée ; sinon il remet `BBASS.old.exe` et redémarre sur l'ancienne version. Séquence de l'ADR-0022 ; logique dans `coeur/src/mise_a_jour.rs`.

- Écran de démarrage : « Vérification… », « Mise à jour vers vX.Y.Z… » (barre de progression), « Démarrage… ».
- VM ou Internet injoignable, téléchargement ou signature en échec : démarrage sur la version installée, bandeau dans l'application, nouvel essai au lancement suivant. Une VM en version `dev` ne déclenche rien.
- `versions\installation.json` : version précédente gardée (une seule) et bascule en cours. Les autres versions, `BBASS.old.exe` et `BBASS.echec.exe` sont supprimés au lancement suivant.
- `%LOCALAPPDATA%\BBASS\mise-a-jour.json` : résultat de la dernière vérification (date, versions, résultat, détail, bandeau), servi par le backend sur `GET /mise-a-jour`.
- Le paquet construit en local (`target\paquet\BBASS\`) se met à jour lui aussi s'il trouve un Serveur BBASS d'une autre version publiée.
- « Vérifier les mises à jour maintenant » (menu « … », À propos, `GET /a-propos`) : le backend lance `BBASS.exe --verifier-mise-a-jour` (`BBASS_LANCEUR`, donné au sidecar avec `BBASS_VERSION`) ; l'instance unique le transmet au Lanceur en cours, qui redémarre avec cet argument : même parcours qu'au lancement, puis la fenêtre s'ouvre sur À propos avec le résultat (`/?a-propos`).

## Setup et désinstallation

`BBASS-Setup-vX.Y.Z.exe` est le Lanceur suivi du Paquet poste signé de sa version (`coeur/src/setup.rs`) : l'installation marche hors ligne. Lancé alors que `%LOCALAPPDATA%\BBASS\BBASS.exe` n'existe pas, il ouvre l'assistant (Bienvenue, Serveur BBASS avec test en direct sur `/sante`, Options, Installation) ; sinon il lance le BBASS installé.

- Par utilisateur, sans droits administrateur : décompresse dans `versions\vX.Y.Z\`, pose `BBASS.exe`, écrit `configuration.json` (adresse, `demarrage_windows` ; les autres réglages sont gardés), raccourci Menu Démarrer (et Bureau), `HKCU\…\Run\BBASS` (`--demarrage-windows`) et `HKCU\…\Uninstall\BBASS`. La signature est vérifiée avant de poser quoi que ce soit.
- Assistant : React, construit depuis `poste/frontend` (`npm run build:installateur`) dans `ecran/installateur/`, committé comme `poste/src/poste/static` (ADR-0010) ; `build-front` contrôle sa dérive. Commandes Tauri dans `src/installateur.rs`.
- Désinstallation (« Applications installées » → `BBASS.exe --desinstaller`) : confirmation, copie temporaire du Lanceur, arrêt du BBASS en cours (`--quitter`, transmis par l'instance unique), retrait des raccourcis, du démarrage avec Windows, de l'entrée de désinstallation, de la Session (gestionnaire d'identifiants) et de `BBASS.exe`, `versions\`, `mise-a-jour.json`. `configuration.json` et `journaux\` restent.
- Le workflow `publier-paquet-poste.yml` assemble le Setup après la signature (`setup-poste`, qui revérifie la signature) et le joint à la Release. À la main, depuis `lanceur\` :

```powershell
cargo run -p bbass-lanceur-coeur --bin setup-poste -- target\release\BBASS.exe <paquet.zip> <paquet.zip.sig> BBASS-Setup-vX.Y.Z.exe
```

## Paquet poste signé

À chaque GitHub Release `vX.Y.Z`, le workflow `publier-paquet-poste.yml` joint à la Release `bbass-poste-vX.Y.Z-windows-x64.zip`, sa signature ed25519 (`.zip.sig`), `BBASS-Setup-vX.Y.Z.exe` et `SHA256SUMS`. Il signe avec le secret `POSTE_CLE_SIGNATURE` ; le Lanceur vérifie avec `cle-publique-poste.txt`, compilée dedans. Depuis `lanceur\` :

```powershell
cargo run -p bbass-lanceur-coeur --bin cle-poste -- generer <fichier-cle-secrete>   # nouvelle paire ; réécrit cle-publique-poste.txt
cargo run -p bbass-lanceur-coeur --bin cle-poste -- signer <paquet>                 # avec $env:POSTE_CLE_SIGNATURE
cargo run -p bbass-lanceur-coeur --bin cle-poste -- verifier <paquet> <signature>   # avec la clé publique compilée
```

Créer ou remplacer la clé : guide dans l'ADR-0022.

## Configuration

Le Lanceur et le backend packagé lisent l'adresse du Serveur BBASS dans `%LOCALAPPDATA%\BBASS\configuration.json`, relue par le backend à chaque appel :

```json
{ "serveur_bbass": { "hote": "10.0.0.5", "port": 8000 } }
```

Sans fichier, l'adresse prod du dépôt s'applique (`ADRESSE_PROD`, `poste/src/poste/config.py` et `coeur/src/configuration.rs`) ; vide en 1.6.2, donc l'écran de connexion ouvre la Configuration. Le menu « … » (écran de connexion, page Profil) l'écrit via `PUT /configuration` sans réinstaller ; il ouvre aussi `%LOCALAPPDATA%\BBASS` (configuration et journaux).

En dev (`lancer-logiciel.*`), le backend lit toujours `VM_CENTRALE_BASE_URL` dans le `.env`.
