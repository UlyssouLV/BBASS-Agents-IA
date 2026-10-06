# Feuille de route de dev

Ordre des **prochaines versions** produit, plus les sujets encore sans numéro.

Ce n’est **pas** une spec (ça vient après « Ouvre la version »).

## Déjà livré

- **1.0.x** — Socle : comptes, connexion, chat, relais Mistral, session persistée (keyring), LAN Castries.
- **1.1.0** — Comptes administrateurs, multi-pôles, mot de passe généré / changement forcé, révocation, affichage pôle/agence dans le chat.
- **1.1.1** — Conversations persistées sur la VM (PostgreSQL) : plusieurs fils, reprise après rechargement / autre poste, historique borné (3 derniers messages + résumé glissant), profil de travail lecture seule ; pas de stockage Mistral Conversations.
- **1.1.2** — Pièces jointes : upload PDF/Word/Excel/image sur un message (une par message), extraction (OCR Mistral, locale pour Word/Excel, vision Mistral pour l'image), contenu injecté dans le chat, mention courte dans le résumé glissant, rappel via un outil si la pièce jointe sort de la fenêtre ; jamais la Files API Mistral.
- **1.1.3** — Consommation : une ligne `Consommation` par appel Mistral réel (chat, titrage, résumé+profil, OCR, vision), tokens ou pages selon le type, coût figé au tarif du jour de l'appel (pas d'API de tarification Mistral, tarifs en dur dans le code). Fenêtre Consommation côté collaborateur (total + classement des conversations par coût) ; onglet Consommations côté administrateur (comptes classés par coût, jamais de détail par conversation).
- **1.2.0** — Interface poste réécrite en React/TypeScript/Vite (shadcn/ui, Tailwind, TanStack Query), build committé dans git (jamais de Node.js requis sur un poste, [ADR-0010](../adr/0010-front-poste-react-typescript-vite.md)) ; écran comptes (compte administrateur) passé de blocs empilés à une table avec une modale par action.
- **1.2.1** — Identité visuelle du poste calquée sur le logo BBASS Géomètre-Expert (couleurs, police Manrope auto-hébergée, logo, favicon) et disposition façon ChatGPT (sidebar avec conversations et puce compte, page Profil dédiée, Panel d'administration dédié avec tableaux/étiquettes shadcn-ui) ; aucun changement côté VM centrale ni du contrat API.
- **1.2.2** — Style de réponse de l'IA : prompt système de style (vm-centrale) sur l'appel de chat principal uniquement (vouvoiement, pas de remplissage réflexe, emojis rares et signifiants, pas de relance systématique en fin de réponse, Markdown borné autorisé — gras/italique/listes/paragraphes), jamais sur le titrage ni le résumé + profil de travail. Rendu Markdown borné côté poste (`react-markdown`, allowlist `strong`/`em`/`ul`/`ol`/`li`/`p`, tout le reste neutralisé au rendu), en remplacement du texte brut affiché jusqu'ici.
- **1.2.3** — Amélioration des délais de chargement (pages et conversations) : cache TanStack Query revu par requête (liste des conversations, détail de conversation, Profil, Panel d'administration), `placeholderData` sur le détail de conversation pour garder l'ancien contenu affiché pendant le rafraîchissement ; pagination par curseur de `GET /conversations/{id}` (vm-centrale), fenêtre de messages la plus récente par défaut, historique plus ancien chargé au défilement façon ChatGPT (pas de pagination par page) ; instrumentation de temps légère (`performance.mark`/`performance.measure`) sur l'ouverture/bascule de conversation, Profil et Panel d'administration, désactivée par défaut, posée pour être réutilisée par la 1.3.0.
- **1.3.0** — Inspecteur des échanges avec le modèle (outil de développement) : Mode développeur ouvert par `Ctrl+Maj+D` depuis n'importe quel compte, dans un nouvel onglet `/inspecteur`, débloqué par la Clé d'administration VM (saisie en mémoire de l'onglet, jamais stockée) ; accès à toutes les conversations de tous les comptes ([ADR-0012](../adr/0012-mode-developpeur-cle-admin-vm-tous-comptes.md)) — comptes → conversations → fil chronologique des échanges. Chaque appel Mistral réel (chat, titrage, résumé+profil, OCR, vision, chaque aller-retour de tool calling) est capturé dans une table `echanges_inspecteur` séparée de `Consommation` (payload exact envoyé, réponse brute, statut succès/échec), supprimée en cascade avec la conversation ; un échange en échec survit au rollback du tour ; pièce jointe affichée comme référence cliquable plutôt qu'en texte brut ; jamais la clé API Mistral dans un échange. Historique seulement, lecture seule.
- **1.3.1** — Le chat ne fige plus ses inventions ([#110](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/110), [spec](../specs/v1.3.1-chat-ne-fige-plus-ses-inventions.md)) : consigne de chat sans lien proposé (seule une URL écrite par le compte peut ressortir), refus d’un fait inventé sans demande explicite ; pièce jointe traitée comme déjà jointe et décrite par son seul extrait ; résumé glissant qui note « proposé, non vérifié » ce que l’assistant a affirmé, plafonné à 1 500 caractères ; profil de travail réécrit en entier sous 800 caractères au lieu d’empiler des deltas, profils existants vidés. Garde-fous centralisés dans `vm_centrale/garde_fous/` : URL absente des messages du compte retirée ; sans document ni chiffre fourni, une réponse chiffrée est remplacée par une phrase fixe de la VM ; avec une source, seuls les chiffres présents restent. Pas de changement du contrat HTTP du poste.

## En cours : 1.4.0 — Recherche web dans le chat

**Objectif.** Un outil de recherche internet, exécuté par la VM et branché sur le chat comme l’outil pièce jointe, pour que le modèle trouve une page réelle au lieu d’en inventer l’adresse. Ouverte le 2026-10-06 ([#117](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/117), [spec](../specs/v1.4.0-recherche-web-dans-le-chat.md)) : SearXNG auto-hébergé ([ADR-0013](../adr/0013-recherche-web-searxng-auto-heberge.md)), pages entières nettoyées puis appel d’extraction isolé du contexte ([ADR-0014](../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)), outils du modèle centralisés dans `vm_centrale/outils/`, boucle d’outils sur 3 tours, inspecteur chronologique Mistral / local.

**Hors périmètre.** Moduléo, déploiement, n8n. Pas de changement du contrat HTTP du poste : l’outil reste interne à l’appel de chat.

**Bug connu à la livraison.** Quand la recherche ne trouve rien, l’IA invente des chiffres et des sources au lieu de le dire ; les garde-fous n’en retirent qu’une partie et abîment la mise en forme ([#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131)). La 1.4.0 est finalisée avec ce bug ; correction en **1.4.5**.

## Ensuite : 1.4.1 — Mémoire de la conversation (pièces jointes et recherches)

**Objectif.** Le résumé glissant ne garde qu’une mention courte d’une pièce jointe sortie de la fenêtre de 3 ; depuis la 1.4.0, une recherche web n’y laisse que sa requête et ses URL. Cette version garde à part, pour la durée de la conversation, la liste des pièces jointes **et des recherches** partagées, et donne au modèle un outil (tool calling) pour se les rappeler et en relire le contenu. Piste née de l’ouverture de la 1.3.1 ([spec](../specs/v1.3.1-chat-ne-fige-plus-ses-inventions.md)), élargie aux recherches à l’ouverture de la 1.4.0 ([spec](../specs/v1.4.0-recherche-web-dans-le-chat.md)) : à confirmer par le retest de la 1.3.1 (une URL ou une pièce jointe du compte survit-elle au résumé plafonné ?).

**Hors périmètre.** Moduléo, déploiement, n8n. Pas de changement du contrat HTTP du poste : l’outil reste interne à l’appel de chat.

- Conservation d’une pièce jointe au-delà de sa conversation d’origine (usage multi-conversationnel, matière pour entraîner les futurs Agents) : piste évoquée dès le grilling 1.1.2, pas tranchée.

## Ensuite : 1.4.2 — Tokenizer Mistral pour le plafond des pages web

**Objectif.** En 1.4.0, le plafond global des pages nettoyées (~80 % de la fenêtre du modèle d’extraction) est une estimation en caractères (3 caractères ≈ 1 token), faute de tokenizer Mistral en local. Cette version ajoute le tokenizer officiel (`mistral-common` / Tekken) pour compter les tokens réels des pages avant de retirer une page entière, et ainsi caler le seuil sur le modèle d’extraction plutôt que sur une approximation. À trancher à l’ouverture : quel artefact tokenizer coller à `mistral-small-latest` (fichier `tekken.json` versionné ou téléchargé), et si le compte sert seulement au plafond ou aussi à une prévision affichée avant l’appel.

**Hors périmètre.** Suivi de consommation facturée (reste basé sur l’`usage` renvoyé par l’API Mistral). Moduléo, déploiement, n8n. Pas de changement du contrat HTTP du poste.

## Ensuite : 1.4.3 — Cache des pages web entre conversations

**Objectif.** En 1.4.0, les pages téléchargées par une recherche ne vivent que le temps de leur conversation. Garder un cache commun (clé : l’URL) éviterait de retélécharger une page déjà lue. À trancher à l’ouverture : durée de validité au-delà de laquelle on retélécharge (une page change), règle de partage entre comptes (pages publiques seulement), taille et purge du cache. Piste née de l’ouverture de la 1.4.0.

## Ensuite : 1.4.4 — Statut d’attente dynamique pendant une réponse

**Objectif.** Remplacer l’indicateur figé du type « Réflexion… » par un statut qui suit **en direct** ce que la VM est en train de faire (ex. une recherche web en cours, une page lue, une extraction). Formulations, canaux (streaming, polling…), granularité et libellés : **à trancher au grilling** à l’ouverture — rien n’est fixé ici.

**Hors périmètre.** Changer le contenu final de la réponse ; modes Rapide / Approfondi.

## Ensuite : 1.4.5 — Dire « pas trouvé » plutôt qu’inventer après une recherche

**Objectif.** Corriger le bug [#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131), constaté au test humain de la 1.4.0 : quand la recherche (ou la pièce jointe) ne contient pas l’information, la réponse dit qu’elle ne l’a pas trouvée, au lieu d’estimer des tarifs, des dates ou de citer une source qui n’existe pas. Jamais « sourcé » ni « confirmé par » sans résultat de l’outil qui le contient ; une source dont le lien est retiré ne reste pas affichée comme source ; le contenu de la pièce jointe prime sur une généralité du web. Les garde-fous ne cassent plus la mise en forme (indentation des listes et tableaux, parenthèses vides) ; une page quasi vide n’est pas comptée comme lue ; la date du jour est donnée en toutes lettres et seule l’année va dans la requête. À trancher au grilling : sort d’une réponse dont beaucoup de chiffres sont retirés (marqueur visible, réécriture, phrase fixe), contrôle des petits montants (« 5 € »), et traitement ici ou à part du profil de travail et du résumé qui débordent d’une conversation à l’autre.

**Hors périmètre.** Pages refusées par les sites (HTTP 403) et PDF trouvés sur le web ; vérification de la fiabilité des sources ; modes Rapide / Approfondi. Pas de changement du contrat HTTP du poste.

## Ensuite : 1.5.0 — Moduléo en lecture (outil transverse) + premier branchement via l’Agent Administration

**Moduléo n’est pas « l’outil du pôle Administration ».** C’est un logiciel **cabinet**, susceptible d’être utilisé par **tous les pôles**, avec des **restrictions / allowlists différentes** selon le pôle (et l’Agent) qui l’appelle. Le pôle Administration est seulement le **premier** à brancher Moduléo dans le chat (premier Agent métier + premier jeu d’outils Moduléo), pas le propriétaire exclusif de l’intégration.

**Objectif.** Depuis un prompt dans le chat (d’abord via l’Agent **Administration**), demander des **éléments issus de Moduléo** (API, **lecture seule**) et obtenir une **réponse utile** (ex. affaire, intervenants, … selon allowlist **du pôle appelant**). Pas d’écriture Moduléo. Pas de n8n dans ce livrable : les appels passent par des **outils** (tool calling) + client HTTP **dans la VM** (Python), pas un workflow par route API.

**Hors périmètre 1.5.0.** Orchestration / workflows **n8n** (→ **1.8.0**), automatismes multi-étapes, écriture Moduléo. Documentation mémoire / souveraineté (→ **1.6.0**). Déploiement / CI/CD / installateur poste (→ **1.7.0**). Allowlists Moduléo pour les **autres** pôles (Foncier, etc.) : plus tard, en réutilisant la même intégration.

**Auth Moduléo (tranché pour 1.5.0).** Pour ce premier livrable on **force un périmètre minimal** : **une seule clé API** Moduléo (config VM, ex. `.env`) et les essais / l’usage ciblé sur **un seul utilisateur** Moduléo (un SecurityCode lié à ce compte de test). Pas de multi-clés, pas d’affectation de codes depuis le panel d’administration, pas de « rôles de clés » dans BBASS. Objectif : valider le Q&A lecture (chat → outils → API) et, sur serveur de test, le comportement auth (identité, droits, historique) avant d’industrialiser.

**Si multi-clés / multi-collabs s’avère nécessaire** → version **1.5.x** dédiée : gestion de plusieurs clés, liaison / affectation depuis le **panel d’administration** (création côté Moduléo reste chez Moduléo ; BBASS stocke et affecte ce qu’il doit pour appeler l’API). Pas anticipé dans le code 1.5.0 au-delà de ne pas se fermer la porte (ex. un seul enregistrement de config plutôt qu’une usine à tables).

**Orientation déploiement (tranchée pour 1.5.0, à garder en tête pour la suite).** Un Agent = configuration métier (prompt, pôle, outils) dans le flux chat de la **VM centrale**, pas un conteneur Docker par Agent / par pôle. Docker reste ce qu’il est aujourd’hui (ex. Postgres) ; pas de micro-services Agent pour ce premier livrable. Motif : prompts et outils légers (lecture API) n’ont pas de runtime propre — un conteneur par Agent ajouterait ops (réseau, versions, healthchecks) sans gain réel de déploiement, alors que plus tard peu de tech sera sur place pour l’opérer.

**Piste pour plus tard (pas 1.5.0)** — quand le besoin d’indépendance de déploiement / zéro coupure se confirmera (itérer un Agent sans republier les autres, éviter de couper le chat) :
- d’abord privilégier **config rechargeable** / hot-reload et, si besoin, **rolling** du cœur VM ;
- isoler en conteneur seulement ce qui a un **vrai cycle de vie** (adaptateur Moduléo en écriture, bac à sable d’exécution, dépendances lourdes, instance n8n) — plutôt **par système / capacité à risque** que « un Docker = un pôle » ;
- ne microservicer les Agents par pôle que si hot-reload + adaptateurs ne suffisent plus.

**Proposition d’organisation du code (explorée, pas tranchée).** Paquetiser **intégration logicielle** et **Agent par pôle** séparément. Ce qui suit a été exploré en discussion ; **ce n’est pas encore une décision** — à l’ouverture de la 1.5.0 on peut encore retenir autre chose si une meilleure idée apparaît.

- **Découpage (conséquence du modèle transverse).**  
  - `…/integrations/moduleo/` — client HTTP, auth (clé + SecurityCode), docs API, capacités Moduléo **partagées** (pas « sous » Administration).  
  - `…/agents/administration/` — consigne + **allowlist d’outils** Moduléo autorisés pour ce pôle (sous-ensemble / restrictions Admin).  
  Plus tard : `agents/foncier/`, etc. réutilisent la **même** intégration Moduléo avec une allowlist différente. **Ne pas** mettre Moduléo uniquement sous `agents/administration/moduleo/` (ça figerait le mauvais modèle).  
  Variante acceptable en tout début de proto : un seul dossier `moduleo/` **à la racine integrations**, avec une allowlist « Admin » en dur — à scinder Agents dès le 2ᵉ pôle.
- **Emplacement** : code sous `src/vm_centrale/` (importable par le routeur chat, comme `analyse_pieces_jointes/`), pas un dossier docs orphelin à côté de `tests/`. Le pack `agents/` à la racine du dépôt reste **dev only** (skills/hooks Cursor/Claude, non déployé) — distinct des Agents métier runtime ; un README parent dans le dossier Agents métier le rappelle.
- **Vocabulaire runtime** : côté Agent = `consigne` + `outils/` (schémas tool calling exposés **pour ce pôle**) ; côté intégration = `client/` Moduléo lecture seule. **Pas** de `skills/` / `hooks/` façon pack de développement. Pas un outil / workflow par endpoint de la [doc API Moduléo](https://mwa-kpw-api.kipaware.fr/api/documentation) : allowlist par pôle (ou client HTTP borné selon le pôle appelant).
- **Docs** : sous `integrations/moduleo/docs/` + README d’arborescence (injecté vs outil vs référence humaine) ; `api/` / `metier/` si besoin. Pas toute la doc Moduléo brute sans triage (coût tokens). Les restrictions **par pôle** se documentent plutôt côté Agent (`capacites.md` / allowlist), pas en dupliquant l’intégration.
- **À prévoir aussi** : allowlist explicite des capacités **Administration** pour 1.5.0 ; petit **registre / loader** (Agent → outils Moduléo filtrés par pôle) sans if spaghetti dans `conversations.py` ; secrets Moduléo (**une** clé + SecurityCode du compte de test) dans `.env` / config VM, jamais dans `docs/` ; tests HTTP-boundary dans `vm-centrale/tests/`.
- **Hors proposition pour le premier livrable** : un Docker / service par Agent ; hooks façon Claude/Cursor ; n8n ; multi-clés / panel d’affectation (→ **1.5.x** si besoin) ; branchement Moduléo pour tous les pôles d’un coup.

**Recherche / tests.**

- API Moduléo : auth (`ApiKey` + `SecurityCode`), limites, endpoints utiles pour le Q&A Admin (serveur de **test** uniquement) — avec **un** utilisateur de test.
- Scénarios chat : ex. « retrouve l’affaire X / ses intervenants » → outil → réponse.
- Valider sur test : identité (`utilisateurencours`), refus si mauvais code, comportement des droits / historique ; décider ensuite si une **1.5.x** multi-clés / multi-collabs est nécessaire.
- Trancher / amender la proposition d’organisation ci-dessus à l’ouverture (ou documenter une alternative retenue).

## Ensuite : 1.6.0 — Documentation : mémoire conversationnelle et souveraineté des données

**Objectif.** Deux documents produit / fonctionnels (même format que la doc recherche web prévue ailleurs dans cette feuille), rédigés dans `docs/features/` **et** portés chacun par une issue GitHub labellee **`documentation`** (plan, schémas, captures, exemples). Pas de changement de code produit hors ajustements de doc / schémas / exemples de tests cités. Placée après Moduléo lecture (**1.5.0**) pour documenter aussi l’état mémoire / hébergement une fois ce socle métier posé, avant le déploiement postes.

1. **Persistance de la mémoire** (`docs/features/memoire-conversationnelle.md` ou équivalent). Schéma complet (tables / relations : conversations, messages, résumé glissant, profil de travail, pièces jointes, résultats de recherche web, etc.), flux tour par tour (ce qui entre, ce qui sort de la fenêtre de 3, ce qui est plafonné, ce que le modèle relit via outils), choix et décisions déjà prises et **pourquoi** (persistance VM vs API Conversations Mistral, séparation identité / profil, etc.). Exemples concrets (inspecteur, états en base) et références aux tests HTTP-boundary qui verrouillent ces comportements. À l’ouverture : si la **1.4.1** (mémoire pièces jointes + recherches) n’est pas encore livrée, documenter l’existant et prévoir une section « prévu / à mettre à jour » pour l’outil de rappel.

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

**Recherche / décisions à trancher à l’ouverture.**
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

S’appuie sur la [1.1.2](../specs/v1.1.2-pieces-jointes.md) (pipeline d’extraction, une pièce jointe par message) et sur le premier **Agent** métier / Moduléo livré en 1.5.0. Deux limites actées volontairement en 1.1.2 sont à lever ici, pas avant : **plusieurs pièces jointes par message**, et un **traitement spécifique par pôle** (un agent Foncier ne traite pas un document comme un agent Urbanisme) — demande explicite du cabinet dès le grilling de 1.1.2, remise à plus tard faute d’Agent réel pour la justifier.

**Objectif.** Une pièce jointe mieux exploitée dans la durée d’une conversation (le contenu retrouvé reste fiable une fois hors de la fenêtre des derniers messages, cf. les essais fonctionnels 1.1.2) et mieux exploitée selon qui la reçoit (le pôle de l’Agent destinataire).

**Recherche.**

- Plusieurs pièces jointes par message : impact sur le schéma `PieceJointe` (déjà pensé pour ne pas bloquer ça), sur l’outil `obtenir_contenu_piece_jointe` (choisir parmi plusieurs plutôt qu’une seule hors fenêtre), sur le résumé glissant (une mention courte par pièce jointe, pas une agrégée).
- Traitement par pôle : qu’est-ce qui change concrètement pour un même format (PDF, image, …) selon le pôle de l’Agent qui le reçoit — nouveau prompt d’extraction, post-traitement dédié, ou simple différence de consigne à l’IA plutôt qu’un pipeline dupliqué.
- Fiabilité de l’analyse elle-même, au-delà de la plomberie : enseignements des essais fonctionnels 1.1.2 (ex. liens inventés entre pièces jointes sans preuve, confusions de vocabulaire métier propre à un document) qui ne relèvent ni de la fenêtre de 3 messages ni du profil de travail.
- Conservation d’une pièce jointe au-delà de sa conversation d’origine (usage multi-conversationnel, matière pour entraîner les futurs Agents) : piste évoquée dès le grilling 1.1.2, pas tranchée.

## Plus tard (pas encore numéroté)

### Bug — lien de source peu visible (#99)

Constat (essai manuel 2026-10-05, suite #98) : malgré les travaux front sur le rendu des sources, l’affichage **ne valide toujours pas** les critères — le texte de l’ancre n’est pas clairement cliquable (URL au survol natif), et l’affordance (couleur / soulignement) ne rend pas le lien repérable sans pastille seule, ni sans laisser croire que toute la phrase est cliquable.

Suivi : [#99](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/99) (`bug`). À traiter dans une version ultérieure (front `LienSource` / Markdown chat), hors version courante.

### Bug — bascule de conversation pendant qu’une réponse est en cours

Constat : on démarre / envoie un message, l’IA « réfléchit », puis on clique une **autre** conversation dans la sidebar → la **sélection** dans la liste change bien, mais le **fil de chat** affiché ne suit pas (reste celui de la conversation en attente de réponse).

À corriger dans une version ultérieure (front poste) : synchroniser l’affichage du fil avec la conversation sélectionnée même si une requête de chat est encore en vol ; décider si on annule / ignore la réponse qui arrive pour l’ancien fil, ou si on la range silencieusement sans écraser le fil affiché.

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

Pistes à trancher à l’ouverture : ne lire / extraire les pages que si les snippets ne suffisent pas ; outil `lire_page(url)` pour cibler les pages utiles sans tout télécharger ; plafonds et format des résultats renvoyés au modèle ; affiner la consigne d’extraction ; éventuel lien avec le cache 1.4.3. S’appuie sur le registre d’outils et [ADR-0014](../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md). Hors périmètre tant que la 1.4.0 n’a pas été retestée. Distinct des modes Rapide / Approfondi ci-dessous (ceux-là changent le contrat HTTP du poste).

**Documentation livrable (même version).** Un document dans le dépôt qui décrit **très exactement et fonctionnellement** le fonctionnement du tool calling de recherche web (paramètres, déroulé VM, pannes, ce qui part vers le moteur / l’extraction / le modèle principal, ce qui est persisté, rôle des garde-fous) — langage produit / fonctionnel, pas un dump de code. Des **schémas** illustrent tous les cas et cheminements possibles (succès snippets seuls, lecture de pages, extraction, moteur indisponible, page en échec, plafond, etc.). À l’ouverture : créer une issue GitHub labellee **`documentation`** (label déjà présent dans le dépôt) qui porte le plan de ce document, les captures / images d’exemples (inspecteur, messages `tool`, réponses) et toute info complémentaire ; le doc versionné dans `docs/` reste la référence une fois rédigé.

### Pages web refusées (HTTP 403) et PDF trouvés sur le web

Constat (test humain 1.4.0, conversations 89 à 92) : sur 24 pages téléchargées, 9 refusées en HTTP 403 (dont Légifrance et leboncoin), 1 PDF non lu, 5 pages JavaScript sans contenu exploitable. Légifrance est la source officielle d’un cabinet : la réponse se rabat sur un site tiers. Pistes à trancher à l’ouverture : en-têtes de navigateur plus complets, API officielle (Légifrance / PISTE) pour les textes de loi, lecture des PDF, rendu JavaScript. Distinct de #131 (ce que le modèle écrit quand il n’a rien trouvé, 1.4.5).

### Vérification de la fiabilité des sources web

Constat (essais manuels 1.4.0) : `rechercher_web` ramène des pages et l’IA les cite ; rien ne dit encore si une source est digne de confiance (site officiel, presse, blog, forum, page commerciale). Une amélioration ultérieure de la recherche web ferait **évaluer la fiabilité des sites sourcés** avant ou avec la réponse : indiquer au collaborateur le degré de confiance, écarter ou rétrograder les sources douteuses, et garder une trace lisible (inspecteur ou mention courte).

Pistes à trancher à l’ouverture : critères (domaine `.gouv.fr` / institutionnel, liste blanche cabinet, score heuristique, second passage modèle…), moment du contrôle (à la réception des résultats, après lecture des pages, à la rédaction), ce que voit le collaborateur, et le lien avec les garde-fous URL déjà en place. S’appuie sur la 1.4.0 et le registre d’outils. Distinct de l’optimisation **par défaut** (tokens / snippets) et des modes Rapide / Approfondi.

### Modes de réponse (Rapide / Approfondi) et outils de lecture plus fins

Constat (ouverture 1.4.0) : plusieurs façons d’utiliser les outils sont possibles selon l’effort voulu. Un mode choisi par le collaborateur réglerait le nombre de tours d’outils, le nombre de pages lues, un outil `lire_page(url)` (le modèle choisit ses pages au lieu de prendre les premières), un appel de synthèse, ou le modèle utilisé. Change le contrat HTTP du poste (choix du mode). Le découpage de la 1.4.0 (registre d’outils, appel d’extraction isolé, [ADR-0014](../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)) est fait pour s’y brancher. Distinct de l’optimisation **par défaut** de la recherche web et de la **vérification de fiabilité des sources** (rubriques précédentes), qui ne demandent pas de choix utilisateur.

### Exécution de code dans le chat (cellules Python exécutables, façon ChatGPT)

Constat (validation manuelle de la coloration syntaxique, #95/#97) : au-delà de l'afficher correctement, le cabinet a comparé au comportement de ChatGPT qui permet d'exécuter directement une cellule de code Python dans la conversation et d'en voir le résultat.

Pas de travail avant que le besoin se confirme — portée très différente d'un ajustement de rendu : il faudrait un bac à sable d'exécution (isolation, limites CPU/mémoire/temps, pas d'accès réseau/fichiers du poste), une décision sur où il tourne (poste local vs VM centrale vs service tiers) et une revue sécurité dédiée avant d'exposer quoi que ce soit d'exécutable à une réponse de modèle. Distinct de #97 (habillage visuel des blocs de code), qui n'en dépend pas.
