# Feuille de route de dev

Ordre des **prochaines versions** produit, plus les sujets encore sans numéro.

Ce n’est **pas** une spec (ça vient après « Ouvre la version »).

## Déjà livré

- **1.0.x** — Socle : comptes, connexion, chat, relais Mistral, session persistée (keyring), LAN Castries.
- **1.1.0** — Comptes administrateurs, multi-pôles, mot de passe généré / changement forcé, révocation, affichage pôle/agence dans le chat.
- **1.1.1** — Conversations persistées sur la VM (PostgreSQL) : plusieurs fils, reprise après rechargement / autre poste, historique borné (3 derniers messages + résumé glissant), profil de travail lecture seule ; pas de stockage Mistral Conversations.
- **1.1.2** — Pièces jointes : upload PDF/Word/Excel/image sur un message (une par message), extraction (OCR Mistral, locale pour Word/Excel, vision Mistral pour l'image), contenu injecté dans le chat, mention courte dans le résumé glissant, rappel via un outil si la pièce jointe sort de la fenêtre ; jamais la Files API Mistral.
- **1.1.3** — Consommation : une ligne `Consommation` par appel Mistral réel (chat, titrage, résumé+profil, OCR, vision), tokens ou pages selon le type, coût figé au tarif du jour de l'appel (pas d'API de tarification Mistral, tarifs en dur dans le code). Fenêtre Consommation côté collaborateur (total + classement des conversations par coût) ; onglet Consommations côté administrateur (comptes classés par coût, jamais de détail par conversation).
- **1.2.0** — Interface poste réécrite en React/TypeScript/Vite (shadcn/ui, Tailwind, TanStack Query), build committé dans git (jamais de Node.js requis sur un poste, [ADR-0010](../../adr/0010-front-poste-react-typescript-vite.md)) ; écran comptes (compte administrateur) passé de blocs empilés à une table avec une modale par action.
- **1.2.1** — Identité visuelle du poste calquée sur le logo BBASS Géomètre-Expert (couleurs, police Manrope auto-hébergée, logo, favicon) et disposition façon ChatGPT (sidebar avec conversations et puce compte, page Profil dédiée, Panel d'administration dédié avec tableaux/étiquettes shadcn-ui) ; aucun changement côté VM centrale ni du contrat API.
- **1.2.2** — Style de réponse de l'IA : prompt système de style (vm-centrale) sur l'appel de chat principal uniquement (vouvoiement, pas de remplissage réflexe, emojis rares et signifiants, pas de relance systématique en fin de réponse, Markdown borné autorisé — gras/italique/listes/paragraphes), jamais sur le titrage ni le résumé + profil de travail. Rendu Markdown borné côté poste (`react-markdown`, allowlist `strong`/`em`/`ul`/`ol`/`li`/`p`, tout le reste neutralisé au rendu), en remplacement du texte brut affiché jusqu'ici.
- **1.2.3** — Amélioration des délais de chargement (pages et conversations) : cache TanStack Query revu par requête (liste des conversations, détail de conversation, Profil, Panel d'administration), `placeholderData` sur le détail de conversation pour garder l'ancien contenu affiché pendant le rafraîchissement ; pagination par curseur de `GET /conversations/{id}` (vm-centrale), fenêtre de messages la plus récente par défaut, historique plus ancien chargé au défilement façon ChatGPT (pas de pagination par page) ; instrumentation de temps légère (`performance.mark`/`performance.measure`) sur l'ouverture/bascule de conversation, Profil et Panel d'administration, désactivée par défaut, posée pour être réutilisée par la 1.3.0.
- **1.3.0** — Inspecteur des échanges avec le modèle (outil de développement) : Mode développeur ouvert par `Ctrl+Maj+D` depuis n'importe quel compte, dans un nouvel onglet `/inspecteur`, débloqué par la Clé d'administration VM (saisie en mémoire de l'onglet, jamais stockée) ; accès à toutes les conversations de tous les comptes ([ADR-0012](../../adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)) — comptes → conversations → fil chronologique des échanges. Chaque appel Mistral réel (chat, titrage, résumé+profil, OCR, vision, chaque aller-retour de tool calling) est capturé dans une table `echanges_inspecteur` séparée de `Consommation` (payload exact envoyé, réponse brute, statut succès/échec), supprimée en cascade avec la conversation ; un échange en échec survit au rollback du tour ; pièce jointe affichée comme référence cliquable plutôt qu'en texte brut ; jamais la clé API Mistral dans un échange. Historique seulement, lecture seule.
- **1.3.1** — Le chat ne fige plus ses inventions ([#110](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/110), [spec](../../specs/v1.3.1-chat-ne-fige-plus-ses-inventions.md)) : consigne de chat sans lien proposé (seule une URL écrite par le compte peut ressortir), refus d’un fait inventé sans demande explicite ; pièce jointe traitée comme déjà jointe et décrite par son seul extrait ; résumé glissant qui note « proposé, non vérifié » ce que l’assistant a affirmé, plafonné à 1 500 caractères ; profil de travail réécrit en entier sous 800 caractères au lieu d’empiler des deltas, profils existants vidés. Garde-fous centralisés dans `vm_centrale/garde_fous/` : URL absente des messages du compte retirée ; sans document ni chiffre fourni, une réponse chiffrée est remplacée par une phrase fixe de la VM ; avec une source, seuls les chiffres présents restent. Pas de changement du contrat HTTP du poste.
- **1.4.0** — Recherche web dans le chat ([#117](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/117), [spec](../../specs/v1.4.0-recherche-web-dans-le-chat.md)) : outil `rechercher_web` exécuté par la VM sur un SearXNG auto-hébergé ([ADR-0013](../../adr/0013-recherche-web-searxng-auto-heberge.md)) ; pages entières nettoyées puis appel d’extraction isolé du contexte de la conversation ([ADR-0014](../../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)) ; outils du modèle centralisés dans `vm_centrale/outils/`, tous les appels d’outils traités sur 3 tours au plus ; seules les URL revenues de l’outil et les chiffres écrits dans les pages lues restent ; date du jour donnée au modèle pour les recherches d’actualité ; inspecteur chronologique Mistral / local avec ligne garde-fous. Pas de changement du contrat HTTP du poste. Bug connu à la livraison : quand la recherche ne trouve rien, l’IA invente encore au lieu de le dire ([#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131), correction reportée en **Plus tard**).
- **1.4.1** — Mémoire de la conversation ([#132](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/132), [spec](../../specs/v1.4.1-memoire-de-la-conversation.md)) : à chaque appel de chat, la VM envoie la liste recalculée de tout ce qui a été partagé (pièces jointes, recherches web, URL écrites par le compte, marquées comme telles), chacune avec ses **questions couvertes** (jusqu’à 8, produites par l’appel d’extraction devenu JSON pour une page, par un appel `questions_piece_jointe` à l’envoi pour une pièce jointe ; jamais une source des garde-fous) ; `relire_pieces_jointes` (plusieurs à la fois, dès le tour suivant) et `lire_pages_web` (page trouvée par une recherche relue sans retéléchargement, URL du compte téléchargée une fois puis source des garde-fous) avec un `besoin` facultatif dont la réponse, ou « non présent selon l’extraction », rejoint les questions couvertes ; boucle d’outils portée à 5 appels principaux par message ; garde-fous corrigés (URL en gras Markdown gardée, numéro groupé autrement que la source comparé chiffres bout à bout et retiré en entier). Pas de changement du contrat HTTP du poste.
- **1.4.2** — Le contexte en vrais tokens ([#144](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/144), [spec](../../specs/v1.4.2-contexte-en-vrais-tokens.md)) : fiche de modèle dans `config.py` (fenêtre, tokenizer, tarifs), modèle de chat figé à `mistral-small-2603` (fenêtre 262 144) au lieu de l’alias `mistral-small-latest` ; `tekken.json` de Mistral Small 4 versionné et chargé avec `mistral-common` (la VM refuse de démarrer sans lui) ; plafond des pages de `rechercher_web` et de `lire_pages_web` avec `besoin` à 80 % de la fenêtre, compté en vrais tokens ; page trop longue non relue : consigne de réponse honnête avec son titre s’il est connu, même refus tout le tour, mention fixe en fin de réponse (garde-fou `pages_trop_longues`, un sous-dossier par garde-fou) ; jauge de contexte sous le champ de saisie (`prompt_tokens` du dernier appel principal sur la fenêtre, orange à partir de 80 %). Seul changement du contrat HTTP du poste : `tokens_contexte` et `fenetre_contexte` sur les messages.
- **1.4.3** — Cache des pages web entre conversations ([#153](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/153), [spec](../../specs/v1.4.3-cache-des-pages-web.md), [ADR-0015](../../adr/0015-cache-commun-des-pages-web.md)) : une page lue avec succès est gardée 24 h, clé = URL exacte, partagée entre tous les comptes (texte et titre seulement) ; chaque conversation garde sa photo datée ; une page sans texte est retentée au tour suivant ; relecture forcée quand le collaborateur dit que la page a changé, questions déjà couvertes revérifiées ; en échec, l’ancienne version datée reste et l’IA le dit ; script de purge des lignes expirées, prêt pour une crontab (branchée au déploiement, 1.7.0). Pas de changement du contrat HTTP du poste.
- **1.4.4** — Statut d’attente dynamique pendant une réponse ([#163](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/163), [spec](../../specs/v1.4.4-statut-attente-dynamique.md), [ADR-0016](../../adr/0016-envoi-de-message-en-flux-sse.md)) : pendant un tour, le fil affiche l’étape en cours publiée par la VM (« Réflexion… », « Recherche sur le web : “…” », « Lecture de <domaine> », « Relecture de <fichier> », « Vérification de la réponse… », « Titre de la conversation… »), une à la fois, jamais persistée ; les deux envois de message répondent en flux SSE (`statut` / `fin` / `erreur`) de la VM au navigateur, relayé tel quel par le poste ; le tour s’exécute dans un thread et va au bout même si le flux est coupé ; rejeu idempotent = flux avec le seul `fin` en cache ; la bascule de conversation suit la sélection (envoi en cours et brouillon tenus par conversation, indicateur de chargement dans la sidebar, bug [#169](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/169) corrigé) ; envoi possible dans une autre conversation pendant un tour, mis en attente du verrou du compte avec le statut « En attente de la réponse en cours dans une autre conversation… ». Contrat HTTP du poste : `POST /conversations` et `POST /conversations/{id}/messages` en `text/event-stream`.
- **1.5.0** — Lire Moduléo depuis le chat ([#171](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/171), [spec](../../specs/v1.5.0-lire-moduleo-depuis-le-chat.md), [ADR-0017](../../adr/0017-lecture-moduleo-par-outil.md)) : deux outils communs à tous les comptes, `chercher_affaires_moduleo` et `chercher_contacts_moduleo`, proposés dès que la config Moduléo est présente (statut « Consultation Moduléo ») ; le modèle donne des noms, la VM les résout en ids et renvoie des fiches denses en noms (5 par défaut, 10 au plus), affaires récentes (90 jours) sans critère ; client HTTP en lecture seule limité aux routes GET du WADL du cabinet, doc Moduléo copiée en local avec un script de mise à jour ; une seule clé d’API et le SecurityCode d’un utilisateur de test, chiffrés (Fernet), jamais envoyés au modèle ni visibles dans l’inspecteur ; chaque fiche enregistrée dans `lectures_outils`, source des garde-fous sur toute la conversation (« Sources : Moduléo, affaire … »), questions couvertes générées par script dans la Mémoire de la conversation ; panne ou refus Moduléo dit en une phrase fixe, détail dans l’inspecteur ; corrections des tests humains (garde-fou chiffres et date du jour, phrase fixe Moduléo, titrage, note système après une réponse remplacée, garde-fou `contact_non_lu`). Pas de changement du contrat HTTP du poste.

## Prochaine : 1.6.0 — Documentation : mémoire conversationnelle et souveraineté des données

**Objectif.** Deux documents produit / fonctionnels (même format que la doc recherche web prévue ailleurs dans cette feuille), rédigés dans `docs/features/` **et** portés chacun par une issue GitHub labellee **`documentation`** (plan, schémas, captures, exemples). Pas de changement de code produit hors ajustements de doc / schémas / exemples de tests cités. Placée après Moduléo lecture (**1.5.0**) pour documenter aussi l’état mémoire / hébergement une fois ce socle métier posé, avant le déploiement postes.

1. **Persistance de la mémoire** (`docs/features/memoire-conversationnelle.md` ou équivalent). Schéma complet (tables / relations : conversations, messages, résumé glissant, profil de travail, pièces jointes, résultats de recherche web, etc.), flux tour par tour (ce qui entre, ce qui sort de la fenêtre de 3, ce qui est plafonné, ce que le modèle relit via outils), choix et décisions déjà prises et **pourquoi** (persistance VM vs API Conversations Mistral, séparation identité / profil, etc.). Exemples concrets (inspecteur, états en base) et références aux tests HTTP-boundary qui verrouillent ces comportements. Inclut la Mémoire de la conversation et les questions couvertes (1.4.1), le cache des pages web (1.4.3).

2. **Souveraineté des données** (`docs/features/souverainete-des-donnees.md` ou équivalent). Cartographie de tous les choix qui font que **seul le cabinet** détient les données persistées : Postgres et fichiers sur la VM Castries, SearXNG auto-hébergé, pas de Files API / Conversations Mistral, ZDR / `chat/completions` sans rétention côté modèle, clé API unique derrière la VM, LAN uniquement, etc. Expliquer **pourquoi** chaque décision rend le cabinet souverain (Mistral ne stocke pas nos fils ni nos fichiers ; aucun service externe n’héberge notre mémoire métier ; tout ce qui persiste est hébergé par nous). Relier ADR et specs déjà actées ; schémas « où vit la donnée » (poste / VM / Mistral / SearXNG) pour les chemins critiques.

**Hors périmètre.** Implémentation de nouvelles capacités mémoire ou cache (→ **1.4.1**, **1.4.3**). Déploiement postes (→ **1.7.0**), n8n (→ **1.8.0**). Doc tool calling recherche web (déjà prévue dans « Optimisation de la recherche web » / livrable doc associé).

## Ensuite : 1.7.0 — Déploiement postes (CI/CD, conteneurisation, installateur)

**Contexte.** Après la semaine en cours, l’alternant repart à l’école (~2 semaines). Les collaborateurs peuvent déjà vouloir **utiliser Moduléo en lecture** via le chat (livré en 1.5.0) sans attendre le retour. Il faut donc pouvoir **déployer / mettre à jour** le logiciel sur les postes du cabinet de façon reproductible — pas seulement via les scripts de dev actuels.

**Objectif.** Une chaîne de **déploiement** : CI/CD (ex. GitHub Actions), **conteneurisation Docker** là où ça aide (au minimum ce qui est déjà Dockerisé + ce qui doit l’être pour un rollout propre), et un **installateur / logiciel poste** qui démarre le **backend local obligatoire** (ADR-0001) et donne accès au chat. Priorité produit de fin de semaine : **livrer cette 1.7.0** pour que le cabinet puisse installer et utiliser ce qui est déjà là (dont Moduléo lecture si 1.5.0 est passée), même en absence de l’alternant.

**Périmètre envisagé.**
- CI : build front Vite (fin du commit systématique du seul `dist/` à la main — voir aussi les notes « Plus tard » historiques), tests, artefacts versionnés / release.
- Conteneurisation : Postgres déjà en compose ; trancher ce qui est conteneurisé (VM centrale en prod/pilote, poste, ou les deux) vs process natif Windows sur le poste.
- **Installateur Windows** (et éventuellement macOS plus tard) : installe / met à jour le poste, configure le lien vers la VM Castries, démarre le backend local.
- **Accès UI** — archi à trancher à l’ouverture : fenêtre **pywebview** (ou équivalent) qui embarque l’UI, **ou** navigateur sur `localhost` du poste ; dans les deux cas le **backend Python par poste reste obligatoire**. Fermer la fenêtre ne devrait pas forcément tuer le process (accès encore possible en navigateur) — piste déjà notée sous « Lanceur poste ».
- Doc d’installation collab / admin cabinet (quelques étapes, pas un clone git).
- **Clé maître Moduléo en production** (ADR-0017 ; remplace la piste « clé USB », peu adaptée à une VM qui tourne en continu et redémarre sans personne pour la brancher). Niveau 1 au premier déploiement : fichier dans un répertoire système hors du dépôt et hors du dossier de `.env` (`/etc/bbass/` sous Linux, `C:\ProgramData\BBASS\secrets\` sous Windows, ou secret Docker monté dans `/run/secrets/` si la VM centrale est conteneurisée), lisible par le seul compte de service ; **exclu des sauvegardes de la VM** et sauvegardé à part (coffre / gestionnaire de mots de passe du cabinet) ; clé d’API Moduléo **restreinte à l’IP de la VM**, la vraie barrière si elle fuit. Niveau 2 si la VM est sous Linux avec un TPM (virtuel) : clé maître scellée par `systemd-creds`, illisible depuis une copie du disque ou un instantané, démarrage toujours automatique. Pas de service de clés séparé (Vault, OpenBao, Infisical) à ce stade : un seul secret, un seul consommateur, et l’accès au coffre demanderait lui-même un secret stocké sur la VM.

**Recherche / décisions à trancher à l’ouverture.**
- Clé maître : OS de la VM centrale et TPM virtuel disponible (niveau 2 possible ou non) ; politique de sauvegarde de la VM (exclusion du fichier). Décision à consigner dans un ADR qui complète ADR-0017.
- pywebview vs navigateur seul vs les deux (lanceur + URL de secours).
- Quoi Dockeriser sur le poste vs sur la VM ; prérequis Docker Desktop côté collab ou non.
- Canal de mise à jour (GitHub Releases, partage interne Castries, etc.).
- Périmètre « pilote » : une machine / quelques postes Admin avant rollout large.

**Note semaine en cours.** On peut encore **viser** d’avancer n8n en parallèle si le temps le permet, mais le **livrable prioritaire** reste **1.7.0 déploiement** (n8n est **1.8.0** ; la doc mémoire / souveraineté est **1.6.0**).

## Ensuite : 1.8.0 — Workflows n8n (socle d’automatisation), branchés sur Moduléo 1.5.0

*(Anciennement 1.6.0, puis 1.7.0 — passe en 1.8.0 pour laisser 1.6.0 à la documentation mémoire / souveraineté.)*

S’appuie sur les **outils / client Moduléo lecture** livrés en 1.5.0. n8n devient le **runtime d’automatisation** (scénarios multi-étapes, plus tard d’autres logiciels), pas un miroir 1:1 de chaque route API.

**Objectif.** Intégrer **n8n** (self-host envisagé sur le LAN) de façon **sûre** : l’Agent / la VM peut s’appuyer sur des workflows (déclencher, et selon garde-fous créer/modifier **inactifs**, idéalement depuis templates) en réutilisant ce qu’on sait déjà faire côté Moduléo. Les collaborateurs pourront à terme orchestrer des automates au-delà du simple Q&A chat — sans god-mode CRUD n8n ni activation libre en prod dès le premier jet.

**Périmètre envisagé.**
- Instance n8n de test ; client API / webhooks côté VM ; dossier d’intégration (ex. `integrations/n8n/`).
- Outils Agent bornés : list/get, exécuter un workflow existant, créer/update **inactif** (templates de préférence) ; activer / delete / credentials sous contrôle strict (admin ou validation).
- Premiers workflows utiles qui **composent** des appels Moduléo (réutiliser la logique 1.5.0), pas « un workflow par endpoint ».
- Mistral peut **aider** à concevoir / paramétrer un automate ; l’exécution du workflow elle-même ne consomme pas de tokens (seuls les tours de chat + résultats réinjectés en consomment).

**Recherche / décisions à trancher à l’ouverture.**
- Self-host Docker vs autre ; où tourne n8n par rapport à la VM.
- Contrat outils chat ↔ n8n (webhook vs API execute).
- Gouvernance : qui active un workflow ; audit des exécutions.
- Comment réexposer ou appeler la stack Moduléo 1.5.0 depuis n8n (HTTP Request vers Moduléo vs rappel d’un service VM).

## Ensuite : 1.9.0 — Analyse et traitement des pièces jointes, approfondis

*(Anciennement 1.5.0, puis 1.6.0, puis 1.7.0, puis 1.8.0 — passe en 1.9.0 pour laisser 1.6.0 à la documentation mémoire / souveraineté.)*

S’appuie sur la [1.1.2](../../specs/v1.1.2-pieces-jointes.md) (pipeline d’extraction, une pièce jointe par message). Le traitement par pôle suppose les **Agents métier par pôle** (Plus tard) : à livrer avant, ou à faire entrer ici. Deux limites actées volontairement en 1.1.2 sont à lever ici, pas avant : **plusieurs pièces jointes par message**, et un **traitement spécifique par pôle** (un agent Foncier ne traite pas un document comme un agent Urbanisme) — demande explicite du cabinet dès le grilling de 1.1.2, remise à plus tard faute d’Agent réel pour la justifier.

**Objectif.** Une pièce jointe mieux exploitée selon qui la reçoit (le pôle de l’Agent destinataire). Le rappel d’une pièce jointe dans la durée de la conversation est livré par la 1.4.1 (Mémoire de la conversation, questions couvertes, `relire_pieces_jointes`).

**Recherche.**

- Plusieurs pièces jointes par message : impact sur le schéma `PieceJointe` (déjà pensé pour ne pas bloquer ça), sur l’outil `relire_pieces_jointes` (1.4.1, déjà capable d’en relire plusieurs d’un coup), sur le résumé glissant (une mention courte par pièce jointe, pas une agrégée).
- Traitement par pôle : qu’est-ce qui change concrètement pour un même format (PDF, image, …) selon le pôle de l’Agent qui le reçoit — nouveau prompt d’extraction, post-traitement dédié, ou simple différence de consigne à l’IA plutôt qu’un pipeline dupliqué.
- Fiabilité de l’analyse elle-même, au-delà de la plomberie : enseignements des essais fonctionnels 1.1.2 (ex. liens inventés entre pièces jointes sans preuve, confusions de vocabulaire métier propre à un document) qui ne relèvent ni de la fenêtre de 3 messages ni du profil de travail.
- Conservation d’une pièce jointe au-delà de sa conversation d’origine (usage multi-conversationnel, matière pour entraîner les futurs Agents) : piste évoquée dès le grilling 1.1.2, pas tranchée.

## Plus tard (pas encore numéroté)

### Agents métier par pôle (consigne et capacités par pôle)

Sorti de la 1.5.0 pour la garder petite. Un **Agent** sert un pôle : sa consigne, et la liste des capacités qu’il a le droit d’utiliser. Les **outils restent communs** (`vm_centrale/outils/`, dont Moduléo depuis la 1.5.0) : ce n’est pas un « Agent Moduléo ». L’Agent Administration aura simplement des capacités Moduléo autorisées que les autres Agents n’ont pas. Le code d’un Agent (consigne, liste des outils autorisés, éventuels traitements propres au pôle) vit dans un dossier par Agent ; un petit registre choisit les outils du tour selon l’Agent, sans `if` par pôle dans `routers/conversations.py`. Le pack `agents/` à la racine du dépôt reste un outil de développement (skills, hooks), distinct des Agents métier.

Déjà tranché : un Agent est une configuration dans le flux chat de la VM centrale, **pas un conteneur Docker par Agent / par pôle** (pas de runtime propre, ops inutiles alors que peu de tech sera sur place). Si l’indépendance de déploiement devient un besoin : config rechargeable d’abord, et ne conteneuriser que ce qui a un vrai cycle de vie (adaptateur Moduléo en écriture, bac à sable d’exécution, n8n).

À trancher à l’ouverture : comment un tour choisit son Agent (pôle du compte, choix explicite, plusieurs pôles), quelles capacités pour chaque pôle, lien avec le traitement des pièces jointes par pôle (1.9.0).

### Clés API Moduléo par utilisateur (droits côté Moduléo)

Sorti de la 1.5.0. Sur le serveur Moduléo, tous les utilisateurs n’ont pas accès aux mêmes choses. Une seule clé de test (1.5.0) ne reflète pas ces droits. À trancher : une clé / un SecurityCode par collaborateur ou par profil, où BBASS les stocke, qui les affecte (panel d’administration ; la création reste côté Moduléo), comportement quand un compte n’a pas de clé. S’appuie sur ce que la 1.5.0 aura appris de l’interface de paramétrage Moduléo. Avec plusieurs secrets et plusieurs services (n8n 1.8.0, `MISTRAL_API_KEY` à chiffrer), réexaminer un coffre de secrets centralisé (rotation, révocation, journal des lectures) à la place du fichier clé maître de la 1.7.0.

### Dire « pas trouvé » plutôt qu’inventer après une recherche (ex-1.4.5, #131)

Corriger le bug [#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131), constaté au test humain de la 1.4.0 : quand la recherche (ou la pièce jointe) ne contient pas l’information, la réponse dit qu’elle ne l’a pas trouvée, au lieu d’estimer des tarifs, des dates ou de citer une source qui n’existe pas. Jamais « sourcé » ni « confirmé par » sans résultat de l’outil qui le contient ; une source dont le lien est retiré ne reste pas affichée comme source ; le contenu de la pièce jointe prime sur une généralité du web. Les garde-fous ne cassent plus la mise en forme (indentation des listes et tableaux, parenthèses vides) ; une page quasi vide n’est pas comptée comme lue ; la date du jour est donnée en toutes lettres et seule l’année va dans la requête. À trancher au grilling : sort d’une réponse dont beaucoup de chiffres sont retirés (marqueur visible, réécriture, phrase fixe), contrôle des petits montants (« 5 € »), et traitement ici ou à part du profil de travail et du résumé qui débordent d’une conversation à l’autre.

**Hors périmètre.** Pages refusées par les sites (HTTP 403) et PDF trouvés sur le web ; vérification de la fiabilité des sources ; modes Rapide / Approfondi. Pas de changement du contrat HTTP du poste.

### Bug — lien de source peu visible (#99)

**Constat :** malgré les travaux front sur le rendu des sources (suite #98), l’affichage **ne valide toujours pas** les critères — le texte de l’ancre n’est pas clairement cliquable (URL au survol natif), et l’affordance (couleur / soulignement) ne rend pas le lien repérable sans pastille seule, ni sans laisser croire que toute la phrase est cliquable.

**Reproductibilité :** essai manuel — ouvrir une réponse qui cite une source et vérifier ancre, `href` au survol, et affordance dans le fil.

**Impact :** citations de sources peu repérables / peu utilisables ; critères d’acceptation de #98 non tenus.

**Cause probable :** Informations manquantes

**À corriger :** rendre le texte de l’ancre cliquable (URL au survol natif) ; affordance claire sans pastille seule et sans faire croire que toute la phrase hors citation est cliquable (front `LienSource` / Markdown chat).

**Hors périmètre :** vm-centrale / prompt de style (hors sujet, déjà #96).

**Suivi :** [#99](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/99) (`bug`). Trouvé dans : Informations manquantes · Contexte : essai manuel · Date : 2026-10-05 · Priorité : Informations manquantes.

### Bug — données d’un compte visibles par un autre compte (#161)

**Constat :** après une déconnexion puis une connexion à un autre compte, la barre latérale affiche d’abord les conversations du compte précédent, jusqu’au rafraîchissement ; un compte recréé avec le même identifiant retrouve les conversations de l’ancien compte supprimé.

**Reproductibilité :** (1) compte A → déconnexion → compte B sur le même poste : sidebar montre d’abord les conversations de A jusqu’au rafraîchissement ; (2) supprimer un compte puis le recréer avec le même identifiant → anciennes conversations / données liées réapparaissent.

**Impact :** un collaborateur peut voir, même brièvement, les conversations d’un autre compte ; un compte recréé hérite des données de l’ancien (isolation des comptes).

**Cause probable :** poste — déconnexion ne vide pas le cache React Query ; VM centrale — suppression de compte n’efface pas les tables liées par identifiant.

**À corriger :** la déconnexion vide toute la mémoire du compte côté poste ; la suppression d’un compte supprime aussi ses conversations, pièces jointes, profil de travail et échanges d’inspecteur, avec nettoyage des données déjà orphelines.

**Hors périmètre :** décision de garder ou non la consommation d’un compte supprimé pour le suivi des coûts — à trancher.

**Suivi :** [#161](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/161) (`bug`). Trouvé dans : 1.4.3 · Contexte : test humain · Date : 2026-10-07 · Priorité : non prioritaire en dev.

### Bug — Markdown brut pendant l'animation de frappe (#170)

**Constat :** pendant l'animation de frappe d'une réponse, le Markdown s'affiche brut : les balises (`**`, `#`, `-`, `|` des tableaux…) sont visibles et le texte ne se met en forme qu'à la fin de l'animation, d'un coup.

**Reproductibilité :** poser une question dont la réponse contient du gras, des titres, des listes ou un tableau (ex. « Compare ces aides dans un tableau ») et regarder la réponse s'écrire : balises visibles pendant toute la frappe, mise en forme à la dernière étape.

**Impact :** rendu peu lisible pendant la frappe, puis « saut » visuel à la fin ; tous les comptes, sur chaque réponse mise en forme.

**Cause probable :** choix volontaire de `TexteAnimeReponse` (`poste/frontend/src/onglets/OngletChat.tsx`, suite #99) : tant que le texte révélé est tronqué, il est affiché en texte brut ; le rendu Markdown (remark-gfm, Prism) n'est fait qu'une fois, à la fin, pour éviter une syntaxe incomplète cassée à chaque étape.

**À corriger :** la réponse se met en forme au fur et à mesure de la frappe, sans balises Markdown visibles ni syntaxe incomplète cassée (lien, tableau, bloc de code non refermé).

**Hors périmètre :** pas dans la V1.4.4. Streaming du texte de la réponse depuis la VM (les garde-fous s'appliquent au texte complet).

**Suivi :** [#170](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/170) (`bug`). Trouvé dans : 1.4.4 · Contexte : test humain · Date : 2026-10-07 · Priorité : non prioritaire en dev.

### Agent IA de continuation du développement, validation par compte administrateur

Constat (grilling 1.2.0) : à terme, plus aucune personne qualifiée ne sera sur place pour faire évoluer le logiciel elle-même. L'évolution du code (nouvelles versions, corrections, nouveaux Agents métier) serait alors portée par un agent IA dédié à la continuation du développement, avec un compte administrateur qui ne fait que **valider** (approuver/refuser) les changements proposés, sans avoir à coder ni à relire le code en détail.

Implications déjà identifiées à creuser plus tard :
- Cette contrainte pèse sur les choix techniques pris dès 1.2.0 (ex. TypeScript plutôt que JS nu, pour donner un filet de sécurité à la compilation en l'absence de relecture humaine technique).
- Reste à définir : à quoi ressemble concrètement le flux de validation (où/comment un compte administrateur voit et approuve un changement), le périmètre de ce que l'agent peut faire seul vs ce qui nécessite une validation, et les garde-fous (rollback, tests obligatoires avant validation, etc.).
- Tests front (grilling 1.2.0) : pas de tests dédiés côté UI React en 1.2.0 (on reste sur les tests pytest HTTP-boundary existants + validation visuelle par l'admin). À une version pas encore numérotée : ajouter un filet de sécurité automatisé côté UI (ex. Playwright) puisque seul un agent IA maintient ce code sans relecture humaine technique — pertinent surtout quand le volume d'écrans aura grossi (1.3.0, 1.4.0, 1.5.0, 1.6.0, 1.7.0, 1.8.0, 1.9.0 et au-delà).

### Lanceur poste (exécutable, pywebview)

→ **Repris et numéroté en 1.7.0** (déploiement postes : installateur + accès UI, pywebview vs navigateur à trancher). Cette entrée « Plus tard » ne fait plus office de file d’attente séparée.

### Déploiement, CI/CD, retours utilisateurs

→ **Repris et numéroté en 1.7.0**. Contraintes déjà vues à réintégrer dans la spec à l’ouverture : pas forcément de VM centrale physique pour un CD du relais ; LAN Castries vs Internet ; Actions pour pytest + build front ; pilote sur quelques machines. Depuis 1.2.0 le `dist/` front est committé — la CI 1.7.0 doit prendre en charge le build Vite.

### Mémoire / RAG / plateforme LLM tierce (Open WebUI, Mem0…) — en réserve, pas prioritaire

**Décision pour maintenant.** À notre échelle, on se concentre sur le reste de la feuille de route (Agents, PJ approfondies, etc.). On **garde ces options en tête** : si un jour le besoin (multi-modèles, mémoire à snippets, corpus documentaire) ou la dette de maintenance du chat custom le justifie, on réévalue. Pas de travail ni de version dédiée tant que ce n’est pas le cas.

**Ce qu’Open WebUI fait concrètement (self-host local possible).**
- **Memory** : snippets faits / préférences par utilisateur (`user` / `context`, chemins optionnels), en base locale + embeddings ; rappel par injection dans le prompt et/ou outils agentiques (`add_memory`, `search_memories`, …). Par défaut : SQLite + Chroma embarqués — **tout peut rester local**, les DB externes (Postgres, Qdrant…) sont optionnelles surtout pour scaler.
- **RAG / Knowledge** : documents chunkés, retrieval vectoriel (hybrid search possible), attachables à un chat / un modèle ; mode legacy (injection auto) ou agentique (le modèle appelle des outils).
- **Relais multi-modèles** + API utilisable depuis un front externe (`/api/chat/completions` compatible OpenAI, clés API).

Ce n’est **pas** le même objet que la 1.1.1 (résumé glissant de conversation + profil de travail).

**Pourquoi on ne l’adopte pas tout de suite comme backend « mémoire + relais ».** Open WebUI n’est pas une librairie isolée : c’est un **produit** (users, permissions, conversations, fichiers, admin). Derrière un front BBASS, le coût réel est la **double stack** : mapper `Compte` ↔ users OWUI, trancher ce qui reste dans `vm-centrale` (conso métier, admin VM, pôles, session poste…) vs ce qui vit chez OWUI, et subir les évolutions d’une API conçue pour leur UI. Les contraintes BBASS actuelles sont des **choix de grilling**, pas des lois — on pourrait pivoter (BBASS = shell métier, OWUI = plateforme LLM) si un jour ça vaut le coup ; ce n’est juste pas le focus maintenant.

**Autres pistes si on réouvre le sujet (sans avaler un second produit).**
- **Mem0** (OSS self-host) : couche mémoire à brancher à côté de l’agent existant — plus proche d’« adapter leurs méthodes » que d’adopter une plateforme chat.
- RAG cabinet : **pgvector** sur le Postgres VM déjà prévu, plutôt qu’un framework chat monolithique.
- S’inspirer des méthodes (snippets + embeddings, knowledge bases) et les réimplémenter dans poste / VM si le périmètre reste petit.

À creuser seulement si le besoin métier le justifie (doc Moduléo / Agents, corpus par pôle, multi-providers, etc.) :
- Mémoire inter-conversationnelle plus fine que le seul profil de travail synthétique.
- RAG sur un corpus cabinet, distinct des pièces jointes du fil courant (1.1.2 / 1.9.0).
- **Optimisation du résumé+profil actuel (1.1.1)** — **dans la même version** que le reste de ce chantier mémoire, pas une version à part. Distinct de la **1.3.1**, qui corrige le contenu figé (inventions reprises comme des faits, [#110](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/110)), pas la fréquence des appels ni un RAG. Aujourd’hui, dès qu’il y a des messages sortants, chaque tour fait **1 chat + 1 appel résumé/profil** (agrégés tous les deux en « Chat » côté conso) : fiable, mais ~2× les requêtes après le premier message. Pistes à trancher alors : résumé moins fréquent (tous les N tours / seuil de tokens), résumé en arrière-plan après la réponse affichée (façon *Dreaming*), ou mémoire à la demande (outil / notes) — en gardant éventuellement le combo résumé léger + embeddings pour le long terme.

### Éléments de réponse visuels plus riches dans le chat (graphiques, documents générés)

Constat (grilling 1.2.2) : au-delà du Markdown borné (gras, listes) posé en 1.2.2, le cabinet a exprimé l'envie qu'une réponse de l'IA puisse à terme intégrer des éléments plus riches — graphiques, voire génération de documents (façon Word/Excel, à la manière de ce que proposent certains assistants IA) — plutôt que de la prose seule.

Pas de travail dédié avant que le besoin se confirme. Le rendu posé en 1.2.2 (`react-markdown` + mapping de composants React par élément Markdown) est délibérément choisi pour rendre cette extension simple le moment venu : ajouter un nouveau type de bloc revient à enregistrer un composant supplémentaire dans ce mapping, sans reprendre l'architecture du rendu.

### Optimisation de la recherche web par défaut (tokens, contexte, outils)

Constat (essais manuels 1.4.0) : les extraits du moteur suffisent parfois à répondre, alors que télécharger et extraire les pages à chaque recherche coûte des tokens et du délai. Ce n’est **pas** un choix de mode Rapide / Approfondi côté collaborateur : c’est améliorer le **comportement par défaut** de `rechercher_web` après la 1.4.0, pour diminuer au maximum les tokens par conversation tout en gardant un contexte propre et des réponses efficaces (messages `tool` denses, infos pertinentes seulement).

Pistes à trancher à l’ouverture : ne lire / extraire les pages que si les snippets ne suffisent pas ; s’appuyer sur `lire_pages_web` (1.4.1) pour ne lire que les pages utiles plutôt que les 3 premières ; plafonds et format des résultats renvoyés au modèle ; affiner la consigne d’extraction ; éventuel lien avec le cache 1.4.3. S’appuie sur le registre d’outils et [ADR-0014](../../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md). Hors périmètre tant que la 1.4.0 n’a pas été retestée. Distinct des modes Rapide / Approfondi ci-dessous (ceux-là changent le contrat HTTP du poste).

**Documentation livrable (même version).** Un document dans le dépôt qui décrit **très exactement et fonctionnellement** le fonctionnement du tool calling de recherche web (paramètres, déroulé VM, pannes, ce qui part vers le moteur / l’extraction / le modèle principal, ce qui est persisté, rôle des garde-fous) — langage produit / fonctionnel, pas un dump de code. Des **schémas** illustrent tous les cas et cheminements possibles (succès snippets seuls, lecture de pages, extraction, moteur indisponible, page en échec, plafond, etc.). À l’ouverture : créer une issue GitHub labellee **`documentation`** (label déjà présent dans le dépôt) qui porte le plan de ce document, les captures / images d’exemples (inspecteur, messages `tool`, réponses) et toute info complémentaire ; le doc versionné dans `docs/` reste la référence une fois rédigé.

### Pages web refusées (HTTP 403) et pages JavaScript

Constat (test humain 1.4.0, conversations 89 à 92) : sur 24 pages téléchargées, 9 refusées en HTTP 403 (dont Légifrance et leboncoin), 1 PDF non lu, 5 pages JavaScript sans contenu exploitable. Légifrance est la source officielle d’un cabinet : la réponse se rabat sur un site tiers. Pistes à trancher à l’ouverture : en-têtes de navigateur plus complets, API officielle (Légifrance / PISTE) pour les textes de loi, rendu JavaScript. Les PDF ont leur propre entrée ci-dessous. Distinct de #131 (ce que le modèle écrit quand il n’a rien trouvé, entrée « Plus tard » ci-dessus).

### Lecture des PDF trouvés sur le web ou envoyés par URL

Constat (test humain 1.4.0, ouverture 1.4.1) : une page PDF, trouvée par `rechercher_web` ou écrite par le compte et lue par `lire_pages_web`, est ignorée (« page non lue ») ; seul l’extrait du moteur reste. Or un PDF officiel porte souvent l’information utile. Version à part, pas une 1.4.x : télécharger le PDF, le passer par l’OCR Mistral comme une pièce jointe ([ADR-0009](../../adr/0009-pieces-jointes-jamais-mistral-files-api.md) : jamais la Files API), plafond de pages, prise en compte dans le plafond de texte des pages, questions couvertes par la même extraction (1.4.1). À trancher à l’ouverture : plafond de pages, coût OCR (au tarif de la Consommation), délai de téléchargement, PDF scannés vs texte.

### Le tool calling ne boucle pas

Constat (ouverture 1.4.1) : la boucle d’outils est bornée par une limite fixe (3 appels principaux en 1.4.0, 5 depuis la 1.4.1), qui protège d’une boucle sans en prouver l’absence. Le but n’est pas un plafond arbitraire : plus le modèle trouve seul les bonnes données, mieux c’est. Cette version prouve que le tool calling ne tourne pas en rond (détection d’un même appel ou d’arguments répétés, trace dans l’inspecteur, tests), puis revoit la limite à chaque nouvel outil plutôt que de la figer.

### Questions couvertes à la demande pour Moduléo (`besoin`)

Constat (1.5.0, [#177](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/177)) : une lecture Moduléo n’a que les questions couvertes écrites par script, champ par champ, sans appel IA. Une question imprévue (« l’affaire est-elle en retard ? ») oblige le modèle à rappeler Moduléo, et sa réponse n’est gardée nulle part. Piste : un `besoin` sur les outils Moduléo, sur le modèle de `lire_pages_web` (1.4.1) : un appel d’extraction isolé sur la fiche relue, avec une réponse (ou « non présent selon l’extraction ») enregistrée en question couverte d’origine `besoin`. **Déclencheur** : l’essai réel ([#178](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/178)) ou l’usage montre beaucoup de rappels de Moduléo pour une même question. Sinon, ne rien changer : relire Moduléo garde une donnée fraîche, et une fiche est courte.

### Vérification de la fiabilité des sources web

Constat (essais manuels 1.4.0) : `rechercher_web` ramène des pages et l’IA les cite ; rien ne dit encore si une source est digne de confiance (site officiel, presse, blog, forum, page commerciale). Une amélioration ultérieure de la recherche web ferait **évaluer la fiabilité des sites sourcés** avant ou avec la réponse : indiquer au collaborateur le degré de confiance, écarter ou rétrograder les sources douteuses, et garder une trace lisible (inspecteur ou mention courte).

Pistes à trancher à l’ouverture : critères (domaine `.gouv.fr` / institutionnel, liste blanche cabinet, score heuristique, second passage modèle…), moment du contrôle (à la réception des résultats, après lecture des pages, à la rédaction), ce que voit le collaborateur, et le lien avec les garde-fous URL déjà en place. S’appuie sur la 1.4.0 et le registre d’outils. Distinct de l’optimisation **par défaut** (tokens / snippets) et des modes Rapide / Approfondi.

### Modes de réponse (Rapide / Approfondi) et outils de lecture plus fins

Constat (ouverture 1.4.0) : plusieurs façons d’utiliser les outils sont possibles selon l’effort voulu. Un mode choisi par le collaborateur réglerait le nombre de tours d’outils (voir « Le tool calling ne boucle pas »), le nombre de pages lues, le choix des pages par le modèle (s’appuie sur `lire_pages_web`, 1.4.1), un appel de synthèse, ou le modèle utilisé. Change le contrat HTTP du poste (choix du mode). Le découpage de la 1.4.0 (registre d’outils, appel d’extraction isolé, [ADR-0014](../../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)) est fait pour s’y brancher. Distinct de l’optimisation **par défaut** de la recherche web et de la **vérification de fiabilité des sources** (rubriques précédentes), qui ne demandent pas de choix utilisateur.

### Exécution de code dans le chat (cellules Python exécutables, façon ChatGPT)

Constat (validation manuelle de la coloration syntaxique, #95/#97) : au-delà de l'afficher correctement, le cabinet a comparé au comportement de ChatGPT qui permet d'exécuter directement une cellule de code Python dans la conversation et d'en voir le résultat.

Pas de travail avant que le besoin se confirme — portée très différente d'un ajustement de rendu : il faudrait un bac à sable d'exécution (isolation, limites CPU/mémoire/temps, pas d'accès réseau/fichiers du poste), une décision sur où il tourne (poste local vs VM centrale vs service tiers) et une revue sécurité dédiée avant d'exposer quoi que ce soit d'exécutable à une réponse de modèle. Distinct de #97 (habillage visuel des blocs de code), qui n'en dépend pas.
