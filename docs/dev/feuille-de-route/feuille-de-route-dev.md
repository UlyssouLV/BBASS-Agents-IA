# Feuille de route de dev

Ordre des **prochaines versions** produit, plus les sujets encore sans numéro.

Ce n’est **pas** une spec (ça vient après « Ouvre la version »).

**Numéro de développement, numéro produit.** Les numéros de ce fichier sont des numéros de **développement** : une série par numéro mineur (1.7.x documentation, 1.8.x cartographie des usages, 1.9.x Agents métier, 1.10.x serveur MCP Moduléo…), et deux séries peuvent arriver sur `main` en alternance. Le collaborateur ne voit que le **numéro produit** (tag de la Release, `/sante`, « À propos » du poste), toujours croissant. Règle : [README](https://github.com/UlyssouLV/BBASS-Agents-IA/blob/main/docs/dev/feuille-de-route/README.md#numéro-de-développement-et-numéro-produit).

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
- **1.4.3** — Cache des pages web entre conversations ([#153](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/153), [spec](../../specs/v1.4.3-cache-des-pages-web.md), [ADR-0015](../../adr/0015-cache-commun-des-pages-web.md)) : une page lue avec succès est gardée 24 h, clé = URL exacte, partagée entre tous les comptes (texte et titre seulement) ; chaque conversation garde sa photo datée ; une page sans texte est retentée au tour suivant ; relecture forcée quand le collaborateur dit que la page a changé, questions déjà couvertes revérifiées ; en échec, l’ancienne version datée reste et l’IA le dit ; purge des lignes expirées (timer systemd horaire, branché au déploiement de la VM, **1.6.1**). Pas de changement du contrat HTTP du poste.
- **1.4.4** — Statut d’attente dynamique pendant une réponse ([#163](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/163), [spec](../../specs/v1.4.4-statut-attente-dynamique.md), [ADR-0016](../../adr/0016-envoi-de-message-en-flux-sse.md)) : pendant un tour, le fil affiche l’étape en cours publiée par la VM (« Réflexion… », « Recherche sur le web : “…” », « Lecture de <domaine> », « Relecture de <fichier> », « Vérification de la réponse… », « Titre de la conversation… »), une à la fois, jamais persistée ; les deux envois de message répondent en flux SSE (`statut` / `fin` / `erreur`) de la VM au navigateur, relayé tel quel par le poste ; le tour s’exécute dans un thread et va au bout même si le flux est coupé ; rejeu idempotent = flux avec le seul `fin` en cache ; la bascule de conversation suit la sélection (envoi en cours et brouillon tenus par conversation, indicateur de chargement dans la sidebar, bug [#169](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/169) corrigé) ; envoi possible dans une autre conversation pendant un tour, mis en attente du verrou du compte avec le statut « En attente de la réponse en cours dans une autre conversation… ». Contrat HTTP du poste : `POST /conversations` et `POST /conversations/{id}/messages` en `text/event-stream`.
- **1.5.0** — Lire Moduléo depuis le chat ([#171](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/171), [spec](../../specs/v1.5.0-lire-moduleo-depuis-le-chat.md), [ADR-0017](../../adr/0017-lecture-moduleo-par-outil.md)) : deux outils communs à tous les comptes, `chercher_affaires_moduleo` et `chercher_contacts_moduleo`, proposés dès que la config Moduléo est présente (statut « Consultation Moduléo ») ; le modèle donne des noms, la VM les résout en ids et renvoie des fiches denses en noms (5 par défaut, 10 au plus), affaires récentes (90 jours) sans critère ; client HTTP en lecture seule limité aux routes GET du WADL du cabinet, doc Moduléo copiée en local avec un script de mise à jour ; une seule clé d’API et le SecurityCode d’un utilisateur de test, chiffrés (Fernet), jamais envoyés au modèle ni visibles dans l’inspecteur ; chaque fiche enregistrée dans `lectures_outils`, source des garde-fous sur toute la conversation (« Sources : Moduléo, affaire … »), questions couvertes générées par script dans la Mémoire de la conversation ; panne ou refus Moduléo dit en une phrase fixe, détail dans l’inspecteur ; corrections des tests humains (garde-fou chiffres et date du jour, phrase fixe Moduléo, titrage, note système après une réponse remplacée, garde-fou `contact_non_lu`). Pas de changement du contrat HTTP du poste.
- **1.5.1** — Lire plus de données Moduléo depuis le chat ([#185](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/185), [spec](../../specs/v1.5.1-lire-plus-de-donnees-moduleo.md), [ADR-0018](../../adr/0018-droits-moduleo-appliques-par-bbass.md)) : quatre outils de lecture, un par domaine — `chercher_devis_moduleo`, `chercher_factures_moduleo` (reste à payer quand Moduléo le permet), `chercher_temps_passes_moduleo`, `chercher_planning_moduleo` — et les parcelles d’une seule affaire à la demande (`avec_parcelles`, propriétaires compris) ; totaux (nombre, HT / TTC, reste à payer, heures par collaborateur et par code activité) calculés par la VM sur tout l’ensemble trouvé ; période par défaut toujours annoncée ; activités et codes activité lus dans Moduléo ; statut « Consultation Moduléo : <domaine> » ; « mes temps » / « mon planning » filtrés sur l’utilisateur Moduléo lié au compte, planning d’une seule personne détaillé en entier (60 tâches au plus) ; « cette semaine » / « la semaine dernière » du lundi au dimanche. Droits Moduléo appliqués par BBASS : groupes Cogeo et Planning recopiés (catalogue et groupe Admin versionnés, rattachement des comptes par script), outils proposés seulement aux comptes rattachés à un groupe qui a le droit, garde fermé par défaut dans le client (`lire(route, paramètres, droits)`, chaque route GET classée, route non classée refusée), champs retirés par sous-droit, phrase fixe quand un droit manque. `MISTRAL_API_KEY` remplacée par `MISTRAL_API_KEY_CHIFFREE` (Fernet, même clé maître que Moduléo) : la VM refuse de démarrer sans clé utilisable. Essai réel sur le serveur du cabinet (#194) : filtres de date en JJ/MM/AAAA. Pas de changement du contrat HTTP du poste.
- **1.5.3** — Administration des groupes et droits Moduléo depuis le Panel d’administration ([#209](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/209), [spec](../../specs/v1.5.3-administration-groupes-droits-moduleo-panel.md), [ADR-0019](../../adr/0019-groupes-moduleo-administres-en-base.md)) : nouvel onglet **Outils** → **Moduléo** du Panel, réservé aux comptes administrateurs ; groupes Cogeo et Planning créés, renommés, droits cochés dans une arborescence façon Moduléo (conditions Planning : participation, activité, créateur), suppression refusée tant qu’un compte y est rattaché ; rattachement de chaque compte à son groupe Cogeo, son groupe Planning et son utilisateur Moduléo (recherche par nom) ; journal minimal des droits Moduléo (date, admin, action, cible), sans export. Cases et groupes vivent en base : `catalogue.json` ne sert plus qu’à une migration unique, le démarrage ne le relit plus (groupe Admin semé seulement si aucun groupe) ; catalogue des cases en lecture seule ; groupe « Tous droits (dev) » hors Panel ; `affecter_groupes_moduleo.py` réservé au poste de dev. Un changement vaut dès le tour de chat suivant. Livrée avant la 1.5.2, en parallèle depuis `main`. Pas de changement du contrat HTTP du chat.
- **1.6.0** — CI : versions vérifiées et prêtes à livrer ([#216](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/216), [spec](../../specs/v1.6.0-ci-versions-verifiees.md), [ADR-0020](../../adr/0020-ci-argos-compartimentee.md)) : CI GitHub Actions compartimentée façon ArgOS, un workflow par compartiment — `tests-vm-centrale`, `tests-poste`, `build-front` (build Vite + contrôle de dérive du dist committé, [ADR-0010](../../adr/0010-front-poste-react-typescript-vite.md) inchangé), `build-docs` (build Docusaurus sur PR, sans déploiement), Sonar lancé en premier en analyse CI-only sans attendre la couverture ; path filters avec skip→vert ; ruleset `main` : squash-merge seul + checks requis ; `deploy-docs.yml` réduit au build + GitHub Pages, plus aucun commit `github-actions[bot]` sur `main` après « Finalise la version » (aperçus README produits sur la branche de version, dans le squash). Référence d’une version = tag + GitHub Release. Livrée avant la 1.5.2, en parallèle depuis `main`. Pas de changement du code produit ni du contrat HTTP.
- **1.6.1** — CD : packaging, conteneurs et mise à jour de la VM Castries sans l’alternant ([#229](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/229), [spec](../../specs/v1.6.1-cd-vm-castries.md), [ADR-0021](../../adr/0021-cd-vm-centrale-staging-prod.md)) : VM centrale livrée en conteneurs sur une VM Ubuntu Server 26.04 LTS + Docker Compose, sans cloner le dépôt ; images `vm-centrale` et `searxng` construites à chaque Release et publiques sur GHCR (aucun secret dedans), nouveau check CI `build-image-vm` (stack démarrée, `/sante` 200) ; deux Environnements séparés sur la même VM, **staging** (port 8001, serveur de test Kipaware) et **prod** (port 8000), Postgres et SearXNG sur le réseau Docker interne, pas de HTTPS (LAN) ; une Release pose l’étiquette `staging`, le workflow manuel « Promouvoir en prod » pose `prod` sur les mêmes images sans rebuild, refusé pour une version jamais passée en staging ; installation en une commande par Environnement (secrets générés et affichés une fois, clés Mistral et Moduléo saisies en clair et chiffrées par l’installateur, premier compte administrateur par `creer-admin`) ; mise à jour par `mettre-a-jour <env>` ou au redémarrage (service systemd), sauvegarde `pg_dump` avant changement de version, retour aux images précédentes si `/sante` échoue, démarrage sur les images présentes sans Internet, refus de GHCR distingué d’une coupure réseau ; fichiers de déploiement embarqués dans l’image, `.env` jamais écrasé ; convention unique des tâches planifiées (`taches-planifiees.conf`, timers systemd), purge horaire du cache des pages web (1.4.3) branchée ; guide admin sur le site de doc. Livrée avant la 1.5.2, en parallèle depuis `main`. Dev (`lancer-vm.*`) inchangé ; pas de changement du contrat HTTP du poste.
- **1.6.2** — Installateur et mise à jour automatique des postes ([#238](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/238), [spec](../../specs/v1.6.2-installateur-mise-a-jour-postes.md), [ADR-0022](../../adr/0022-poste-application-windows-version-dictee-par-la-vm.md)) : le poste devient une application Windows 10/11 x64 sans git, Python ni Docker ; Lanceur Rust / Tauri v2 (fenêtre WebView2, icône et titre BBASS) autour du backend poste Python inchangé, figé par PyInstaller ; `BBASS-Setup-vX.Y.Z.exe` joint à chaque Release, installateur maison en quatre étapes (Bienvenue, Serveur BBASS avec pastille de test, Options, Installation), par utilisateur et sans droits administrateur dans `%LOCALAPPDATA%\BBASS`, raccourcis et entrée de désinstallation `HKCU`, désinstallation qui garde la configuration ; à chaque lancement le poste se met à la version du Serveur BBASS (`/sante`) : Paquet poste signé ed25519 téléchargé depuis la Release, une version précédente gardée, retour arrière automatique si la nouvelle ne démarre pas, démarrage sur la version installée avec bandeau si la VM ou Internet manque ; zone de notification (Ouvrir BBASS, Ouvrir dans le navigateur sur `http://127.0.0.1:8100`, Quitter), instance unique, démarrage avec Windows en fond ; écran de connexion revu en deux panneaux avec pastille d’état et menu « … » (Configuration du Serveur BBASS sans réinstaller, dossier de configuration, À propos, « Vérifier les mises à jour maintenant ») ; guides collaborateur et admin sur le site de doc (menu Exploitation). Tests humains (#247) joués après la publication de la Release, puisque le Setup n’existe qu’une fois la Release publiée. Livrée avant la 1.5.2, en parallèle depuis `main`. Dev (`lancer-logiciel.*`) inchangé.
- **1.5.2** — Écrire dans Moduléo depuis le chat ([#201](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/201), [spec](../../specs/v1.5.2-ecrire-dans-moduleo-depuis-le-chat.md), [ADR-0023](../../adr/0023-ecriture-moduleo-confirmee-serveur-de-test.md)) : deux outils génériques, `decrire_ecriture_moduleo` et `ecrire_moduleo` ; le modèle propose, le collaborateur confirme chaque écriture sur une Carte de confirmation en noms (ce qui change champ par champ pour une modification, fiche « Sera supprimé » pour une suppression), boutons traités par la VM, hors du modèle ; un « oui » tapé ne confirme rien, la carte expire au message suivant. Droits Moduléo appliqués à l’écriture, journal des écritures, id dans les fiches pour le modèle et retiré de la réponse affichée, écriture annoncée en texte sans carte relancée puis remplacée par une phrase fixe, refus de droit montré tel quel. Écriture réservée au serveur de test : staging (port 8001) et poste de dev, jamais la prod (port 8000), par `BBASS_ENVIRONNEMENT`. Cibles de dev `test` et `cabinet` (`lancer-vm.bat` / `lancer-logiciel.bat [test|cabinet]`, `.env.test` / `.env.cabinet`), Paquet poste construit depuis `poste/uv.lock`. [#256](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/256) corrigé. Périmètre réduit après trois passages de tests humains ([#206](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/206)) : limites reportées en **1.10.1** et **1.10.2**. Bugs connus livrés avec la version, reportés en **Plus tard** : [#263](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/263), [#264](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/264). Livrée en **1.6.3**.
- **1.6.3** — Corriger les bugs existants ([#266](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/266), [spec](../../specs/v1.6.3-corriger-les-bugs-existants.md), [ADR-0024](../../adr/0024-relecture-isolee-apres-garde-fou.md)) : la déconnexion vide toute la mémoire du compte sur le poste ; supprimer un compte supprime ses données, sa consommation reste sous « Compte supprimé », et un nettoyage unique reprend celles des comptes déjà supprimés ; sans source, l’IA dit ce qu’elle n’a pas trouvé (consigne, date en toutes lettres, bornes de la semaine prochaine données par le code, pages quasi vides écartées, marqueur « [non trouvé] », phrase fixe, relecture isolée après un retrait de garde-fou) ; la réponse est mise en forme pendant l’animation de frappe ; le bandeau de mise à jour pousse le contenu au lieu de recouvrir le bouton **…**. Embarque aussi la séparation numéro de développement / numéro produit et la planification des séries 1.7.x et 1.10.x. Livrée en **1.6.4**.

## Prochaine : 1.6.4 — Corriger les bugs constatés après la 1.6.3

**Objectif.** Les trois problèmes trouvés à l’usage juste après la finalisation de la 1.6.3 sont corrigés, pour que le poste installé fasse ce que les dernières versions annoncent :

- **Le poste se met à la version du serveur** ([#277](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/277)) : « Vérifier les mises à jour maintenant » vérifie à chaque clic et rouvre BBASS sur le résultat, sans jamais le laisser fermé ; la mise à jour aboutit sur un poste équipé d’un antivirus, sans intervention du collaborateur ; après l’enregistrement d’une nouvelle adresse de serveur, le poste propose de redémarrer pour se mettre à la version de ce serveur ; le tout début du lanceur est journalisé pour qu’un échec se voie.
- **Une conversation de l’ancien Environnement ne reste plus visible** ([#278](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/278)) : après un changement de serveur, le poste ne montre que les conversations du serveur auquel il est relié.
- **L’écriture Moduléo fonctionne depuis un poste installé** ([#279](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/279)) : **Confirmer** et **Annuler** atteignent le serveur auquel le poste est relié, et après une mise à jour le poste montre l’interface de sa version, sans manipulation du collaborateur.

**Contrainte.** Le chemin de mise à jour d’un poste est porté par le Lanceur déjà installé : les postes en place gardent l’ancien comportement jusqu’à ce qu’ils aient reçu le nouveau.

**Hors périmètre.** Mise à jour pendant que BBASS tourne en fond ([ADR-0022](../../adr/0022-poste-application-windows-version-dictee-par-la-vm.md)). Sélecteur d’Environnement sur le poste. Texte du modèle qui annonce une carte inexistante.

## Ensuite : 1.7.0 — Suivi de l’alternance

*(Série **1.7.x** : documentation seule, menée en parallèle de la série **1.8.x**. Aucune Release produit ([numéro produit](https://github.com/UlyssouLV/BBASS-Agents-IA/blob/main/docs/dev/feuille-de-route/README.md#numéro-de-développement-et-numéro-produit)). Les anciennes 1.7.0 à 1.7.8 deviennent **1.7.1** à **1.7.9**.)*

**Objectif.** Un supérieur hiérarchique qui n’est pas du métier voit sur le site de documentation, dans un espace **Suivi de l’alternance**, où en est réellement la mission, preuves à l’appui, sans explication orale. L’espace mesure l’avancement sur les critères de la feuille de route de BBASS et de la note de cadrage, pas sur le volume de développement :

- **Critères de réussite** : objectifs des phases 1 et 2, jalons J1 et J2, livrables L1 à L11, chacun avec son état (à faire, en cours, atteint) et sa preuve ; ce qui n’est pas atteint se voit ;
- **Semaines** : semaines passées, semaine en cours et semaines à venir, avec les objectifs de chacune et le travail fait ou prévu, en langage purement fonctionnel ;
- **Vidéo de démonstration** par semaine, hébergée sur YouTube en non répertorié et visible depuis le site ; un **skill** dit concrètement quoi filmer pour montrer les nouveautés de la semaine ;
- **Documents** : feuille de route de déploiement tenue à jour, note de cadrage, feuille de route initiale, documents de suivi hebdomadaires ;
- **Échanges** : mails, messages Moduléo et autres échanges avec les prestataires externes, les collaborateurs et les supérieurs ;
- **En dehors de la mission** : tâches supplémentaires demandées par BBASS. L’alternant crée lui-même les tâches ; cette version livre la rubrique vide.

Le site est public et les documents comme les échanges y sont publiés : décision du 2026-10-30, risque accepté, passage éventuel en privé en **Plus tard**. Le site se republie à chaque commit pour rester à jour ; la semaine en cours se déduit de la date.

**À trancher au grilling.** Format des données d’une semaine et d’un critère. Branche qui déclenche la publication à chaque commit, `main` n’acceptant que des fusions de PR. Forme des échanges publiés. Place des semaines déjà écoulées. Format du skill de démonstration.

**Hors périmètre.** Envoi de fichiers depuis le site : un document s’ajoute par commit. Choix de lecture Collaborateur / Administrateur / Développeur (→ **1.7.1**) : le Suivi a son propre onglet. Saisie des tâches « En dehors de la mission ». Refonte du document de suivi hebdomadaire.

## Ensuite : 1.7.1 — Site de documentation à trois lectures : Collaborateur, Administrateur, Développeur

**Objectif.** Toute personne qui ouvre le site de documentation choisit sa lecture d’un bouton : **Collaborateur** (utiliser le Copilote au quotidien), **Administrateur** (gérer les comptes, installer et maintenir), **Développeur** (comprendre et faire évoluer le système). Le choix est mémorisé ; l’accueil, le menu et la recherche montrent d’abord les pages de cette lecture, et une page commune adapte ses parties. La version livre aussi :

- une **convention de page** courte (objectif, schémas, tableaux « où vit / qui voit / ce qui sort », pas de copie de code, public déclaré par page), modèle des versions 1.7.x suivantes ;
- un socle d’**accessibilité** et d’ergonomie : contraste, navigation au clavier, textes alternatifs, langage simple et captures côté Collaborateur ;
- les pages existantes (Connexion, Branchement Moduléo, Inspecteur, Installation) rangées dans la convention et rattachées à leur lecture ;
- un **tableau de couverture** fonctionnalité → page → lecture, qui montre ce qui reste à documenter et se vide au fil de la série ;
- le Changelog en deux suivis : **Nouveautés** (numéros produit, lectures Collaborateur et Administrateur) et **Journal de développement** (numéros de développement, lecture Développeur).

À partir de cette version, toute version qui change une fonctionnalité met à jour sa page dans chaque lecture concernée.

**À trancher au grilling.** Page par lecture ou page commune à parties adaptées. Lecture par défaut à la première visite. Rendu de la bascule sur mobile. Outil de vérification de l’accessibilité.

**Hors périmètre.** Nouveau contenu (→ **1.7.2** à **1.7.9**). Suivi de l’alternance (→ **1.7.0**). Contrôle d’accès : le site reste public, la bascule ne cache rien. Traduction.

## Ensuite : 1.7.2 — Documentation : utiliser le chat au quotidien

**Objectif.** Lecture **Collaborateur**, avec captures : tout ce qu’on fait dans le chat. Conversations (créer, reprendre, renommer, supprimer, changer de conversation pendant une réponse), envoi et statut d’attente, pièces jointes, recherche web et sources, ce que l’IA retient d’une conversation et ce qu’elle relit, jauge de contexte, Profil, Consommation. Ce que l’IA refuse ou remplace, expliqué simplement (chiffre sans source, lien non fourni, « pas trouvé », la relecture : réponse réécrite qui dit ce qui n’a pas été trouvé et où on a cherché, le marqueur « [non trouvé] » et la phrase fixe). Lecture Développeur : renvois courts vers **1.7.5** et **1.7.6**.

**Hors périmètre.** Moduléo (→ **1.7.3**). Panel d’administration (→ **1.7.4**). Détail des flux (→ **1.7.5**, **1.7.6**).

## Ensuite : 1.7.3 — Documentation : Moduléo depuis le chat

**Objectif.** Les pages « Branchement Moduléo » reprises dans la convention et complétées de l’écriture livrée en 1.5.2 : ce qu’on peut lire et écrire, la carte de confirmation (création, modification, suppression), ce que veut dire chaque statut de carte, les refus faute de droit, le serveur de test. Lecture **Collaborateur** : demandes types et ce qu’on voit. Lecture **Administrateur** : configuration, droits, groupes. Lecture **Développeur** : garde des droits, routes classées, ADR.

**Hors périmètre.** Serveur MCP Moduléo (série **1.10.x**, qui met ces pages à jour). Gestion des groupes dans le Panel (→ **1.7.4**).

## Ensuite : 1.7.4 — Documentation : administrer BBASS

**Objectif.** Lecture **Administrateur** : tout le Panel d’administration — comptes (création, mot de passe généré, changement forcé, révocation, pôle et agence), consommations, groupes et droits Moduléo (reprend l’ancienne entrée Plus tard « Doc-site : administration des groupes et droits Moduléo ») — et les guides d’installation et de maintenance du serveur et du poste (1.6.1, 1.6.2), rangés sous cette lecture, avec staging / prod et la promotion d’une version.

**Hors périmètre.** Fonctionnement interne (→ **1.7.7**, **1.7.8**). Inspecteur (lecture Développeur, rangé en **1.7.1**).

## Ensuite : 1.7.5 — Documentation : mémoire et souveraineté des données

**Objectif.** Deux documents, chacun en deux lectures : **Collaborateur** (« où vont mes données, qui les voit », en une page simple) et **Développeur** (détail ci-dessous).

1. **Persistance de la mémoire.** Schéma compréhensible (conversations, messages, résumé glissant, profil de travail, pièces jointes, résultats de recherche web, etc.), flux tour par tour (ce qui entre, ce qui sort de la fenêtre de 3, ce qui est plafonné, ce que le modèle relit via outils), choix déjà pris et **pourquoi** (persistance VM vs API Conversations Mistral, séparation identité / profil, etc.). Exemples concrets (inspecteur, états) et renvois aux tests HTTP-boundary en annexe courte. Inclut la Mémoire de la conversation et les questions couvertes (1.4.1), le cache des pages web (1.4.3).

2. **Souveraineté des données.** Cartographie de tous les choix qui font que **seul le cabinet** détient les données persistées : Postgres et fichiers sur la VM Castries, SearXNG auto-hébergé, pas de Files API / Conversations Mistral, ZDR / `chat/completions` sans rétention côté modèle, clé API unique derrière la VM, LAN uniquement, etc. Expliquer **pourquoi** chaque décision rend le cabinet souverain. **Carte globale** « où vit la donnée » et **ce qui quitte le cabinet** (Mistral, Moduléo, SearXNG, rien d’autre) pour les chemins critiques ; liens ADR / specs.

La souveraineté dit aussi que la relecture isolée est un appel Mistral de plus : ce qu’il reçoit (question, réponse, résultats d’outils) et ce qu’il ne reçoit pas (historique).

**Hors périmètre.** Détail par outil de ce qui part / revient (→ **1.7.6**). Doc détaillée du tool calling recherche web (→ **Optimisation de la recherche web**, Plus tard). Implémentation de nouvelles capacités mémoire ou cache.

## Ensuite : 1.7.6 — Documentation : outils du modèle et flux par outil

**Objectif.** Lecture **Développeur** : inventaire de **tous les outils** exposés au modèle — recherche web, relecture de pièces jointes / pages, Moduléo, etc. Pour chaque outil : à quoi il sert, paramètres utiles en langage produit, **ce qu’il envoie / reçoit / persiste**, ce qui reste sur la VM, lien avec l’inspecteur. Complète la carte de souveraineté de la **1.7.5** sans la réécrire.

**Hors périmètre.** Doc ultra-détaillée du tool calling recherche web (→ **Optimisation de la recherche web**, Plus tard). Outils Moduléo passés par le serveur MCP (mis à jour par la série **1.10.x**).

## Ensuite : 1.7.7 — Documentation : base de données

**Objectif.** Lecture **Développeur** : toute la base de la VM centrale **documentée et visualisée** — un schéma lisible (tables et relations), puis chaque table, chaque colonne, son rôle en langage clair, qui l’écrit, qui la lit, combien de temps les lignes vivent. Une personne qui découvre le projet comprend où vit chaque donnée sans lire le code.

**Hors périmètre.** Relations entre les services (→ **1.7.8**). Système de migration de schéma (→ **Alembic**, Plus tard). Carte de souveraineté (→ **1.7.5**, non réécrite).

## Ensuite : 1.7.8 — Documentation : relations entre les services

**Objectif.** Lectures **Développeur** et **Administrateur** : une carte claire de **qui parle à qui** — poste, VM centrale, Postgres, SearXNG, Mistral, Moduléo, et les deux Environnements staging / prod de la **1.6.1** : ports, sens des appels, ce qui reste sur le LAN et ce qui sort, ce qui se passe quand un service manque.

**Hors périmètre.** Détail par outil du modèle (→ **1.7.6**). Tables et colonnes (→ **1.7.7**). Procédure d’installation (→ **1.7.4**). Serveur MCP Moduléo (ajouté à la carte par la série **1.10.x**).

## Ensuite : 1.7.9 — Documentation : que faire si…

**Objectif.** Toutes lectures : une entrée par situation que l’on peut rencontrer, retrouvable depuis le message vu à l’écran — bandeaux du poste (Serveur BBASS injoignable, mise à jour, retour arrière), phrases fixes de la VM (Moduléo en panne ou refusé, droit manquant, page trop longue, réponse remplacée par un garde-fou, « Certaines informations n’ont pas été trouvées dans les sources consultées »…), statuts de carte Moduléo, erreurs de connexion. Pour chacune : ce que ça veut dire, si c’est grave, quoi faire, qui prévenir. En fin de version, le tableau de couverture de la **1.7.1** est vide.

**Hors périmètre.** Corriger ces situations (bugs → Plus tard).

## Ensuite : 1.8.0 — Filmer une tâche depuis le poste

*(Série **1.8.x** : cartographie des usages, menée en parallèle de la série **1.7.x**, avant le serveur MCP Moduléo. Les anciennes 1.8.x deviennent **1.10.x**, les workflows n8n **1.12.0**, les pièces jointes approfondies **1.13.0**.)*

**Objectif.** Depuis le logiciel, le collaborateur filme son écran quand il estime qu’une tâche mérite d’être montrée : une tâche répétitive, un comportement à signaler, un besoin. C’est lui qui déclenche et arrête la capture ; rien n’est filmé sans son geste, et ce n’est pas un outil de surveillance. La vidéo est rattachée à son compte et à son pôle, et il décrit la tâche en quelques mots. L’alternant les retrouve toutes au même endroit, pôle par pôle : il voit le travail réel des pôles sans être présent, y compris pendant les semaines d’école.

**Pourquoi avant le serveur MCP.** La feuille de route de BBASS et la note de cadrage demandent une cartographie des besoins et une mesure de la réussite ; rien n’est fait aujourd’hui. Une tâche doit être observée avant qu’une solution la change, sinon aucun gain ne pourra être mesuré.

**Contraintes.** Les écrans montrent des données clients : les vidéos restent sur la VM, ne vont ni chez Mistral ni sur YouTube, et leur accès est restreint. Les postes concernés seront installés à la sortie de la version.

**À trancher au grilling.** Micro pour commenter pendant la capture. Écran, fenêtre ou onglet partagé. Durée maximale. Place sur le disque de la VM et durée de conservation. Qui peut voir une vidéo. Ce qui est demandé au collaborateur à la fin de la capture. Information des collaborateurs avant le premier essai réel.

**Hors périmètre.** Toute capture non déclenchée par le collaborateur. Analyse automatique d’une vidéo. Cartographie et priorisation (→ **1.8.1**).

## Ensuite : 1.8.1 — Cartographie des usages et priorisation

**Objectif.** Chaque vidéo devient une fiche de tâche : pôle, tâche, logiciels et données utilisés, fréquence, temps réellement passé. La durée d’une vidéo ne suffit pas : le temps et la fréquence se demandent au collaborateur. Les fiches forment la **cartographie des besoins** des six pôles et la liste de **cas d’usage**, classée selon les critères de la feuille de route de BBASS : gain de temps potentiel, fréquence, intérêt pour BBASS, faisabilité technique, données disponibles, niveau de risque, besoin de validation humaine. Le temps noté devient la **référence avant solution**. La cartographie et la liste alimentent le **Suivi de l’alternance** (livrable L1) et servent à arrêter l’ordre des cinq autres pôles.

**À trancher au grilling.** Barème de priorisation. Saisie des fiches : Panel d’administration ou document. Entretiens en complément des vidéos.

**Hors périmètre.** Réaliser les cas d’usage. Comparer avant et après (→ **Mesure du gain de temps**, Plus tard).

## Ensuite : 1.9.0 — Agent Administration

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

*(Reprend l’entrée Plus tard « Agents métier par pôle », sortie de la 1.5.0 pour la garder petite.)*

**Objectif.** Le premier Agent métier : le pôle Administration a sa consigne et sa liste de capacités autorisées, nourries par les cas d’usage priorisés de la **1.8.1**. Il exécute des tâches administratives depuis le chat (suivi des affaires, devis, factures, temps passés, planning), testé avec les collaborateurs du pôle, et il pose le cadre commun aux Agents suivants. Jalon J1 de la note de cadrage (fin décembre 2026), à réévaluer avec le tuteur : les courriels et les documents arrivent en **1.11.0** et **1.11.1**.

**Déjà tranché.** Un **Agent** sert un pôle : sa consigne, et la liste des capacités qu’il a le droit d’utiliser. Les **outils restent communs** (`vm_centrale/outils/`, dont Moduléo depuis la 1.5.0) : ce n’est pas un « Agent Moduléo ». Le code d’un Agent (consigne, liste des outils autorisés, éventuels traitements propres au pôle) vit dans un dossier par Agent ; un petit registre choisit les outils du tour selon l’Agent, sans `if` par pôle dans `routers/conversations.py`. Le pack `agents/` à la racine du dépôt reste un outil de développement (skills, hooks), distinct des Agents métier. Un Agent est une configuration dans le flux chat de la VM centrale, **pas un conteneur Docker par Agent / par pôle** (pas de runtime propre, ops inutiles alors que peu de tech sera sur place). Si l’indépendance de déploiement devient un besoin : config rechargeable d’abord, et ne conteneuriser que ce qui a un vrai cycle de vie (adaptateur Moduléo en écriture, bac à sable d’exécution, n8n).

**À trancher à l’ouverture.** Comment un tour choisit son Agent (pôle du compte, choix explicite, plusieurs pôles), quelles capacités pour le pôle Administration, lien avec le traitement des pièces jointes par pôle (**1.13.0**).

**Hors périmètre.** Agents des cinq autres pôles (→ Plus tard). Messagerie et serveurs de fichiers (→ **1.11.0**, **1.11.1**).

## Ensuite : 1.9.1 — Jeu de cas de test et taux de réponses correctes

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

**Objectif.** Chaque Agent a un jeu de cas de test métier, rejouable, qui donne son **taux de réponses correctes**, ses erreurs et les situations où une validation humaine reste nécessaire, comme le demandent la note de cadrage (livrable L8) et la feuille de route de BBASS. Les résultats sont publiés dans le **Suivi de l’alternance**. Le premier jeu porte sur l’Agent Administration.

**Hors périmètre.** Mesure du gain de temps (→ Plus tard).

## Ensuite : 1.10.0 — Serveur MCP Moduléo : lire Moduléo par un serveur standard

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

*(Série **1.10.x** : reprend l’entrée Plus tard « Serveur MCP Moduléo » (spec 1.5.2, tests humains [#206](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/206)).)*

**Objectif.** Les lectures Moduléo du chat passent par un **serveur MCP** (Model Context Protocol) Moduléo, sans changement visible pour le collaborateur : mêmes fiches en noms, mêmes droits par groupe, mêmes phrases fixes, mêmes sources des garde-fous. La VM centrale devient l’**hôte** MCP : elle garde la boucle Mistral et présente au modèle les outils du serveur. À « Qu’est-ce que tu sais faire avec Moduléo ? », le chat répond avec ce que le compte peut réellement lire, tiré de la liste d’outils du serveur filtrée par ses droits, et non de ce que le modèle imagine (tests humains [#206](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/206) : réponse inventée, puis avalée par le garde-fou des chiffres). Socle des **1.10.1** et **1.10.2**.

**Recherche** (dans `docs/dev/recherches/`, avant d’ouvrir la version). Partir de la doc officielle : [Getting started](https://modelcontextprotocol.io/docs/2026-07-28/getting-started/intro), [Architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture), [Server concepts](https://modelcontextprotocol.io/docs/2026-07-28/learn/server-concepts), [Build servers](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server), [Security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices). Trancher :

- où tourne le serveur : processus lancé par la VM (transport stdio) ou conteneur à côté sur le réseau Docker interne (Streamable HTTP) ;
- comment le compte et ses droits Moduléo atteignent le serveur sans en faire un « adjoint confus » (un seul compte de service pour tous) et sans transmettre à Moduléo un jeton émis pour le serveur ;
- ce qui reste un outil, ce qui devient une ressource (listes de référence) ;
- la granularité des outils : génériques (une route et son corps JSON, comme l’écriture de la 1.5.2) ou métier (un outil par geste, qui prend des noms) — décidée ici, elle conditionne les **1.10.1** et **1.10.2** ;
- SDK Python `mcp` (version 2 ou plus), tests à la frontière avec un client MCP de test, place du serveur dans l’inspecteur.

**Hors périmètre.** Retrouver un élément par son nom (→ **1.10.1**). Écriture (→ **1.10.2**). Ouvrir le serveur à des clients hors BBASS.

## Ensuite : 1.10.1 — Serveur MCP Moduléo : retrouver par son nom ce que l’API ne lit que par id

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

**Objectif.** Le collaborateur peut dire « catégorie Terrain » : le serveur construit et tient à jour la correspondance nom → id des éléments que l’API Moduléo ne lit que par id (catégories de tâche à faire `moduleo/categorietacheafaire/{id}`, de note `cogeo/categorienote/{id}`…), en lisant les ids un à un et en les mettant en cache faute de route de liste, ou par une route de liste si Kipaware en ouvre une. Le serveur donne aussi au modèle l’id des éléments que les fiches de la 1.5.2 ne portent pas (téléphones, e-mails et adresses d’un contact, notes, tâches à faire), pour pouvoir les modifier ou les supprimer, et les valeurs de référence qu’une écriture exige sans moyen de les retrouver (lieux d’un temps passé, catégories et utilisateurs affectés d’une tâche à faire). Lève les limites de la 1.5.2 (« pas de moyen de retrouver l’élément à partir de son nom », écritures refusées faute d’id, [#257](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/257)). Les codes activité et le collaborateur du compte sont déjà donnés en 1.5.2 (`decrire_ecriture_moduleo`).

**Constaté en 1.5.2** (troisième passage des tests humains, [#206](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/206), captures au commit `59f6142`) :

- un élément déjà enregistré qu’aucune fiche ne désigne par son id ne peut être ni modifié ni supprimé : le téléphone d’un contact (scénarios 12 et 16, [12a](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-12a-telephone-existant.png), [16a](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-16a-suppression-telephone-existant.png)), une tâche à faire (20 bis : le refus faute d’id passe avant celui du droit, qui n’est donc jamais nommé, [20bis](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-20bis-refus-droit-edition-tache.png)) ;
- le modèle refuse même un id autorisé, celui qu’une création confirmée de la conversation vient de renvoyer (16b, [16b](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-16b-carte-suppression-telephone.png)) ;
- des champs obligatoires n’ont aucun moyen d’être retrouvés : le lieu d’un temps passé, Moduléo refuse « Veuillez sélectionner le lieu. » à la confirmation (scénario 10, [10f](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-10f-temps-passe-confirme.png)) ; la catégorie et les utilisateurs affectés d’une tâche à faire, 8 demandes de création sur 10 sans carte ([rejeu 10](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-252-rejeu-10.png)) ;
- le modèle confond un numéro d’affaire et un id : « SCPT-0010 » devient l’affaire 10 (f02) sur une modification de note non demandée, que la carte montre (scénario 19, [19c](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-19c-modification-note-mauvaise-affaire-annulee.png)).

**À trancher au grilling.** Durée de vie du cache et rafraîchissement. Borne de lecture des ids. Exposition des listes comme ressources du serveur.

**Hors périmètre.** Demander une route de liste à Kipaware (démarche à mener en parallèle, sans bloquer). Écriture (→ **1.10.2**).

## Ensuite : 1.10.2 — Serveur MCP Moduléo : écrire par le serveur

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

**Objectif.** Les écritures Moduléo de la 1.5.2 passent par le serveur MCP avec toutes leurs garanties : garde des droits appliqué par le serveur pour le compte authentifié, carte de confirmation dans le poste et confirmation hors du modèle, identifiant de carte lié au compte (le posséder ne suffit pas à confirmer), serveur de test seulement, ids jamais à l’écran. Le serveur refuse une écriture non confirmée, quel que soit l’hôte qui l’appelle. La réponse à « Qu’est-ce que tu sais faire avec Moduléo ? » (1.10.0) couvre alors les écritures : celles que le compte peut proposer, d’après les outils d’écriture du serveur et ses droits.

**Constaté en 1.5.2** (troisième passage des tests humains, [#206](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/206), captures au commit `59f6142`) :

- le modèle répond en texte (« Confirmez l’écriture pour l’enregistrer ») au lieu d’ouvrir une carte, surtout après une première carte dans la conversation, et même relancé par la garde avec un outil imposé (`tool_choice` « any » et une consigne) : déplacer un téléphone vers un autre contact (scénario 12, [12g](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-12g-carte-deplacement-telephone.png)), supprimer une note (19, [19d](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-19d-carte-suppression-note.png)) ; rien n’est écrit, la phrase fixe « Aucune carte de confirmation n’a été ouverte… » s’affiche ;
- le texte du modèle reste trompeur, avec ou sans carte, et une garde par motifs ne peut pas couvrir toutes les tournures : « a été renommé » sans écriture (13, [13](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-13-modification-sans-changement.png)), « ont été saisies » avant la confirmation et « mercredi 29 octobre » pour un jeudi (10, [10e](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-10e-carte-temps-passe-en-noms.png)), titre de conversation « … ajouté » sans écriture (20, [20](https://github.com/UlyssouLV/BBASS-Agents-IA/raw/59f6142ef5f93f9fd804452e1e71e634a075b9b1/docs/img/changelog/v1.5.2/p3-20-refus-droit-rechercher-contacts.png)), fragment « (id Moduléo ) » et id demandé au collaborateur (20 bis).

**Piste à confronter au grilling** (pas une décision). Des outils métier (créer un téléphone, saisir un temps passé…) qui prennent des noms et retrouvent les ids côté serveur, à la place de l’outil générique route + corps JSON de la 1.5.2, pour que le modèle ait moins à décider ; un texte du tour tiré du statut de la carte plutôt que des mots du modèle.

**À trancher au grilling.** Rôle de l’elicitation MCP (demande de confirmation du serveur à l’hôte) à côté de la carte, qui reste la garantie.

**Hors périmètre.** Écriture sur le serveur Moduléo du cabinet (décision à part). Ouvrir le serveur à des clients hors BBASS.

## Ensuite : 1.11.0 — Messagerie : préparer et envoyer un courriel depuis le chat

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

**Objectif.** Le collaborateur prépare un courriel depuis le chat : brouillon, confirmation dans l’interface, puis envoi, comme une écriture Moduléo. Aucun envoi sans confirmation. Demandé par la note de cadrage (composant P2, livrable L4).

**Recherche.** Messagerie utilisée par le cabinet et moyens d’y accéder, droits de chaque compte.

**Hors périmètre.** Envoi automatique sans confirmation. Serveurs de fichiers (→ **1.11.1**).

## Ensuite : 1.11.1 — Retrouver un document sur les serveurs de fichiers

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

**Objectif.** Le collaborateur retrouve et consulte un document des dossiers du cabinet depuis le chat, dans le respect de ses droits d’accès. Demandé par la note de cadrage (composant P2, livrable L4).

**Recherche.** Accès aux serveurs de fichiers depuis la VM, reprise des droits existants, données qui sortent vers Mistral.

**Hors périmètre.** Écriture et classement sur les serveurs de fichiers.

## Ensuite : 1.12.0 — Workflows n8n (socle d’automatisation), branchés sur Moduléo 1.5.0

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

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
- Comment réexposer ou appeler la stack Moduléo 1.5.0 depuis n8n (HTTP Request vers Moduléo vs rappel d’un service VM vs serveur MCP Moduléo de la série **1.10.x**).

## Ensuite : 1.13.0 — Analyse et traitement des pièces jointes, approfondis

*(Brouillon : à partir de la 1.9.0, le contenu et l’ordre changeront très probablement.)*

S’appuie sur la [1.1.2](../../specs/v1.1.2-pieces-jointes.md) (pipeline d’extraction, une pièce jointe par message). Le traitement par pôle suppose les Agents métier : l’Agent Administration (**1.9.0**), puis ceux des cinq autres pôles (Plus tard). Deux limites actées volontairement en 1.1.2 sont à lever ici, pas avant : **plusieurs pièces jointes par message**, et un **traitement spécifique par pôle** (un agent Foncier ne traite pas un document comme un agent Urbanisme) — demande explicite du cabinet dès le grilling de 1.1.2, remise à plus tard faute d’Agent réel pour la justifier.

**Objectif.** Une pièce jointe mieux exploitée selon qui la reçoit (le pôle de l’Agent destinataire). Le rappel d’une pièce jointe dans la durée de la conversation est livré par la 1.4.1 (Mémoire de la conversation, questions couvertes, `relire_pieces_jointes`).

**Recherche.**

- Plusieurs pièces jointes par message : impact sur le schéma `PieceJointe` (déjà pensé pour ne pas bloquer ça), sur l’outil `relire_pieces_jointes` (1.4.1, déjà capable d’en relire plusieurs d’un coup), sur le résumé glissant (une mention courte par pièce jointe, pas une agrégée).
- Traitement par pôle : qu’est-ce qui change concrètement pour un même format (PDF, image, …) selon le pôle de l’Agent qui le reçoit — nouveau prompt d’extraction, post-traitement dédié, ou simple différence de consigne à l’IA plutôt qu’un pipeline dupliqué.
- Fiabilité de l’analyse elle-même, au-delà de la plomberie : enseignements des essais fonctionnels 1.1.2 (ex. liens inventés entre pièces jointes sans preuve, confusions de vocabulaire métier propre à un document) qui ne relèvent ni de la fenêtre de 3 messages ni du profil de travail.
- Conservation d’une pièce jointe au-delà de sa conversation d’origine (usage multi-conversationnel, matière pour entraîner les futurs Agents) : piste évoquée dès le grilling 1.1.2, pas tranchée.

## Plus tard (pas encore numéroté)

### Agents des cinq autres pôles

Appels d’offres, Foncier, DAO, Urbanisme et Détection de réseaux : même cadre que l’Agent Administration (**1.9.0**), un à la fois, chacun testé avec les collaborateurs de son pôle. L’ordre est arrêté à partir de la cartographie (**1.8.1**) ; numérotation à ce moment-là.

### Mesure du gain de temps

Compare le temps d’une tâche après la mise en service d’une solution à sa référence avant solution (**1.8.1**), pour montrer si les tâches chronophages ont réellement diminué. **Déclencheur** : un premier cas d’usage en service.

### Rendre le site de documentation privé

Le site est public par choix ; il publie notamment les échanges et les documents du Suivi de l’alternance (**1.7.0**). Le rendre privé protégerait ces contenus, sans couper l’accès du tuteur pédagogique, extérieur au cabinet.

### Bug — lien de source peu visible (#99)

**Constat :** malgré les travaux front sur le rendu des sources (suite #98), l’affichage **ne valide toujours pas** les critères — le texte de l’ancre n’est pas clairement cliquable (URL au survol natif), et l’affordance (couleur / soulignement) ne rend pas le lien repérable sans pastille seule, ni sans laisser croire que toute la phrase est cliquable.

**Reproductibilité :** essai manuel — ouvrir une réponse qui cite une source et vérifier ancre, `href` au survol, et affordance dans le fil.

**Impact :** citations de sources peu repérables / peu utilisables ; critères d’acceptation de #98 non tenus.

**Cause probable :** Informations manquantes

**À corriger :** rendre le texte de l’ancre cliquable (URL au survol natif) ; affordance claire sans pastille seule et sans faire croire que toute la phrase hors citation est cliquable (front `LienSource` / Markdown chat).

**Hors périmètre :** vm-centrale / prompt de style (hors sujet, déjà #96).

**Suivi :** [#99](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/99) (`bug`). Trouvé dans : Informations manquantes · Contexte : essai manuel · Date : 2026-10-05 · Priorité : Informations manquantes.

### Agent IA de continuation du développement, validation par compte administrateur

Constat (grilling 1.2.0) : à terme, plus aucune personne qualifiée ne sera sur place pour faire évoluer le logiciel elle-même. L'évolution du code (nouvelles versions, corrections, nouveaux Agents métier) serait alors portée par un agent IA dédié à la continuation du développement, avec un compte administrateur qui ne fait que **valider** (approuver/refuser) les changements proposés, sans avoir à coder ni à relire le code en détail.

Implications déjà identifiées à creuser plus tard :
- Cette contrainte pèse sur les choix techniques pris dès 1.2.0 (ex. TypeScript plutôt que JS nu, pour donner un filet de sécurité à la compilation en l'absence de relecture humaine technique).
- Reste à définir : à quoi ressemble concrètement le flux de validation (où/comment un compte administrateur voit et approuve un changement), le périmètre de ce que l'agent peut faire seul vs ce qui nécessite une validation, et les garde-fous (rollback, tests obligatoires avant validation, etc.).
- Tests front (grilling 1.2.0) : pas de tests dédiés côté UI React en 1.2.0 (on reste sur les tests pytest HTTP-boundary existants + validation visuelle par l'admin). À une version pas encore numérotée : ajouter un filet de sécurité automatisé côté UI (ex. Playwright) puisque seul un agent IA maintient ce code sans relecture humaine technique — pertinent surtout quand le volume d'écrans aura grossi (1.3.0, 1.4.0, 1.5.0, 1.6.0, 1.7.0, 1.8.0, 1.9.0 et au-delà).

### Lanceur poste (exécutable, fenêtre + accès web)

→ **Repris et numéroté en 1.6.2** (installateur propre, fenêtre propre, logiciel en fond après fermeture de la fenêtre, ouverture possible depuis le navigateur / raccourci). Cette entrée « Plus tard » ne fait plus office de file d’attente séparée.

### Déploiement, livrables, retours utilisateurs

→ **Repris et numéroté en 1.6.0** (CI : versions vérifiées et prêtes à livrer), **1.6.1** (CD : mise à jour VM Castries) et **1.6.2** (installateur postes). Contraintes déjà vues à réintégrer dans la spec à l’ouverture de chaque version : pas forcément de VM centrale physique pour déployer le relais ; LAN Castries vs Internet ; pilote sur quelques machines ; fin du build front fait uniquement à la main.

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
- RAG sur un corpus cabinet, distinct des pièces jointes du fil courant (1.1.2 / 1.13.0).
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

### Vérification de la fiabilité des sources web

Constat (essais manuels 1.4.0) : `rechercher_web` ramène des pages et l’IA les cite ; rien ne dit encore si une source est digne de confiance (site officiel, presse, blog, forum, page commerciale). Une amélioration ultérieure de la recherche web ferait **évaluer la fiabilité des sites sourcés** avant ou avec la réponse : indiquer au collaborateur le degré de confiance, écarter ou rétrograder les sources douteuses, et garder une trace lisible (inspecteur ou mention courte).

Pistes à trancher à l’ouverture : critères (domaine `.gouv.fr` / institutionnel, liste blanche cabinet, score heuristique, second passage modèle…), moment du contrôle (à la réception des résultats, après lecture des pages, à la rédaction), ce que voit le collaborateur, et le lien avec les garde-fous URL déjà en place. S’appuie sur la 1.4.0 et le registre d’outils. Distinct de l’optimisation **par défaut** (tokens / snippets) et des modes Rapide / Approfondi.

### Modes de réponse (Rapide / Approfondi) et outils de lecture plus fins

Constat (ouverture 1.4.0) : plusieurs façons d’utiliser les outils sont possibles selon l’effort voulu. Un mode choisi par le collaborateur réglerait le nombre de tours d’outils (voir « Le tool calling ne boucle pas »), le nombre de pages lues, le choix des pages par le modèle (s’appuie sur `lire_pages_web`, 1.4.1), un appel de synthèse, ou le modèle utilisé. Change le contrat HTTP du poste (choix du mode). Le découpage de la 1.4.0 (registre d’outils, appel d’extraction isolé, [ADR-0014](../../adr/0014-recherche-web-en-deux-temps-extraction-isolee.md)) est fait pour s’y brancher. Distinct de l’optimisation **par défaut** de la recherche web et de la **vérification de fiabilité des sources** (rubriques précédentes), qui ne demandent pas de choix utilisateur.

### Exécution de code dans le chat (cellules Python exécutables, façon ChatGPT)

Constat (validation manuelle de la coloration syntaxique, #95/#97) : au-delà de l'afficher correctement, le cabinet a comparé au comportement de ChatGPT qui permet d'exécuter directement une cellule de code Python dans la conversation et d'en voir le résultat.

Pas de travail avant que le besoin se confirme — portée très différente d'un ajustement de rendu : il faudrait un bac à sable d'exécution (isolation, limites CPU/mémoire/temps, pas d'accès réseau/fichiers du poste), une décision sur où il tourne (poste local vs VM centrale vs service tiers) et une revue sécurité dédiée avant d'exposer quoi que ce soit d'exécutable à une réponse de modèle. Distinct de #97 (habillage visuel des blocs de code), qui n'en dépend pas.

### Migrations de schéma (Alembic)

Constat (grilling 1.6.1) : la base de la VM se crée au démarrage et ne sait qu’**ajouter** tables et colonnes ([ADR-0008](../../adr/0008-postgresql-vm-centrale.md)). Alembic transformerait chaque changement de schéma en script numéroté, appliqué dans l’ordre au démarrage. **Déclencheur** : la première version qui renomme ou supprime une colonne, ou déplace des données.

### HTTPS partout : poste, réseau du cabinet et services internes de la VM

Constat (grilling 1.6.1, puis quality gate Sonar de la 1.6.2, PR #248) : la VM n’est servie qu’en HTTP sur le LAN de Castries ([ADR-0003](../../adr/0003-v1-scope-castries-seule.md), [ADR-0021](../../adr/0021-cd-vm-centrale-staging-prod.md)). Entre le poste et le Serveur BBASS passent donc en clair les mots de passe, les jetons de session, les conversations, les pièces jointes et les données Moduléo : tout appareil du réseau peut les lire ou se faire passer pour le Serveur BBASS. L’alerte Sonar (`python:S5332`) est acceptée pour l’instant par un `# NOSONAR` dans `poste/src/poste/config.py` (`adresse_http`).

**Objectif.** Tous les échanges de BBASS passent en HTTPS, internes compris, avec vérification du certificat : backend poste et Lanceur vers le Serveur BBASS, test du Setup, fenêtre BBASS vers le backend du poste (`127.0.0.1:8100`), VM vers Postgres et SearXNG, script de mise à jour de la VM. Le passage se fait sans casser les postes déjà installés : la VM sert HTTP et HTTPS le temps que les postes se mettent à jour, puis l’admin ferme l’HTTP. Le collaborateur n’a rien à installer à la main ; l’admin confirme une seule fois l’empreinte du certificat du cabinet au Setup.

**Orientation technique (à trancher au grilling).** Méthodes détaillées, avantages et limites dans la note [HTTPS sur tous les échanges BBASS](../recherches/recherche-https-partout.md) : reverse proxy TLS devant la VM (Caddy recommandé) ou TLS dans uvicorn ; certificat d’une autorité interne épinglée dans les clients BBASS (recommandé), certificat public Let’s Encrypt par défi DNS sur un nom du cabinet, PKI Active Directory du cabinet, ou auto-signé épinglé ; Postgres en `verify-full` et SearXNG derrière le proxy ; pour la boucle locale du poste, HTTP gardé et assumé par ADR, certificat par poste accepté par WebView2, ou plus de port TCP (IPC Tauri). Décision figée dans un ADR qui révise l’ADR-0021, et retrait du `# NOSONAR`.

**Hors périmètre.** TLS mutuel (certificat par poste), VPN, ouverture aux satellites ou à Internet.

### Sauvegarde nocturne et copie hors de la VM

Constat (grilling 1.6.1) : la 1.6.1 ne sauvegarde la base qu’avant un changement de version, sur le même disque. Une sauvegarde nocturne de la base **et** des fichiers de pièces jointes, copiée hors de la VM (NAS du cabinet), protégerait contre la perte de la machine. Se branche sur la convention des tâches planifiées de la 1.6.1 (`taches-planifiees.conf`).

### Chiffrer `VM_ADMIN_KEY` dans le `.env` de la VM

Constat (tests humains 1.6.1, #236, scénario 10) : dans `/opt/bbass/<env>/.env`, les clés Mistral et Moduléo sont chiffrées avec la clé maître, mais `VM_ADMIN_KEY` y est écrite en clair (fichier lisible par root seul). La chiffrer comme les autres clés éviterait qu’une copie du `.env` seule (sauvegarde, instantané, envoi pour dépannage) suffise à administrer la VM. Hors périmètre : le mot de passe Postgres, qui ne sert que sur le réseau interne de la stack.

### Migrer le compte Ubuntu One propriétaire d’Ubuntu Pro

Constat (tests humains 1.6.1, #236) : Ubuntu Pro de la VM est rattaché au compte Ubuntu One `j.rasolofono@bbass.fr` (gérant du cabinet), pas à une adresse générique du cabinet. Passer l’abonnement sur un compte au nom du cabinet pour qu’il ne dépende pas d’une personne ; modalités à transmettre par le cabinet. Mettre à jour le guide [Installation du serveur du Copilote BBASS](../../installation/serveur.mdx) en même temps.

### Déploiement automatique (pull périodique ou runner à Castries)

Constat (grilling 1.6.1) : la mise à jour reste déclenchée par l’admin (commande ou redémarrage). Un timer qui applique seul la dernière Promotion, ou un runner GitHub auto-hébergé dans le LAN, rendrait le CD réellement continu. **Déclencheur** : la cadence des versions rend le geste manuel pénible.

### Mise en production définitive (checklist de livraison)

À faire quand la solution est remise au cabinet pour de bon, pour qu’il en reste une trace :

- Activer **Ubuntu Pro** (gratuit jusqu’à 5 machines ; correctifs jusqu’en 2036) avec un compte **Ubuntu One au nom du cabinet** (adresse générique, double authentification). Ce compte ne donne aucun accès à la machine ; une fuite permettrait au pire de détacher la VM des correctifs étendus. Revérifier à ce moment que l’offre gratuite couvre toujours l’usage commercial.
- Ranger dans le **gestionnaire de mots de passe du cabinet** : identifiants Ubuntu One, valeurs générées par l’installateur (mots de passe Postgres, `VM_ADMIN_KEY` de chaque Environnement), emplacement des clés maîtres.
- Vérifier que l’admin du cabinet a joué seul, avec le guide, une mise à jour et une Promotion.

### Bug — « Écrit dans Moduléo. » après une suppression (#263)

**Constat :** au second passage des tests humains V1.5.2 (#206, scénario 17), la confirmation d'une suppression de temps passé affiche « Écrit dans Moduléo. » sur la carte « Sera supprimé » ; l'élément est bien supprimé, mais la phrase dit « écrit ».

**Reproductibilité :** demander « Supprime mon temps passé du <date> sur l'affaire <numéro> », puis Confirmer. Systématique (même phrase pour toute méthode).

**Impact :** formulation ambiguë après une suppression ; aucune donnée fausse.

**Cause probable :** une seule phrase fixe après confirmation, quelle que soit la méthode (spec 1.5.2 : « Écrit dans Moduléo »).

**À corriger :** phrase selon la méthode : « Créé dans Moduléo. », « Modifié dans Moduléo. », « Supprimé de Moduléo. », sur la carte et dans le résultat d'outil vu par le modèle ; spec à amender en même temps.

**Hors périmètre :** Aucun.

**Suivi :** [#263](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/263) (`bug`, capture en pièce jointe). Trouvé dans : 1.5.2 · Contexte : test humain · Date : 2026-10-29 · Priorité : non prioritaire.

### Bug — Moduléo supprime le téléphone vide d'un contact quand on lui en ajoute un (#264)

**Constat :** au second passage des tests humains V1.5.2 (#206, scénarios 5 et 6), CLIENT EXEMPLE 11 avait un téléphone n°160 vide ; après un seul `POST moduleo/telephone` de BBASS (id renvoyé 161), la liste du contact est `[161]` et le n°160 n'existe plus. Chaque contact de test semble avoir un tel téléphone vide.

**Reproductibilité :** sur le serveur de test, lire les téléphones d'un contact qui n'a qu'un téléphone vide, créer un téléphone depuis le chat et confirmer, relire. Vu une fois.

**Impact :** aucun a priori pour le collaborateur (téléphone vide) ; un id de téléphone lu avant une création peut ne plus exister après.

**Cause probable :** comportement du serveur Moduléo (Kipaware), pas de BBASS ; voulu ou non, à confirmer.

**À corriger :** demander à Kipaware si c'est voulu et dans quels cas (e-mails, adresses ?) ; si oui, le noter dans le README du module Moduléo (écriture), sinon le signaler. Rien à changer dans BBASS tant que ce n'est pas confirmé.

**Hors périmètre :** ids des téléphones absents des fiches (#257).

**Suivi :** [#264](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/264) (`bug`). Trouvé dans : 1.5.2 · Contexte : test humain · Date : 2026-10-29 · Priorité : non prioritaire.
