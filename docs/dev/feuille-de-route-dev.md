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

## Prochaine : 1.3.0 — Inspecteur des échanges avec le modèle (outil de développement)

**Objectif.** Une fenêtre / vue **développement** qui montre, pour une conversation, **exactement ce qui a été envoyé et reçu à chaque tour** vers le modèle (et appels annexes : titrage, résumé+profil, OCR, vision, tool calls pièce jointe…) — pas seulement les bulles user/assistant visibles dans le chat.

**Pourquoi.** Aujourd’hui on ne voit côté UI que le message collaborateur et la réponse affichée. On ne voit pas le prompt réel (résumé glissant, profil de travail, messages système pièce jointe, fenêtre des 3 derniers, outils proposés, contenu extrait injecté, etc.). Indispensable pour déboguer style (1.2.2), Agents / Moduléo (1.4.0), n8n (1.5.0), PJ (1.6.0) et comprendre coût / tokens (lien avec 1.1.3).

**Périmètre envisagé.**
- Par conversation : liste des tours / appels, chacun avec le **payload** envoyé (messages `system` / `user` / `assistant`, tools, extraits de pièces jointes, métadonnées utiles : modèle, tokens, type d’appel).
- Réponse brute du modèle (avant éventuel post-traitement / animation UI).
- Accès restreint (compte administrateur et/ou flag dev) : contenu potentiellement sensible, pas un écran collaborateur standard.

**Recherche / décisions à trancher à l’ouverture.**
- Persister les payloads en base (rejouables après coup) vs journal éphémère / logs VM seulement.
- Où vit l’UI : panneau dans le poste, page admin, ou outil hors appli (logs structurés).
- Volume : tronquer les très gros extraits PJ à l’affichage tout en gardant la trace qu’ils étaient présents.
- Ne pas exposer la clé API Mistral ni les secrets dans cette vue.

## Ensuite : 1.4.0 — Premier Agent (pôle Administration) : lecture Moduléo via le chat

Premier **Agent** métier. Pôle **Administration**. Premier logiciel : **Moduléo** (utilisé par tout le cabinet).

**Objectif.** Depuis un prompt dans le chat, demander des **éléments issus de Moduléo** (via l’API, en **lecture seule**) et obtenir une **réponse utile** (ex. affaire, intervenants, … selon allowlist). Pas d’écriture Moduléo. Pas de n8n dans ce livrable : les appels passent par des **outils** (tool calling) + client HTTP **dans la VM** (Python), pas un workflow par route API.

**Hors périmètre 1.4.0 (→ 1.5.0).** Orchestration / création de workflows **n8n**, automatismes multi-étapes, écriture Moduléo.

**Orientation déploiement (tranchée pour 1.4.0, à garder en tête pour la suite).** Un Agent = configuration métier (prompt, pôle, outils) dans le flux chat de la **VM centrale**, pas un conteneur Docker par Agent / par pôle. Docker reste ce qu’il est aujourd’hui (ex. Postgres) ; pas de micro-services Agent pour ce premier livrable. Motif : prompts et outils légers (lecture API) n’ont pas de runtime propre — un conteneur par Agent ajouterait ops (réseau, versions, healthchecks) sans gain réel de déploiement, alors que plus tard peu de tech sera sur place pour l’opérer.

**Piste pour plus tard (pas 1.4.0)** — quand le besoin d’indépendance de déploiement / zéro coupure se confirmera (itérer un Agent sans republier les autres, éviter de couper le chat) :
- d’abord privilégier **config rechargeable** / hot-reload et, si besoin, **rolling** du cœur VM ;
- isoler en conteneur seulement ce qui a un **vrai cycle de vie** (adaptateur Moduléo en écriture, bac à sable d’exécution, dépendances lourdes, instance n8n) — plutôt **par système / capacité à risque** que « un Docker = un pôle » ;
- ne microservicer les Agents par pôle que si hot-reload + adaptateurs ne suffisent plus.

**Proposition d’organisation du code (explorée, pas tranchée).** Idée de **paquetiser** le premier Agent dans la VM (dossier dédié + README capacités + docs), cohérente avec « Agent = consigne / outils dans la VM ». Ce qui suit a été exploré en discussion ; **ce n’est pas encore une décision** — à l’ouverture de la 1.4.0 on peut encore retenir autre chose si une meilleure idée apparaît.

