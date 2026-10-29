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
- **1.4.3** — Cache des pages web entre conversations ([#153](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/153), [spec](../../specs/v1.4.3-cache-des-pages-web.md), [ADR-0015](../../adr/0015-cache-commun-des-pages-web.md)) : une page lue avec succès est gardée 24 h, clé = URL exacte, partagée entre tous les comptes (texte et titre seulement) ; chaque conversation garde sa photo datée ; une page sans texte est retentée au tour suivant ; relecture forcée quand le collaborateur dit que la page a changé, questions déjà couvertes revérifiées ; en échec, l’ancienne version datée reste et l’IA le dit ; script de purge des lignes expirées, prêt pour une crontab (branchée au déploiement de la VM, **1.6.1**). Pas de changement du contrat HTTP du poste.
- **1.4.4** — Statut d’attente dynamique pendant une réponse ([#163](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/163), [spec](../../specs/v1.4.4-statut-attente-dynamique.md), [ADR-0016](../../adr/0016-envoi-de-message-en-flux-sse.md)) : pendant un tour, le fil affiche l’étape en cours publiée par la VM (« Réflexion… », « Recherche sur le web : “…” », « Lecture de <domaine> », « Relecture de <fichier> », « Vérification de la réponse… », « Titre de la conversation… »), une à la fois, jamais persistée ; les deux envois de message répondent en flux SSE (`statut` / `fin` / `erreur`) de la VM au navigateur, relayé tel quel par le poste ; le tour s’exécute dans un thread et va au bout même si le flux est coupé ; rejeu idempotent = flux avec le seul `fin` en cache ; la bascule de conversation suit la sélection (envoi en cours et brouillon tenus par conversation, indicateur de chargement dans la sidebar, bug [#169](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/169) corrigé) ; envoi possible dans une autre conversation pendant un tour, mis en attente du verrou du compte avec le statut « En attente de la réponse en cours dans une autre conversation… ». Contrat HTTP du poste : `POST /conversations` et `POST /conversations/{id}/messages` en `text/event-stream`.
- **1.5.0** — Lire Moduléo depuis le chat ([#171](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/171), [spec](../../specs/v1.5.0-lire-moduleo-depuis-le-chat.md), [ADR-0017](../../adr/0017-lecture-moduleo-par-outil.md)) : deux outils communs à tous les comptes, `chercher_affaires_moduleo` et `chercher_contacts_moduleo`, proposés dès que la config Moduléo est présente (statut « Consultation Moduléo ») ; le modèle donne des noms, la VM les résout en ids et renvoie des fiches denses en noms (5 par défaut, 10 au plus), affaires récentes (90 jours) sans critère ; client HTTP en lecture seule limité aux routes GET du WADL du cabinet, doc Moduléo copiée en local avec un script de mise à jour ; une seule clé d’API et le SecurityCode d’un utilisateur de test, chiffrés (Fernet), jamais envoyés au modèle ni visibles dans l’inspecteur ; chaque fiche enregistrée dans `lectures_outils`, source des garde-fous sur toute la conversation (« Sources : Moduléo, affaire … »), questions couvertes générées par script dans la Mémoire de la conversation ; panne ou refus Moduléo dit en une phrase fixe, détail dans l’inspecteur ; corrections des tests humains (garde-fou chiffres et date du jour, phrase fixe Moduléo, titrage, note système après une réponse remplacée, garde-fou `contact_non_lu`). Pas de changement du contrat HTTP du poste.
- **1.5.1** — Lire plus de données Moduléo depuis le chat ([#185](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/185), [spec](../../specs/v1.5.1-lire-plus-de-donnees-moduleo.md), [ADR-0018](../../adr/0018-droits-moduleo-appliques-par-bbass.md)) : quatre outils de lecture, un par domaine — `chercher_devis_moduleo`, `chercher_factures_moduleo` (reste à payer quand Moduléo le permet), `chercher_temps_passes_moduleo`, `chercher_planning_moduleo` — et les parcelles d’une seule affaire à la demande (`avec_parcelles`, propriétaires compris) ; totaux (nombre, HT / TTC, reste à payer, heures par collaborateur et par code activité) calculés par la VM sur tout l’ensemble trouvé ; période par défaut toujours annoncée ; activités et codes activité lus dans Moduléo ; statut « Consultation Moduléo : <domaine> » ; « mes temps » / « mon planning » filtrés sur l’utilisateur Moduléo lié au compte, planning d’une seule personne détaillé en entier (60 tâches au plus) ; « cette semaine » / « la semaine dernière » du lundi au dimanche. Droits Moduléo appliqués par BBASS : groupes Cogeo et Planning recopiés (catalogue et groupe Admin versionnés, rattachement des comptes par script), outils proposés seulement aux comptes rattachés à un groupe qui a le droit, garde fermé par défaut dans le client (`lire(route, paramètres, droits)`, chaque route GET classée, route non classée refusée), champs retirés par sous-droit, phrase fixe quand un droit manque. `MISTRAL_API_KEY` remplacée par `MISTRAL_API_KEY_CHIFFREE` (Fernet, même clé maître que Moduléo) : la VM refuse de démarrer sans clé utilisable. Essai réel sur le serveur du cabinet (#194) : filtres de date en JJ/MM/AAAA. Pas de changement du contrat HTTP du poste.

## Prochaine : 1.5.2 — Écrire dans Moduléo depuis le chat

**Contexte.** Kipaware (Vincent Mourareau, développement) a ouvert un **serveur Moduléo dédié aux tests**. Accès prévu via le **Client Moduléo Windows** et l’**API Moduléo**.

- **Client Windows** : installateur [SetupModuleo_TestAPI.zip](https://download.kipaware.fr/moduleo/client/setup/demo/SetupModuleo_TestAPI.zip) ; à la première utilisation, saisir le **numéro de série** attribué personnellement par Kipaware (**ne pas le communiquer** — hors dépôt / hors feuille) ; **identifiant et mot de passe** de connexion envoyés dans un e-mail séparé (droits étendus) ; le Client se connecte au serveur en **HTTPS sur le port 5304**.
- **API** : documentation [support Kipaware — API Moduléo](https://support.kipaware.fr/categories-moduleo/api-moduleo/) et [documentation interactive](https://mwa-kpw-api.kipaware.fr/api/documentation) ; **URL de connexion** et **clé d’API** à récupérer **une fois connecté au Client Windows** (détail dans le premier lien de doc).
- **Données** : compte utilisateur **pseudonymisé** ; ne saisir que des données **anonymisées ou fictives**.
- **Aide** : équipe de développement Kipaware — `developpement@kipaware.fr` ; [support.kipaware.fr](https://support.kipaware.fr/) ; [vidéos YouTube Kipaware](https://www.youtube.com/user/kipaware/videos).

**Objectif.** Premiers outils d’**écriture** Moduléo depuis le chat, essayés **uniquement** sur ce serveur de test. Une **seule clé d’API**, avec les droits d’écriture (plus puissante que la clé de lecture de la 1.5.0), dans la config de la VM, chiffrée comme en 1.5.0. Le collaborateur confirme explicitement chaque écriture avant qu’elle parte.

**À trancher au grilling.** Quelles écritures (laissé ouvert). Sécurité : confirmation, journal des écritures, client qui n’autorise que les routes d’écriture retenues. Écriture ouverte à tous les comptes ou réservée à certains (lien avec les Agents par pôle, **Plus tard**). Comment brancher BBASS sur ce serveur de test sans mélanger avec la lecture prod de la 1.5.0 / 1.5.1.

**Hors périmètre.** Écriture sur le serveur de **production** tant que les essais sur le serveur de test ne sont pas validés. Administration des groupes et droits Moduléo (→ **1.5.3**).

## Ensuite : 1.5.3 — Administration des groupes et droits Moduléo depuis le Panel d’administration

**Objectif.** Le compte administrateur gère depuis le Panel d’administration, dans une partie Moduléo, la copie des **groupes Cogeo et Planning** et de leurs **droits** introduite en 1.5.1 ([ADR-0018](../../adr/0018-droits-moduleo-appliques-par-bbass.md)) : créer un groupe, cocher ses droits comme dans Moduléo, le mettre à jour quand Moduléo change, et **rattacher chaque compte** à son groupe Cogeo, à son groupe Planning et à son utilisateur Moduléo. Remplace le fichier versionné et le script de la 1.5.1.

**À trancher au grilling.** Présentation du catalogue (catégories, sous-droits, conditions du Planning). Journal des changements de droits. Aide pour repérer une copie qui a dérivé de Moduléo.

**Hors périmètre.** Une clé d’API par collaborateur (→ **Plus tard**). Restriction d’accès par affaire (→ **Plus tard**). Agents par pôle (→ **Plus tard**).

## Ensuite : 1.6.0 — Versions vérifiées et prêtes à livrer

*(Anciennement un seul bloc « déploiement postes » 1.6.0 — découpé en **1.6.0** / **1.6.1** / **1.6.2**. La doc mémoire / souveraineté reste en **1.7.0** / **1.7.1**.)*

**Contexte.** Avant de pouvoir mettre à jour la VM ou installer les postes sans l’alternant, chaque version doit produire une **même référence** claire, vérifiée, prête à être reprise par le déploiement.

**Objectif.** Chaque version produit un livrable **testé et versionné**, sans dépendre d’un build ou d’une validation faits à la main sur le poste de l’alternant. Le cabinet (ou le prochain déploiement) part toujours de cette référence.

**Hors périmètre.** Mise à jour de la VM Castries (→ **1.6.1**). Installation et mise à jour des postes collab (→ **1.6.2**). Choix d’outillage (pipeline, artefacts, etc.) — **à trancher au grilling**.

## Ensuite : 1.6.1 — Mise à jour de la VM Castries sans l’alternant

**Objectif.** La machine centrale se **déploie et se met à jour** de façon **reproductible**, y compris ce qui doit tourner en continu (services, maintenance type purge du cache des pages web préparée en 1.4.3, secrets Moduléo en production hors du dépôt). Un admin cabinet peut le faire **sans cloner le dépôt** ni connaître la plomberie de développement.

**Hors périmètre.** Chaîne de vérification des livrables (→ **1.6.0**, déjà faite). Installation / mise à jour des postes (→ **1.6.2**). Détail technique (conteneurs, chemins secrets, etc.) — **à trancher au grilling**.

## Ensuite : 1.6.2 — Installer et mettre à jour le poste (installateur, fenêtre, accès web)

**Objectif.** Un collaborateur (ou un admin) **installe ou met à jour** le logiciel poste **sans git**, via un **installateur propre**. Une fois lancé : une **fenêtre propre** pour travailler ; le logiciel **reste disponible en fond** si on ferme la fenêtre (comme Docker Desktop qui continue après fermeture de sa fenêtre) ; on peut aussi l’**ouvrir depuis le navigateur** (raccourci possible). Le backend local obligatoire démarre, le lien vers la VM Castries est configuré, le chat est utilisable. Doc courte collab / admin.

**Hors périmètre.** Comment la VM se met à jour (→ **1.6.1**). Comment les livrables sont produits et vérifiés (→ **1.6.0**). Choix techniques d’embarquer la fenêtre ou le raccourci — **à trancher au grilling**.

## Ensuite : 1.7.0 — Documentation fonctionnelle : mémoire et souveraineté des données

*(Reprise du bloc Plus tard « Documentation : mémoire conversationnelle et souveraineté des données (ex-1.6.0) », élargi en série 1.7.x de documentation fonctionnelle.)*

**Objectif.** Le cabinet dispose d’un **wiki produit** consultable par des non-techniciens (partie **fonctionnelle** du doc-site) : d’abord une **convention courte** de format (structure type : objectif, schémas, tableaux « où vit / qui voit / ce qui sort », sans dump de code) qui servira de modèle aux documentations suivantes ; puis deux documents dans `docs/features/` **et** sur le site de doc, chacun porté par une issue GitHub labellee **`documentation`** (plan, schémas, captures, exemples). Pas de changement de code produit hors ajustements de doc / schémas / exemples de tests cités.

1. **Persistance de la mémoire** (`docs/features/memoire-conversationnelle.md` ou équivalent). Schéma compréhensible (conversations, messages, résumé glissant, profil de travail, pièces jointes, résultats de recherche web, etc.), flux tour par tour (ce qui entre, ce qui sort de la fenêtre de 3, ce qui est plafonné, ce que le modèle relit via outils), choix déjà pris et **pourquoi** (persistance VM vs API Conversations Mistral, séparation identité / profil, etc.). Exemples concrets (inspecteur, états) et renvois aux tests HTTP-boundary en annexe courte. Inclut la Mémoire de la conversation et les questions couvertes (1.4.1), le cache des pages web (1.4.3).

2. **Souveraineté des données** (`docs/features/souverainete-des-donnees.md` ou équivalent). Cartographie de tous les choix qui font que **seul le cabinet** détient les données persistées : Postgres et fichiers sur la VM Castries, SearXNG auto-hébergé, pas de Files API / Conversations Mistral, ZDR / `chat/completions` sans rétention côté modèle, clé API unique derrière la VM, LAN uniquement, etc. Expliquer **pourquoi** chaque décision rend le cabinet souverain. **Carte globale** « où vit la donnée » et **ce qui quitte le cabinet** (Mistral, Moduléo, SearXNG, rien d’autre) pour les chemins critiques ; liens ADR / specs. Le détail *par outil* de ce qui part / revient est en **1.7.1**.

**Hors périmètre.** Inventaire des outils du modèle et flux par outil (→ **1.7.1**). Doc détaillée du tool calling recherche web (→ **Optimisation de la recherche web**, Plus tard). Doc-site administration des groupes et droits Moduléo (reste **hors version**). Déploiement (→ **1.6.0** / **1.6.1** / **1.6.2**), n8n (→ **1.8.0**), Agents par pôle, bugs connus. Implémentation de nouvelles capacités mémoire ou cache.

## Ensuite : 1.7.1 — Documentation fonctionnelle : outils du modèle et flux par outil

**Objectif.** Suite du wiki fonctionnel (même convention que la **1.7.0**) : un document (ou un ensemble de pages liées) qui inventorie **tous les outils** exposés au modèle — recherche web, relecture de pièces jointes / pages, Moduléo, etc. Pour chaque outil : à quoi il sert, paramètres utiles en langage produit, **ce qu’il envoie / reçoit / persiste**, ce qui reste sur la VM, lien avec l’inspecteur. Complète la carte souveraineté de la 1.7.0 **sans la réécrire**. Issue(s) GitHub **`documentation`** ; pages sur le doc-site partie fonctionnelle. Pas de changement de code produit hors doc / schémas / exemples.

**Hors périmètre.** Doc ultra-détaillée du tool calling recherche web (paramètres fins, tous les cheminements d’échec) — reste le livrable doc de **Optimisation de la recherche web** (Plus tard). Nouveaux outils, Agents par pôle, n8n (**1.8.0**), écriture Moduléo (**1.5.2**).

## Ensuite : 1.8.0 — Workflows n8n (socle d’automatisation), branchés sur Moduléo 1.5.0

*(Anciennement 1.6.0 / 1.7.0 — passé en 1.8.0 ; le créneau 1.7.x est repris par la documentation fonctionnelle.)*

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

*(Anciennement 1.5.0 → 1.8.0 selon les décalages ; reste en 1.9.0. La documentation fonctionnelle est en **1.7.0** / **1.7.1**.)*

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

### Bug — heure de l'inspecteur, titre de carte en jargon et confirmation en texte avant la carte (#256)

**Constat :** trois défauts mineurs du premier passage des tests humains V1.5.2 (#206) : l'inspecteur affiche les heures une heure en retard (11:07 pour 12:07, heure de Paris) ; la carte d'écriture reprend la description de la route de la doc Moduléo (« Met à jour une tâche à faire en fonction de son identifiant unique. ») ; le modèle demande souvent une confirmation en texte avant de proposer la carte.

**Reproductibilité :** comparer une heure de l'inspecteur à l'heure locale ; lire le titre d'une carte de modification de tâche à faire ; demander la création d'une tâche à faire sans « propose directement la carte » (question en texte 3 fois sur 8 au premier passage).

**Impact :** lecture moins claire (heure fausse, titre technique) et un tour de chat de plus avant de pouvoir confirmer ; aucune écriture fausse.

**Cause probable :** heures en UTC affichées sans conversion ; titre de carte = description de la route ; consigne système « pose la question de confirmation » qui prend le pas sur la carte.

**À corriger :** heures de l'inspecteur en heure de Paris, lisibles par un humain (« 29 octobre 2026 à 12:07 », pas un format technique), et même règle pour les dates de la carte (« 15 novembre 2026 » au lieu de « 2026-11-15T00:00:00+01:00 ») ; titre de carte en langage métier ; carte proposée directement quand la demande d'écriture est claire.

**Hors périmètre :** fausses cartes et écritures annoncées sans carte (#252) ; ids non résolus et phrase coupée (#254) ; refonte du style de la carte (Agents par pôle).

**Suivi :** [#256](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/256) (`bug`, captures en pièce jointe). Trouvé dans : 1.5.2 · Contexte : test humain · Date : 2026-10-29 · Priorité : non prioritaire en dev.

### Agent IA de continuation du développement, validation par compte administrateur

Constat (grilling 1.2.0) : à terme, plus aucune personne qualifiée ne sera sur place pour faire évoluer le logiciel elle-même. L'évolution du code (nouvelles versions, corrections, nouveaux Agents métier) serait alors portée par un agent IA dédié à la continuation du développement, avec un compte administrateur qui ne fait que **valider** (approuver/refuser) les changements proposés, sans avoir à coder ni à relire le code en détail.

Implications déjà identifiées à creuser plus tard :
- Cette contrainte pèse sur les choix techniques pris dès 1.2.0 (ex. TypeScript plutôt que JS nu, pour donner un filet de sécurité à la compilation en l'absence de relecture humaine technique).
- Reste à définir : à quoi ressemble concrètement le flux de validation (où/comment un compte administrateur voit et approuve un changement), le périmètre de ce que l'agent peut faire seul vs ce qui nécessite une validation, et les garde-fous (rollback, tests obligatoires avant validation, etc.).
- Tests front (grilling 1.2.0) : pas de tests dédiés côté UI React en 1.2.0 (on reste sur les tests pytest HTTP-boundary existants + validation visuelle par l'admin). À une version pas encore numérotée : ajouter un filet de sécurité automatisé côté UI (ex. Playwright) puisque seul un agent IA maintient ce code sans relecture humaine technique — pertinent surtout quand le volume d'écrans aura grossi (1.3.0, 1.4.0, 1.5.0, 1.6.0, 1.7.0, 1.8.0, 1.9.0 et au-delà).

### Lanceur poste (exécutable, fenêtre + accès web)

→ **Repris et numéroté en 1.6.2** (installateur propre, fenêtre propre, logiciel en fond après fermeture de la fenêtre, ouverture possible depuis le navigateur / raccourci). Cette entrée « Plus tard » ne fait plus office de file d’attente séparée.

### Déploiement, livrables, retours utilisateurs

→ **Repris et numéroté en 1.6.0** (versions vérifiées et prêtes à livrer), **1.6.1** (mise à jour VM Castries) et **1.6.2** (installateur postes). Contraintes déjà vues à réintégrer dans la spec à l’ouverture de chaque version : pas forcément de VM centrale physique pour déployer le relais ; LAN Castries vs Internet ; pilote sur quelques machines ; fin du build front fait uniquement à la main.

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

### Une clé d’API Moduléo par collaborateur

Constat (grilling 1.5.1) : les droits de la clé d’API Moduléo font foi sur ceux des groupes utilisateur ; BBASS garde donc une seule clé de lecture et applique lui-même les droits recopiés ([ADR-0018](../../adr/0018-droits-moduleo-appliques-par-bbass.md)). Une clé par collaborateur, réglée dans Moduléo, serait plus sûre (une fuite de la VM ne livrerait pas tout) mais lourde à administrer. **Déclencheur** : Kipaware fait primer les droits des groupes sur ceux de la clé, ou le risque d’une clé unique devient inacceptable (écriture, 1.5.2).

### Restriction d’accès Moduléo par affaire

Constat (grilling 1.5.1) : Moduléo peut limiter l’accès à certaines affaires (« Limiter l’accès à des affaires aux autres collaborateurs », groupes rattachés à une affaire). La copie des droits de la 1.5.1 ne s’applique qu’aux catégories, pas affaire par affaire. Piste : lire les groupes de chaque affaire trouvée et filtrer les fiches dans le garde des droits.

### Serveur MCP Moduléo

Constat (spec 1.5.2, tests humains [#206](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/206)) : BBASS parle à Moduléo par des outils écrits dans la VM (lecture typée, puis `decrire_ecriture_moduleo` / `ecrire_moduleo` génériques). L’API de Kipaware ne lit certains éléments que par leur id, sans liste ni recherche par nom (catégories de tâche à faire `moduleo/categorietacheafaire/{id}`, de note `cogeo/categorienote/{id}`) : depuis la 1.5.2, le modèle dit au collaborateur qu’il ne peut pas retrouver « Terrain » à partir de son nom, au lieu de deviner un id.

**Objectif.** Un serveur MCP (Model Context Protocol) Moduléo expose aux modèles, de façon standard, les lectures et les écritures Moduléo de BBASS, et ajoute ce qui manque au chat : retrouver par son nom un élément que l’API ne lit que par id (catégories de tâche à faire, de note…), en construisant la correspondance nom → id (lecture des ids un à un, mise en cache) faute de route de liste, ou par une route de liste si Kipaware en ouvre une. Les garanties de la 1.5.2 restent : garde des droits, carte de confirmation, serveur de test seulement pour l’écriture, ids jamais à l’écran.

**Prise en main** (premier serveur MCP du projet) : partir de l’introduction officielle [modelcontextprotocol.io — Getting started](https://modelcontextprotocol.io/docs/2026-07-28/getting-started/intro), puis ses pages « Architecture » (concepts : hôte, client, serveur), « Build servers » (construire un serveur ; choisir le SDK Python) et « Security » (bonnes pratiques). Prévoir une recherche dans `docs/dev/recherches/` avant d’ouvrir la version : où tourne le serveur (dans la VM centrale ou à côté), transport, et ce qui remplace ou enveloppe les outils actuels.

**Hors périmètre.** Écriture sur le serveur Moduléo du cabinet (décision à part) ; ouvrir le serveur MCP à des clients hors BBASS ; demander à Kipaware une route de liste (démarche à mener en parallèle, sans bloquer).

### Doc-site : administration des groupes et droits Moduléo (hors version)

Constat (grilling 1.5.1) : une page `features/moduleo` du site de documentation rappelle comment les droits Moduléo s’appliquent dans BBASS : groupes Cogeo et Planning, catalogue des droits, rattachement des comptes, mise à jour quand Moduléo change. Rédigée hors version par le développeur.

### Vérification de la fiabilité des sources web

Constat (essais manuels 1.4.0) : `rechercher_web` ramène des pages et l’IA les cite ; rien ne dit encore si une source est digne de confiance (site officiel, presse, blog, forum, page commerciale). Une amélioration ultérieure de la recherche web ferait **évaluer la fiabilité des sites sourcés** avant ou avec la réponse : indiquer au collaborateur le degré de confiance, écarter ou rétrograder les sources douteuses, et garder une trace lisible (inspecteur ou mention courte).

Pistes à trancher à l’ouverture : critères (domaine `.gouv.fr` / institutionnel, liste blanche cabinet, score heuristique, second passage modèle…), moment du contrôle (à la réception des résultats, après lecture des pages, à la rédaction), ce que voit le collaborateur, et le lien avec les garde-fous URL déjà en place. S’appuie sur la 1.4.0 et le registre d’outils. Distinct de l’optimisation **par défaut** (tokens / snippets) et des modes Rapide / Approfondi.

### Modes de réponse (Rapide / Approfondi) et outils de lecture plus fins

Constat (ouverture 1.4.0) : plusieurs façons d’utiliser les outils sont possibles selon l’effort voulu. Un mode choisi par le collaborateur réglerait le nombre de tours d’outils (voir « Le tool calling ne boucle pas »), le nombre de pages lues, le choix des pages par le modèle (s’appuie sur `lire_pages_web`, 1.4.1), un appel de synthèse, ou le modèle utilisé. Change le contrat HTTP du poste (choix du mode). Le découpage de la 1.4.0 (registre d’outils, appel d’extraction isolé, [ADR-0014](../../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)) est fait pour s’y brancher. Distinct de l’optimisation **par défaut** de la recherche web et de la **vérification de fiabilité des sources** (rubriques précédentes), qui ne demandent pas de choix utilisateur.

### Exécution de code dans le chat (cellules Python exécutables, façon ChatGPT)

Constat (validation manuelle de la coloration syntaxique, #95/#97) : au-delà de l'afficher correctement, le cabinet a comparé au comportement de ChatGPT qui permet d'exécuter directement une cellule de code Python dans la conversation et d'en voir le résultat.

Pas de travail avant que le besoin se confirme — portée très différente d'un ajustement de rendu : il faudrait un bac à sable d'exécution (isolation, limites CPU/mémoire/temps, pas d'accès réseau/fichiers du poste), une décision sur où il tourne (poste local vs VM centrale vs service tiers) et une revue sécurité dédiée avant d'exposer quoi que ce soit d'exécutable à une réponse de modèle. Distinct de #97 (habillage visuel des blocs de code), qui n'en dépend pas.
