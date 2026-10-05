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

## Prochaine : 1.2.2 — Style de réponse de l’IA (ton, format, rendu)

**Constat.** Les réponses actuelles sont souvent longues, très structurées (titres `##`, gras `**…**`, listes, tableaux, séparateurs `---`, emojis ✅/❌, questions de relance en fin), ce qui sonne « ChatGPT générique » plus que « collaborateur BBASS ». Le front affiche aujourd’hui le **texte brut** (`message.contenu` dans une balise `<p>`, sans rendu Markdown) : les `**` et `##` apparaissent donc littéralement, ce qui aggrave l’effet bizarre. Aucun message système de style n’est envoyé au modèle pour le chat — seulement résumé glissant, profil de travail, et contexte pièce jointe (1.1.1 / 1.1.2).

**Ce n’est pas un format standard imposé à tous les modèles.** C’est un **comportement par défaut fréquent** après entraînement / alignement (assistant « utile », structuré, pédagogique). Chaque famille de modèles (Mistral, GPT, Claude…) a ses tics ; sans consigne, le style **varie** d’un modèle à l’autre et même d’un tour à l’autre. Ce n’est pas un schéma API unique partagé — c’est du Markdown / prose libre que le modèle invente.

**Comment on contrôle ça (pas besoin de tool calling / MCP pour le style).**
- **Levier principal : un prompt système de style** (consignes stables côté VM : ton cabinet, longueur, quand utiliser listes / titres, français, pas de blabla de fin, etc.). Suffisant pour la majorité des cas. Pas de MCP ni d’outil dédié « changer le style » : le style n’est pas une action à appeler, c’est une **consigne permanente**.
- **Rendu front (optionnel mais lié)** : soit on **interdit** le Markdown côté modèle et on garde du texte simple ; soit on **autorise** un Markdown borné et on le **rend** proprement (titres, gras, listes) — aujourd’hui ni l’un ni l’autre n’est tranché, d’où l’affichage brut des `**`.
- **Sortie structurée (JSON)** : utile pour des écrans métier (fiche, plan d’automate Moduléo…), pas pour remplacer le style de la prose du chat.
- **Par Agent / pôle (plus tard)** : un Agent Administration / Moduléo n’aura pas forcément le même ton qu’un Agent Foncier ; le style peut devenir une brique par Agent une fois 1.4.0+ en place.

**Objectif.** Des réponses lisibles, professionnelles, stables d’un tour à l’autre (et autant que possible d’un modèle à l’autre via la même consigne), adaptées au cabinet — sans essay encyclopédique non demandé.

**Recherche / décisions à trancher à l’ouverture.**
- Contenu du prompt de style (longueur max relative, Markdown oui/non/borné, tutoiement vs vouvoiement, signature / relance en fin de message).
- Rendu : texte brut contraint vs Markdown rendu côté React.
- Une consigne globale V1 vs styles par Agent dès qu’il y en a plusieurs.
- Mesure simple : mêmes questions de test avant/après sur le modèle actuel (et un second si multi-modèles un jour).

## Ensuite : 1.2.3 — Amélioration des délais de chargement (pages et conversations)

**Constat.** Chaque changement d’écran (chat, profil, admin…) et surtout l’ouverture / le basculement de conversation est **trop lent** au quotidien. Au-delà de l’absence de cache côté front (TanStack Query quasi sans stratégie de `staleTime` / conservation des listes), la latence reste élevée : impression de tout recharger à chaque clic, y compris des données déjà vues.

**Objectif.** Des navigations et des ouvertures de conversation **ressenties comme rapides** : moins d’attentes bloquantes, réutilisation intelligente de ce qui est déjà en mémoire, et identification / réduction des vrais goulots (poste, VM, payload conversations, rendu).

