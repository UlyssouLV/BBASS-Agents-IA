# Architecture Decision Records (ADR)

Un **ADR** fixe une décision technique : ce qu’on a choisi, pourquoi, et ce que ça implique ensuite.

Ce n’est ni une spec produit, ni un tutoriel. C’est le journal des choix structurants. Une ADR déjà écrite ne se réécrit pas : si la décision change, on en ajoute une nouvelle.

## Décisions

| N° | Décision |
| --- | --- |
| [0001](./0001-backend-local-par-poste.md) | Backend local par poste |
| [0002](./0002-relais-central-mistral.md) | Relais central pour la clé API Mistral |
| [0003](./0003-v1-scope-castries-seule.md) | V1 limitée à Castries |
| [0004](./0004-modele-mistral-decide-par-la-vm.md) | Modèle décidé par la VM |
| [0005](./0005-compte-administrateur-droit-global.md) | Droit admin global |
| [0006](./0006-compte-rattache-plusieurs-poles.md) | Compte multi-pôles |
| [0007](./0007-cle-admin-vm-reutilisee-poste.md) | Clé admin VM côté poste |
| [0008](./0008-postgresql-vm-centrale.md) | PostgreSQL sur la VM |
| [0009](./0009-pieces-jointes-jamais-mistral-files-api.md) | Pièces jointes hors Files API |
| [0010](./0010-front-poste-react-typescript-vite.md) | Front React / TypeScript / Vite |
| [0011](./0011-gestion-dependances-python-avec-uv.md) | Dépendances Python avec uv |
| [0012](./0012-mode-developpeur-cle-admin-vm-tous-comptes.md) | Mode développeur |
| [0013](./0013-recherche-web-searxng-auto-heberge.md) | SearXNG auto-hébergé |
| [0014](./0014-recherche-web-en-deux-temps-extraction-isolee.md) | Extraction web isolée |
| [0015](./0015-cache-commun-des-pages-web.md) | Cache commun des pages web |
| [0016](./0016-envoi-de-message-en-flux-sse.md) | Envoi de message en flux SSE |
| [0017](./0017-lecture-moduleo-par-outil.md) | Lecture de Moduléo par outil |
| [0018](./0018-droits-moduleo-appliques-par-bbass.md) | Droits Moduléo appliqués par BBASS |
