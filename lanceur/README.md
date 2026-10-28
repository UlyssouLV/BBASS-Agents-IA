# Lanceur BBASS

Application Windows du poste (ADR-0022) : `BBASS.exe` (Rust / Tauri v2) démarre le backend poste figé par PyInstaller (`poste-backend\`, mode dossier), attend sa réponse sur `127.0.0.1:8100`, puis l'affiche dans sa fenêtre WebView2. Quitter le Lanceur arrête le backend (Job Object Windows).

## Fenêtre et fond

- Fermer la fenêtre la cache : BBASS reste dans la zone de notification (« Ouvrir BBASS », « Ouvrir dans le navigateur », « Quitter ») et le chat reste ouvert sur `http://127.0.0.1:8100`. Seul « Quitter » arrête le Lanceur et le backend.
- Instance unique : relancer `BBASS.exe` rouvre la fenêtre existante.
- `BBASS.exe --demarrage-windows` (lancement avec Windows) démarre en fond, sans fenêtre.
- Journaux dans `%LOCALAPPDATA%\BBASS\journaux\` : `lanceur.log` et `poste-backend.log`, 3 fichiers de 1 Mo au plus chacun, sans secret ni jeton.

- `coeur/` : logique pure, testée par `cargo test` (test-root `lanceur`).
- `src/` : application Tauri (fenêtre, sidecar).
- `ecran/` : écran « Démarrage… » affiché avant le poste.
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

## Paquet poste signé

À chaque GitHub Release `vX.Y.Z`, le workflow `publier-paquet-poste.yml` joint à la Release `bbass-poste-vX.Y.Z-windows-x64.zip`, sa signature ed25519 (`.zip.sig`) et `SHA256SUMS`. Il signe avec le secret `POSTE_CLE_SIGNATURE` ; le Lanceur vérifie avec `cle-publique-poste.txt`, compilée dedans. Depuis `lanceur\` :

```powershell
cargo run -p bbass-lanceur-coeur --bin cle-poste -- generer <fichier-cle-secrete>   # nouvelle paire ; réécrit cle-publique-poste.txt
cargo run -p bbass-lanceur-coeur --bin cle-poste -- signer <paquet>                 # avec $env:POSTE_CLE_SIGNATURE
cargo run -p bbass-lanceur-coeur --bin cle-poste -- verifier <paquet> <signature>   # avec la clé publique compilée
```

Créer ou remplacer la clé : guide dans l'ADR-0022.

## Configuration

Le backend packagé lit l'adresse du Serveur BBASS dans `%LOCALAPPDATA%\BBASS\configuration.json` (sans fichier : `http://localhost:8000`) :

```json
{ "serveur_bbass": { "hote": "10.0.0.5", "port": 8000 } }
```

En dev (`lancer-logiciel.*`), le backend lit toujours `VM_CENTRALE_BASE_URL` dans le `.env`.