- **Découpage privilégié dans cette exploration** : Agent du pôle **Administration** d’un côté, intégration **Moduléo** de l’autre (Moduléo est le premier logiciel utilisé par cet Agent, pas l’Agent lui-même). Ex. `vm-centrale/src/vm_centrale/agents/administration/` + `…/integrations/moduleo/` (noms exacts à trancher). Variante plus simple au tout début : un seul dossier `moduleo/` avec note « sert le pôle Administration » — à scinder dès qu’Admin gagne un autre logiciel.
- **Emplacement** : code sous `src/vm_centrale/` (importable par le routeur chat, comme `analyse_pieces_jointes/`), pas un dossier docs orphelin à côté de `tests/`. Le pack `agents/` à la racine du dépôt reste **dev only** (skills/hooks Cursor/Claude, non déployé) — distinct des Agents métier runtime ; un README parent dans le dossier Agents métier le rappelle.
- **Vocabulaire runtime** : `consigne` (prompt) + `outils/` (schémas tool calling Mistral + handlers Python) + `client/` (HTTP Moduléo lecture seule). **Pas** de `skills/` / `hooks/` façon pack de développement — fausse analogie. Pas un outil / workflow par endpoint de la [doc API Moduléo](https://mwa-kpw-api.kipaware.fr/api/documentation) : plutôt une **allowlist** d’outils métier (ou un client HTTP borné), pour limiter tokens et surface d’erreur.
- **Docs** : `docs/` + README d’arborescence (ce qui est injecté dans le prompt vs rappelé via outil vs référence humaine) ; sous-dossiers type `api/` (endpoints retenus, limites, auth) et `metier/` si besoin. Pas toute la doc Moduléo brute sans triage (coût tokens).
- **À prévoir aussi** : allowlist explicite des capacités actuelles (`capacites.md` ou section figée du README) ; petit **registre / loader** pour brancher consignes + outils sans if spaghetti dans `conversations.py` ; secrets Moduléo dans `.env` / config VM, jamais dans `docs/` ; tests HTTP-boundary dans `vm-centrale/tests/`.
- **Hors proposition pour le premier livrable** : un Docker / service par Agent ; hooks façon Claude/Cursor ; n8n.

**Recherche / tests.**

- API Moduléo : auth, limites, endpoints utiles pour le Q&A Admin (serveur de **test** uniquement).
- Scénarios chat : ex. « retrouve l’affaire X / ses intervenants » → outil → réponse.
- Trancher / amender la proposition d’organisation ci-dessus à l’ouverture (ou documenter une alternative retenue).

## Ensuite : 1.5.0 — Workflows n8n (socle d’automatisation), branchés sur Moduléo 1.4.0

S’appuie sur les **outils / client Moduléo lecture** livrés en 1.4.0. n8n devient le **runtime d’automatisation** (scénarios multi-étapes, plus tard d’autres logiciels), pas un miroir 1:1 de chaque route API.

**Objectif.** Intégrer **n8n** (self-host envisagé sur le LAN) de façon **sûre** : l’Agent / la VM peut s’appuyer sur des workflows (déclencher, et selon garde-fous créer/modifier **inactifs**, idéalement depuis templates) en réutilisant ce qu’on sait déjà faire côté Moduléo. Les collaborateurs pourront à terme orchestrer des automates au-delà du simple Q&A chat — sans god-mode CRUD n8n ni activation libre en prod dès le premier jet.

**Périmètre envisagé.**
- Instance n8n de test ; client API / webhooks côté VM ; dossier d’intégration (ex. `integrations/n8n/`).
- Outils Agent bornés : list/get, exécuter un workflow existant, créer/update **inactif** (templates de préférence) ; activer / delete / credentials sous contrôle strict (admin ou validation).
- Premiers workflows utiles Admin qui **composent** des appels Moduléo (réutiliser la logique 1.4.0), pas « un workflow par endpoint ».
- Mistral peut **aider** à concevoir / paramétrer un automate ; l’exécution du workflow elle-même ne consomme pas de tokens (seuls les tours de chat + résultats réinjectés en consomment).

**Recherche / décisions à trancher à l’ouverture.**
- Self-host Docker vs autre ; où tourne n8n par rapport à la VM.
- Contrat outils chat ↔ n8n (webhook vs API execute).
- Gouvernance : qui active un workflow ; audit des exécutions.
- Comment réexposer ou appeler la stack Moduléo 1.4.0 depuis n8n (HTTP Request vers Moduléo vs rappel d’un service VM).

## Ensuite : 1.6.0 — Analyse et traitement des pièces jointes, approfondis

*(Anciennement numérotée 1.5.0 — décalée pour intercaler n8n en 1.5.0.)*

S’appuie sur la [1.1.2](../specs/v1.1.2-pieces-jointes.md) (pipeline d’extraction, une pièce jointe par message) et sur le premier **Agent** métier livré en 1.4.0. Deux limites actées volontairement en 1.1.2 sont à lever ici, pas avant : **plusieurs pièces jointes par message**, et un **traitement spécifique par pôle** (un agent Foncier ne traite pas un document comme un agent Urbanisme) — demande explicite du cabinet dès le grilling de 1.1.2, remise à plus tard faute d’Agent réel pour la justifier.

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
- Tests front (grilling 1.2.0) : pas de tests dédiés côté UI React en 1.2.0 (on reste sur les tests pytest HTTP-boundary existants + validation visuelle par l'admin). À une version pas encore numérotée : ajouter un filet de sécurité automatisé côté UI (ex. Playwright) puisque seul un agent IA maintient ce code sans relecture humaine technique — pertinent surtout quand le volume d'écrans aura grossi (1.3.0, 1.4.0, 1.5.0, 1.6.0 et au-delà).

### Lanceur poste (exécutable, pywebview)

Un exécutable qui ouvre une fenêtre (pages web du backend local). Fermer la fenêtre ne tuerait pas le process : accès encore possible dans le navigateur (`localhost` du poste).

Recherche : empaquetage Windows, icône / démarrage du backend, barre d’état vs process invisible, mise à jour.

### Déploiement, CI/CD, retours utilisateurs

Déployer pour avoir des retours. Automatiser depuis GitHub Actions / un hébergeur type Netlify.

Contraintes déjà vues : pas de VM centrale physique pour un CD du relais ; Netlify (Internet) vs poste local + LAN ; Actions pour pytest seulement ; pilote sur une machine en attendant.

Ajout (grilling 1.2.0) : depuis 1.2.0, le front `poste` passe par un build Vite/React — en attendant cette CI, le dossier compilé (`dist/`) est committé directement dans git (comme `static/` aujourd'hui), aucune étape de build sur le poste. Quand cette CI/CD sera mise en place, elle devra aussi prendre en charge le build du front (au lieu du commit direct du `dist/` compilé).

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
- RAG sur un corpus cabinet, distinct des pièces jointes du fil courant (1.1.2 / 1.6.0).
- **Optimisation du résumé+profil actuel (1.1.1)** — **dans la même version** que le reste de ce chantier mémoire, pas une version à part. Aujourd’hui, dès qu’il y a des messages sortants, chaque tour fait **1 chat + 1 appel résumé/profil** (agrégés tous les deux en « Chat » côté conso) : fiable, mais ~2× les requêtes après le premier message. Pistes à trancher alors : résumé moins fréquent (tous les N tours / seuil de tokens), résumé en arrière-plan après la réponse affichée (façon *Dreaming*), ou mémoire à la demande (outil / notes) — en gardant éventuellement le combo résumé léger + embeddings pour le long terme.

### Éléments de réponse visuels plus riches dans le chat (graphiques, documents générés)

Constat (grilling 1.2.2) : au-delà du Markdown borné (gras, listes) posé en 1.2.2, le cabinet a exprimé l'envie qu'une réponse de l'IA puisse à terme intégrer des éléments plus riches — graphiques, voire génération de documents (façon Word/Excel, à la manière de ce que proposent certains assistants IA) — plutôt que de la prose seule.

Pas de travail dédié avant que le besoin se confirme. Le rendu posé en 1.2.2 (`react-markdown` + mapping de composants React par élément Markdown) est délibérément choisi pour rendre cette extension simple le moment venu : ajouter un nouveau type de bloc revient à enregistrer un composant supplémentaire dans ce mapping, sans reprendre l'architecture du rendu.

### Exécution de code dans le chat (cellules Python exécutables, façon ChatGPT)

Constat (validation manuelle de la coloration syntaxique, #95/#97) : au-delà de l'afficher correctement, le cabinet a comparé au comportement de ChatGPT qui permet d'exécuter directement une cellule de code Python dans la conversation et d'en voir le résultat.

Pas de travail avant que le besoin se confirme — portée très différente d'un ajustement de rendu : il faudrait un bac à sable d'exécution (isolation, limites CPU/mémoire/temps, pas d'accès réseau/fichiers du poste), une décision sur où il tourne (poste local vs VM centrale vs service tiers) et une revue sécurité dédiée avant d'exposer quoi que ce soit d'exécutable à une réponse de modèle. Distinct de #97 (habillage visuel des blocs de code), qui n'en dépend pas.
