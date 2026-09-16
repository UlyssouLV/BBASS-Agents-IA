# BBASS-Agents-IA

Logiciel d'agents IA pour le cabinet de géomètres-experts BBASS. L'objectif est de mettre à disposition des collaborateurs une interface unique donnant accès à plusieurs agents métiers, capables de les assister sur des tâches courantes du cabinet. Le moteur de langage retenu est Mistral AI, choix du cabinet pour des raisons de souveraineté et de sécurité : ce projet ne consiste pas à entraîner une IA, mais à construire les agents et l'application qui les exploite.

## État actuel

Socle V1 en cours (branche `feat/v1-socle`) : backend local **poste** (interface HTML/CSS/JS) et API **VM centrale** (comptes PostgreSQL + relais Mistral). Les agents métiers ne sont pas encore construits.

## Ce qu'on construit

Une application composée d'un backend Python et d'une interface web (HTML/CSS/JS), avec des comptes par collaborateur. L'interface prend la forme d'une fenêtre de discussion (type chatbot) servant de point d'entrée vers les différents agents métiers. Le logiciel est destiné à être déployé et mis à jour de façon centralisée, pour être utilisé directement sur les postes des agences.

## Agents prévus

- Administration
- Appels d'offres
- Foncier
- DAO
- Urbanisme
- Détection de réseaux

## Priorité du moment

Le travail actuel porte sur l'interface (chat, comptes, accès aux agents) et sur le système de déploiement sur les postes des agences. La configuration fine de chaque agent métier viendra dans un second temps.

## Suite

Le développement des agents métiers eux-mêmes suivra, une fois l'interface et le déploiement en place.

## Lancer en local

Deux processus : la **VM centrale** (port 8000) puis le **poste** (port 8100). Le poste n'appelle jamais Mistral directement.

### Prérequis

- **Python 3.11** (série figée : pas 3.12 / 3.13 / 3.14). Dernier installeur Windows officiel : [Python 3.11.9](https://www.python.org/downloads/release/python-3119/) — prendre *Windows installer (64-bit)*. Cocher **Add python.exe to PATH**. Les correctifs 3.11.x plus récents n'ont plus d'installeur (source only).
- **Docker Desktop** pour le PostgreSQL local de la VM centrale ([ADR-0008](docs/adr/0008-postgresql-vm-centrale.md)) — pas nécessaire pour lancer les tests pytest (SQLite en mémoire).
- Une clé API Mistral (console [La Plateforme](https://console.mistral.ai)) pour un vrai chat ; les tests pytest n'en ont pas besoin
- Windows / PowerShell (chemins avec espaces : rester dans le dossier, ou tout quotter)

### PostgreSQL local (VM centrale)

Depuis la racine du clone :

```powershell
docker compose up -d
```

Démarre un PostgreSQL local sur `localhost:5432` (utilisateur/mot de passe/base `vm_centrale`), déjà pointé par `VM_CENTRALE_DATABASE_URL` dans `vm-centrale/.env.example`. Pour l'arrêter :

```powershell
docker compose down
```

(ajouter `-v` pour aussi supprimer les données persistées).

### Une fois par machine (dépendances)

Les paquets listés dans chaque `pyproject.toml` sont **épinglés en version exacte** (`==`), d’après l’environnement qui a fait tourner les tests. Pour les faire évoluer : changer le `pyproject.toml` à dessein, réinstaller, relancer pytest — pas un `pip install` « tout dernier ».

À la racine du clone, créer un venv **dans chaque** package et installer le projet + pytest :

```powershell
cd vm-centrale
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
copy .env.example .env
```

Dans `vm-centrale/.env` : coller `MISTRAL_API_KEY=...` (jamais Git). `VM_ADMIN_KEY` sert à la révocation admin des jetons ; pour un simple chat local tu peux la laisser vide tant que tu n'appelles pas ces routes.

```powershell
cd ..\poste
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
copy .env.example .env
```

`poste/.env` n'a **pas** de clé Mistral. Par défaut le poste joint `http://localhost:8000`.

### Compte de test

Au premier lancement, `create_all` crée les tables **vides**. Il n'y a pas d'écran d'inscription : insérer un compte à la main (identifiant, hash PBKDF2, prénom, nom, agence, pôle). Depuis `vm-centrale`, après `pip install` :

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -c @"
from vm_centrale.database import SessionLocal, init_db
from vm_centrale.models import Compte
from vm_centrale.security import hash_password
init_db()
db = SessionLocal()
db.add(Compte(
    identifiant='j.dupont',
    mot_de_passe_hash=hash_password('azerty'),
    prenom='Jean', nom='Dupont',
    agence='Castries', pole='Foncier',
))
db.commit()
"@
```

Si le schéma a changé (`create_all` n'ajoute pas de colonnes), repartir d'une base vide (`docker compose down -v` puis `docker compose up -d`) et ré-insérer le compte. Lancer la VM **depuis** `vm-centrale` pour que `.env` soit trouvé.

### Démarrer (deux terminaux)

Terminal 1 — VM :

```powershell
cd vm-centrale
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m vm_centrale.main
```

Terminal 2 — poste :

```powershell
cd poste
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m poste.main
```

Interface : [http://127.0.0.1:8100](http://127.0.0.1:8100) — connexion avec le compte seedé. Relancer la VM après toute modification de `.env`.

Tests : dans `vm-centrale` puis dans `poste`, `.\.venv\Scripts\python.exe -m pytest`.
