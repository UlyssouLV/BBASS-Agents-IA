# Lanceur BBASS

Application Windows du poste (ADR-0022) : `BBASS.exe` (Rust / Tauri v2) démarre le backend poste figé par PyInstaller (`poste-backend\`, mode dossier), attend sa réponse sur `127.0.0.1:8100`, puis l'affiche dans sa fenêtre WebView2. Fermer le Lanceur arrête le backend (Job Object Windows).

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

Le paquet est dans `lanceur\target\paquet\BBASS\` ; il tourne sans Python ni git.

## Configuration

Le backend packagé lit l'adresse du Serveur BBASS dans `%LOCALAPPDATA%\BBASS\configuration.json` (sans fichier : `http://localhost:8000`) :

```json
{ "serveur_bbass": { "hote": "10.0.0.5", "port": 8000 } }
```

En dev (`lancer-logiciel.*`), le backend lit toujours `VM_CENTRALE_BASE_URL` dans le `.env`.
