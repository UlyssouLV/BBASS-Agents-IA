# Poste livré en application Windows native, version dictée par la VM

Jusqu'à la V1.6.1, le Poste ne tournait que depuis un clone du dépôt (`lancer-logiciel.*` : git, Python, venv, Docker, onglet de navigateur), et rien ne reliait sa version à celle de la VM prod, qui change désormais par Promotion ([ADR-0021](./0021-cd-vm-centrale-staging-prod.md)). La V1.6.2 ([spec](../specs/v1.6.2-installateur-mise-a-jour-postes.md)) livre le Poste en application Windows :

- **Lanceur Rust / Tauri v2** (`lanceur/`) : fenêtre WebView2, zone de notification, instance unique, démarrage avec Windows, installateur, mise à jour. Le **backend du Poste reste en Python, inchangé**, figé par PyInstaller en mode dossier et démarré comme sidecar ; le front React ([ADR-0010](./0010-front-poste-react-typescript-vite.md)) est affiché dans la fenêtre et reste ouvrable dans le navigateur (`127.0.0.1:8100`).
- **Version dictée par le Serveur BBASS** : à chaque lancement, le Lanceur lit la version sur `GET /sante` et installe le Paquet poste de cette version, téléchargé depuis la GitHub Release (la VM ne donne que le numéro). Une Promotion met donc à jour la VM puis tous les postes ; un poste n'est jamais plus récent que sa VM.
- **Versions côte à côte** dans `%LOCALAPPDATA%\BBASS\versions\vX.Y.Z\`, une seule précédente gardée pour le retour arrière.
- **Signature ed25519** du Paquet poste : clé privée en secret GitHub, clé publique compilée dans le Lanceur. Une empreinte SHA-256 publiée à côté du fichier ne protégerait pas d'une Release altérée.
- **Installation par utilisateur, sans droits administrateur** (`%LOCALAPPDATA%\BBASS`, désinstallation inscrite dans `HKCU`). La Session reste dans le gestionnaire d'identifiants Windows, qui est par utilisateur.
- **Installateur maison** : le Setup est le Lanceur lui-même, avec un assistant React au style de l'application.

## Bascule du Lanceur (trace)

Chaque Paquet poste contient Lanceur et backend. Quand la version change :

1. télécharger le zip, vérifier la signature, décompresser dans `versions\vX.Y.Z\` ;
2. renommer l'exe du Lanceur en cours en `BBASS.old.exe` (Windows autorise le renommage d'un exe en cours d'exécution, pas son écrasement) et copier le nouveau `BBASS.exe` ;
3. redémarrer sur le nouveau Lanceur, qui démarre le nouveau backend et attend sa réponse locale ;
4. réponse saine : la version devient courante, la précédente est gardée, les plus anciennes et `BBASS.old.exe` sont supprimés au lancement suivant ;
5. pas de réponse : remettre `BBASS.old.exe` en `BBASS.exe` et la version précédente, redémarrer, journaliser l'échec et afficher le bandeau.

VM ou Internet injoignable, signature invalide : aucune bascule, démarrage sur la version installée avec un bandeau qui prévient que certaines fonctionnalités peuvent ne pas fonctionner.

## Alternatives écartées

- **Conteneur Docker sur chaque poste** : Docker Desktop, WSL2 et droits administrateur sur chaque poste ; le conteneur Linux n'atteint pas le gestionnaire d'identifiants Windows où vit la Session.
- **Python seul (pywebview + pystray)** : un seul langage, mais fenêtre, zone de notification, instance unique et démarrage automatique sont à assembler soi-même ; Tauri les fournit et prépare macOS.
- **Electron** : embarque son propre Chromium (≈ 150 Mo par application). WebView2 est déjà dans Windows et partagé ; sur macOS, Tauri utilise WKWebView.
- **.NET** : très bien intégré à Windows, faible pour une interface sur macOS, que l'on veut pouvoir viser plus tard.
- **Go, Java, C** : pas d'équivalent de Tauri (Go), runtime à embarquer et vue web faible (Java), effort et sécurité mémoire (C).
- **`tauri-plugin-updater` et bundler NSIS/MSI** : l'updater remplace l'installation sur place à partir d'un manifeste « dernière version » ; il faudrait recoder la version dictée par la VM et le retour arrière. L'assistant NSIS ne s'accorde pas au style de l'application.
- **Choix d'Environnement dans l'installateur** : le Poste est en prod ; essayer le staging, c'est changer le Serveur BBASS.
- **Certificat Authenticode** : coût annuel, clé sur support matériel ou service de signature cloud. Sans lui, SmartScreen avertit une fois à l'installation ; les mises à jour passent par notre signature. Reporté (Plus tard), déclencheur : déploiement au-delà du pilote.

## Consequences

- Deux langages côté poste (Rust pour le Lanceur, Python pour le backend) : test-root `lanceur` (`cargo test`), compartiments CI `tests-lanceur` et `build-poste-windows`. Ramener le backend dans le Lanceur est l'objet de l'entrée Plus tard « Optimisation du système ».
- Un poste ne se met à jour qu'au lancement (ou par « Vérifier les mises à jour maintenant ») et seulement après une Promotion : un correctif poste suit le même chemin que la VM (Release, staging, Promotion).
- Les antivirus peuvent signaler à tort le sidecar PyInstaller ; le mode dossier limite ce risque.
- Le check `build-poste-windows` s'ajoute aux checks requis du ruleset `main` (geste humain ci-dessous).

## Guide — ajouter `build-poste-windows` au ruleset `main`

Geste **humain** (admin du dépôt), même écran que le guide de l'[ADR-0020](./0020-ci-argos-compartimentee.md) : **Settings** → **Rules** → **Rulesets** → ruleset de `main` → **Require status checks to pass** → ajouter `build-poste-windows` (nom tel qu'affiché sur la PR de la 1.6.2) → sauver.

## Guide — créer la clé de signature du Paquet poste

Geste **humain**, une seule fois : générer la paire ed25519 depuis `lanceur/` (`cargo run -p bbass-lanceur-coeur --bin cle-poste -- generer <fichier-cle-secrete>`, qui réécrit `lanceur/cle-publique-poste.txt`), coller le contenu de ce fichier (la clé privée) dans **Settings** → **Secrets and variables** → **Actions** → **New repository secret** `POSTE_CLE_SIGNATURE`, et ranger une copie dans le gestionnaire de mots de passe du cabinet. Supprimer ensuite le fichier et committer `lanceur/cle-publique-poste.txt`. Perdre la clé privée oblige à réinstaller tous les postes avec un Setup portant la nouvelle clé publique.