**Pistes à creuser à l’ouverture (pas tranchées).**
- Cache / invalidation TanStack Query : liste des conversations, détail d’une conversation, profil, conso — conserver au changement d’écran, invalider seulement quand un envoi / rename / delete le justifie.
- Chargement conversation : payload trop gros (tous les messages d’un coup) ? pagination / fenêtre locale vs tout le fil ; skeleton / contenu précédent pendant le fetch.
- Réseau : appels en série inutiles, waterfalls poste → VM, timeouts ; mesurer avant d’optimiser.
- Rendu : coût des animations (frappe réponse), re-renders React au changement de conversation.
- Critère de succès : scénarios chronométrés (ouvrir une conversation connue, basculer entre deux fils, aller-retour Profil ↔ Chat) avant / après.

## Ensuite : 1.3.0 — Inspecteur des échanges avec le modèle (outil de développement)

**Objectif.** Une fenêtre / vue **développement** qui montre, pour une conversation, **exactement ce qui a été envoyé et reçu à chaque tour** vers le modèle (et appels annexes : titrage, résumé+profil, OCR, vision, tool calls pièce jointe…) — pas seulement les bulles user/assistant visibles dans le chat.

**Pourquoi.** Aujourd’hui on ne voit côté UI que le message collaborateur et la réponse affichée. On ne voit pas le prompt réel (résumé glissant, profil de travail, messages système pièce jointe, fenêtre des 3 derniers, outils proposés, contenu extrait injecté, etc.). Indispensable pour déboguer style (1.2.2), Agents (1.4.0), PJ (1.5.0) et comprendre coût / tokens (lien avec 1.1.3).

**Périmètre envisagé.**
- Par conversation : liste des tours / appels, chacun avec le **payload** envoyé (messages `system` / `user` / `assistant`, tools, extraits de pièces jointes, métadonnées utiles : modèle, tokens, type d’appel).
- Réponse brute du modèle (avant éventuel post-traitement / animation UI).
- Accès restreint (compte administrateur et/ou flag dev) : contenu potentiellement sensible, pas un écran collaborateur standard.

**Recherche / décisions à trancher à l’ouverture.**
- Persister les payloads en base (rejouables après coup) vs journal éphémère / logs VM seulement.
- Où vit l’UI : panneau dans le poste, page admin, ou outil hors appli (logs structurés).
- Volume : tronquer les très gros extraits PJ à l’affichage tout en gardant la trace qu’ils étaient présents.
- Ne pas exposer la clé API Mistral ni les secrets dans cette vue.

## Ensuite : 1.4.0 — Premier Agent (pôle Administration), axé Moduléo

Premier **Agent** métier. Pôle **Administration**. Premier périmètre logiciel : **Moduléo** (utilisé par tout le cabinet), pas tout le métier d’un coup.

**Objectif.** Avancer **lentement** et le plus **sûrement** possible. Configurer l’Agent pour qu’il comprenne Moduléo et puisse, d’abord en **lecture** (pas d’écriture sur le serveur Moduléo) : s’appuyer sur la doc / l’API, récupérer de l’information. Les **automatismes** ne sont pas obligatoires dès le premier livrable : le modèle conversationnel doit déjà être capable de **pondre un plan d’implémentation** d’un automate Moduléo (comment on les générera / brancherait plus tard).

**Recherche / tests.**

- API Moduléo : ce qu’elle permet, limites, auth.
- Essais uniquement sur un **serveur de test**.
- Comment on branchera (plus tard) des automatismes sans les activer trop tôt en prod.

## Ensuite : 1.5.0 — Analyse et traitement des pièces jointes, approfondis

S’appuie sur la [1.1.2](../specs/v1.1.2-pieces-jointes.md) (pipeline d’extraction, une pièce jointe par message) et sur le premier **Agent** métier livré en 1.4.0. Deux limites actées volontairement en 1.1.2 sont à lever ici, pas avant : **plusieurs pièces jointes par message**, et un **traitement spécifique par pôle** (un agent Foncier ne traite pas un document comme un agent Urbanisme) — demande explicite du cabinet dès le grilling de 1.1.2, remise à plus tard faute d’Agent réel pour la justifier.

