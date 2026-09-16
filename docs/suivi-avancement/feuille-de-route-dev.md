# Feuille de route dev

Ordre des **prochaines versions** produit, plus les sujets encore sans numéro.

Ce n’est **pas** une spec (ça vient après « Ouvre la version »).

## Déjà livré

- **1.0.x** — Socle : comptes, connexion, chat, relais Mistral, session persistée (keyring), LAN Castries.
- **1.1.0** — Comptes administrateurs, multi-pôles, mot de passe généré / changement forcé, révocation, affichage pôle/agence dans le chat.

Le chat actuel envoie **un seul message** à Mistral à chaque tour : pas d’historique, pas de fils.

## Prochaine : 1.1.1 — Persistance des conversations

Travail **de recherche d’abord**, puis architecture (et implémentation une fois le grill / la spec faits).

**Objectif.** Des fils de discussion qui survivent au rechargement, à la relance du poste, éventuellement à un autre poste du même compte : historique renvoyé pour un vrai multi-tours.

**Recherche Mistral.**

- Voir ce que Mistral propose pour une conversation persistante (API **Agents & Conversations**, ou autre) : ce qui est stocké chez eux, durée de vie, coût, confidentialité, identifiant de conversation à reprendre.
- L’appel actuel (`POST /v1/chat/completions`) est **sans état** : si on reste sur cet endpoint, **on** doit stocker les messages (`user` / `assistant`, plus tard `system`) et les renvoyer à chaque tour.

**Si on ne passe pas par le stockage Mistral.** Concevoir l’architecture côté cabinet : où vivent les fils (VM centrale vs poste), modèle (compte, fil, messages, dates), qui peut lire / supprimer, un fil vs plusieurs.

## Ensuite : 1.1.2 — Pièces jointes

Le schéma de données de la [1.1.1](../specs/v1.1.1-persistance-conversations.md) réserve déjà une table vide pour les pièces jointes (non exploitée). Cette version branche l'upload et l'exploitation réelle : ce que Mistral accepte comme document, formats, limites de taille, stockage côté VM centrale, envoi à Mistral.

**Recherche.**

- API/document Mistral : formats acceptés, limites de taille, comment un document est transmis dans un appel de chat (URL, upload dédié, encodage).
- Stockage du fichier lui-même côté VM centrale (base vs système de fichiers).

## Ensuite : 1.1.3 — Consommation (tokens, modèles, coûts)

S’appuie sur des **sessions de chat** datées (1.1.1).

**Objectif.** Garder en **base** la consommation : **totale** par compte **et par session**, avec les **dates**. Identifier clairement les **tokens** (entrée / sortie / total) **et le modèle** utilisé à chaque appel, pour en déduire **combien ça a coûté**. Rappel côté collaborateur que l’usage a un prix ; vue agrégée possible pour un compte administrateur.

**Recherche.**

- Enregistrer ce que Mistral renvoie déjà (`usage` sur les complétions) **avec** le nom du modèle réellement appelé (celui décidé par la VM).
- Agrégats : par compte, par session, par jour ; historique d’appels.
- **Tarification dynamique** : existe-t-il une **API Mistral** qui donne les prix par modèle (pour calculer le coût sans tarifs figés dans le code) ? Sinon : source officielle, mise à jour manuelle, ou approximation.

## Ensuite : 1.2.0 — Mise à jour de l’interface (poste)

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

## Plus tard (pas encore numéroté)

### Lanceur poste (exécutable, pywebview)

Un exécutable qui ouvre une fenêtre (pages web du backend local). Fermer la fenêtre ne tuerait pas le process : accès encore possible dans le navigateur (`localhost` du poste).

Recherche : empaquetage Windows, icône / démarrage du backend, barre d’état vs process invisible, mise à jour.

### Déploiement, CI/CD, retours utilisateurs

Déployer pour avoir des retours. Automatiser depuis GitHub Actions / un hébergeur type Netlify.

Contraintes déjà vues : pas de VM centrale physique pour un CD du relais ; Netlify (Internet) vs poste local + LAN ; Actions pour pytest seulement ; pilote sur une machine en attendant.
