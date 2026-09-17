# Feuille de route dev

Ordre des **prochaines versions** produit, plus les sujets encore sans numéro.

Ce n’est **pas** une spec (ça vient après « Ouvre la version »).

## Déjà livré

- **1.0.x** — Socle : comptes, connexion, chat, relais Mistral, session persistée (keyring), LAN Castries.
- **1.1.0** — Comptes administrateurs, multi-pôles, mot de passe généré / changement forcé, révocation, affichage pôle/agence dans le chat.
- **1.1.1** — Conversations persistées sur la VM (PostgreSQL) : plusieurs fils, reprise après rechargement / autre poste, historique borné (3 derniers messages + résumé glissant), profil de travail lecture seule ; pas de stockage Mistral Conversations.
- **1.1.2** — Pièces jointes : upload PDF/Word/Excel/image sur un message (une par message), extraction (OCR Mistral, locale pour Word/Excel, vision Mistral pour l'image), contenu injecté dans le chat, mention courte dans le résumé glissant, rappel via un outil si la pièce jointe sort de la fenêtre ; jamais la Files API Mistral.
- **1.1.3** — Consommation : une ligne `Consommation` par appel Mistral réel (chat, titrage, résumé+profil, OCR, vision), tokens ou pages selon le type, coût figé au tarif du jour de l'appel (pas d'API de tarification Mistral, tarifs en dur dans le code). Fenêtre Consommation côté collaborateur (total + classement des conversations par coût) ; onglet Consommations côté administrateur (comptes classés par coût, jamais de détail par conversation).

## Prochaine : 1.2.0 — Mise à jour de l’interface (poste)

Un peu de **style** et surtout le **minimum d’UX** : aujourd’hui l’écran comptes (compte administrateur) est encombré, pas de **modales**, tout s’empile. On vise une interface **simple** au début, pas forcément très stylisée.

**Recherche (le grilling tranchera).**

- Plugin Claude **`frontend-design`** (`frontend-design@claude-plugins-official`) : à tester / décider si on s’en sert pour cette version.
- Frameworks front existants : lesquels seraient adaptés à un HTML/JS déjà servi par le backend local, sans expérience préalable de framework. Possible aussi de rester en HTML/CSS/JS « nu » + composants minimaux (modales, layout).

## Ensuite : 1.3.0 — Premier Agent (pôle Administration), axé Moduléo

Premier **Agent** métier. Pôle **Administration**. Premier périmètre logiciel : **Moduléo** (utilisé par tout le cabinet), pas tout le métier d’un coup.

**Objectif.** Avancer **lentement** et le plus **sûrement** possible. Configurer l’Agent pour qu’il comprenne Moduléo et puisse, d’abord en **lecture** (pas d’écriture sur le serveur Moduléo) : s’appuyer sur la doc / l’API, récupérer de l’information. Les **automatismes** ne sont pas obligatoires dès le premier livrable : le modèle conversationnel doit déjà être capable de **pondre un plan d’implémentation** d’un automate Moduléo (comment on les générera / brancherait plus tard).

**Recherche / tests.**

- API Moduléo : ce qu’elle permet, limites, auth.
- Essais uniquement sur un **serveur de test**.
- Comment on branchera (plus tard) des automatismes sans les activer trop tôt en prod.

## Ensuite : 1.4.0 — Analyse et traitement des pièces jointes, approfondis

S’appuie sur la [1.1.2](../specs/v1.1.2-pieces-jointes.md) (pipeline d’extraction, une pièce jointe par message) et sur le premier **Agent** métier livré en 1.3.0. Deux limites actées volontairement en 1.1.2 sont à lever ici, pas avant : **plusieurs pièces jointes par message**, et un **traitement spécifique par pôle** (un agent Foncier ne traite pas un document comme un agent Urbanisme) — demande explicite du cabinet dès le grilling de 1.1.2, remise à plus tard faute d’Agent réel pour la justifier.

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
- Tests front (grilling 1.2.0) : pas de tests dédiés côté UI React en 1.2.0 (on reste sur les tests pytest HTTP-boundary existants + validation visuelle par l'admin). À une version pas encore numérotée : ajouter un filet de sécurité automatisé côté UI (ex. Playwright) puisque seul un agent IA maintient ce code sans relecture humaine technique — pertinent surtout quand le volume d'écrans aura grossi (1.3.0, 1.4.0 et au-delà).

### Lanceur poste (exécutable, pywebview)

Un exécutable qui ouvre une fenêtre (pages web du backend local). Fermer la fenêtre ne tuerait pas le process : accès encore possible dans le navigateur (`localhost` du poste).

Recherche : empaquetage Windows, icône / démarrage du backend, barre d’état vs process invisible, mise à jour.

### Déploiement, CI/CD, retours utilisateurs

Déployer pour avoir des retours. Automatiser depuis GitHub Actions / un hébergeur type Netlify.

Contraintes déjà vues : pas de VM centrale physique pour un CD du relais ; Netlify (Internet) vs poste local + LAN ; Actions pour pytest seulement ; pilote sur une machine en attendant.

Ajout (grilling 1.2.0) : depuis 1.2.0, le front `poste` passe par un build Vite/React — en attendant cette CI, le dossier compilé (`dist/`) est committé directement dans git (comme `static/` aujourd'hui), aucune étape de build sur le poste. Quand cette CI/CD sera mise en place, elle devra aussi prendre en charge le build du front (au lieu du commit direct du `dist/` compilé).