**Objectif.** Une pièce jointe mieux exploitée dans la durée d’une conversation (le contenu retrouvé reste fiable une fois hors de la fenêtre des derniers messages, cf. les essais fonctionnels 1.1.2) et mieux exploitée selon qui la reçoit (le pôle de l’Agent destinataire).

**Recherche.**

- Plusieurs pièces jointes par message : impact sur le schéma `PieceJointe` (déjà pensé pour ne pas bloquer ça), sur l’outil `obtenir_contenu_piece_jointe` (choisir parmi plusieurs plutôt qu’une seule hors fenêtre), sur le résumé glissant (une mention courte par pièce jointe, pas une agrégée).
- Traitement par pôle : qu’est-ce qui change concrètement pour un même format (PDF, image, …) selon le pôle de l’Agent qui le reçoit — nouveau prompt d’extraction, post-traitement dédié, ou simple différence de consigne à l’IA plutôt qu’un pipeline dupliqué.
- Fiabilité de l’analyse elle-même, au-delà de la plomberie : enseignements des essais fonctionnels 1.1.2 (ex. liens inventés entre pièces jointes sans preuve, confusions de vocabulaire métier propre à un document) qui ne relèvent ni de la fenêtre de 3 messages ni du profil de travail.
- Conservation d’une pièce jointe au-delà de sa conversation d’origine (usage multi-conversationnel, matière pour entraîner les futurs Agents) : piste évoquée dès le grilling 1.1.2, pas tranchée.

## Plus tard (pas encore numéroté)

### Agent IA de continuation du développement, validation par compte administrateur

Constat (grilling 1.2.0) : à terme, plus aucune personne qualifiée ne sera sur place pour faire évoluer le logiciel elle-même. L'évolution du code (nouvelles versions, corrections, nouveaux Agents métier) serait alors portée par un agent IA dédié à la continuation du développement, avec un compte administrateur qui ne fait que **valider** (approuver/refuser) les changements proposés, sans avoir à coder ni à relire le code en détail.

Implications déjà identifiées à creuser plus tard :
- Cette contrainte pèse sur les choix techniques pris dès 1.2.0 (ex. TypeScript plutôt que JS nu, pour donner un filet de sécurité à la compilation en l'absence de relecture humaine technique).
- Reste à définir : à quoi ressemble concrètement le flux de validation (où/comment un compte administrateur voit et approuve un changement), le périmètre de ce que l'agent peut faire seul vs ce qui nécessite une validation, et les garde-fous (rollback, tests obligatoires avant validation, etc.).
- Tests front (grilling 1.2.0) : pas de tests dédiés côté UI React en 1.2.0 (on reste sur les tests pytest HTTP-boundary existants + validation visuelle par l'admin). À une version pas encore numérotée : ajouter un filet de sécurité automatisé côté UI (ex. Playwright) puisque seul un agent IA maintient ce code sans relecture humaine technique — pertinent surtout quand le volume d'écrans aura grossi (1.3.0, 1.4.0, 1.5.0 et au-delà).

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
- RAG sur un corpus cabinet, distinct des pièces jointes du fil courant (1.1.2 / 1.5.0).

### Éléments de réponse visuels plus riches dans le chat (graphiques, documents générés)

Constat (grilling 1.2.2) : au-delà du Markdown borné (gras, listes) posé en 1.2.2, le cabinet a exprimé l'envie qu'une réponse de l'IA puisse à terme intégrer des éléments plus riches — graphiques, voire génération de documents (façon Word/Excel, à la manière de ce que proposent certains assistants IA) — plutôt que de la prose seule.

Pas de travail dédié avant que le besoin se confirme. Le rendu posé en 1.2.2 (`react-markdown` + mapping de composants React par élément Markdown) est délibérément choisi pour rendre cette extension simple le moment venu : ajouter un nouveau type de bloc revient à enregistrer un composant supplémentaire dans ce mapping, sans reprendre l'architecture du rendu.
