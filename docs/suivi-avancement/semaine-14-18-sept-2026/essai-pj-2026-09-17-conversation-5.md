# Essai fonctionnel pièces jointes — 17 septembre 2026 (matin, conversation #5)

Déplacé depuis `docs/suivi-avancement/essai-pj-2026-09-17.md`.  
Compte `admin`, conversation **#5**, titre *Pièces jointes : utiles et pratiques*.  
Créée à 06:32:20 UTC, dernière activité 06:38:43 UTC.  
Cette conversation a ensuite été **supprimée** de la base (essai suivant : conversation #6).  
7 tours (14 messages persistés). Les appels d’outils **ne sont pas enregistrés en base** : ce qui suit les infère à partir du code (fenêtre de 3 messages) et du contenu des réponses.

## Ce qui a réellement fonctionné (pipeline)

| Pièce jointe | Fichier | Taille | Analyse | `echec_analyse` | Disque |
| --- | --- | --- | --- | --- | --- |
| **#1** liée au message 25 | `gd_1 (14).pdf` (Cerfa récépissé DT) | 352 Ko | OCR Mistral (`/v1/ocr`), 1839 caractères extraits | `false` | `admin/5/1-gd_1 (14).pdf` |
| **#2** liée au message 29 | capture d’écran IGN Teyran (PNG) | 711 Ko | Vision chat (`image_url` + JSON), 834 caractères | `false` | `admin/5/2-Capture d'écran 2026-02-18 154610.png` |

Les deux fichiers sont bien rattachés à la conversation, `message_id` renseigné, pas d’orphelin `_sans_conversation`.  
L’extraction a donc **réussi**. Le mécontentement vient de **ce que le modèle de chat en fait ensuite**, pas d’un échec HTTP ni d’un `echec_analyse`.

## Règles à avoir en tête (pourquoi le chat « oublie »)

1. Le texte OCR / vision n’est **jamais** un message visible dans l’historique. Il n’est injecté en `system` **que le tour où** `piece_jointe_id` est envoyé avec le message.
2. Les tours suivants n’ont que : résumé glissant + profil de travail + **3 derniers messages**.
3. L’outil `obtenir_contenu_piece_jointe` n’est déclaré **que** si une pièce jointe déjà liée a son message **hors** de cette fenêtre. Le schéma de l’outil ne donne **ni le nom du fichier, ni la liste des ids** : le modèle doit inventer ou se souvenir d’un entier `piece_jointe_id`.
4. Un appel d’outil n’apparaît pas dans `messages` : on ne voit que la réponse finale.

## Chronologie point par point

### 1. 06:32:20 — Création de la conversation (sans fichier)

- **Utilisateur :** « J'adore les pièces jointes dans les mails »
- **Appels Mistral :** chat (réponse) + chat (titrage). **Pas d’OCR, pas de vision, pas d’outil.**
- **Assistant :** banalités sur les PJ d’e-mail, demande le type de fichier préféré.
- **Effet :** le fil part sur *parler des pièces jointes*, pas *analyser un document*. Le titre figé le confirme.

### 2. 06:33:30 puis 06:33:36 — Upload PDF + premier message porteur

- Upload sur `POST /conversations/5/pieces-jointes` (conversation déjà existante). OCR **avant** l’envoi du message.
- **OCR (fidèle dans l’ensemble) :** récépissé Cerfa, cases **Récépissé de DT cochée** (pas DICT, pas conjointe), destinataire Bottraud François, 205 avenue des Gardians, 34160 Castries, travaux ZA de l’Ancien Pont à Frontignan, date 26/05/2026, exploitant Agence technique départementale / SOGELINK, « au moins un réseau concerné ». Artefacts OCR : `N°14435'04`, `3.4.1.6.0 Castries`, numéros à points, texte coupé à « Modification ou extension de nos réseaux / ouvrages » (verso probablement manquant).
- **Utilisateur :** il ne comprend pas un document, il l’envoie pour qu’on le lui explique, « ça m’est déjà arrivé avec ce pdf ».
- **Fenêtre :** messages 23–24 seulement. `PieceJointe #1.message_id` encore `NULL` au moment du calcul des tools → **outil non déclaré**.
- **Injection :** `contenu_extrait` du PDF en message `system` pour **cet** appel uniquement.
- **Assistant :** a **vu** le PDF (ministère, DT/DICT, cases, « Éléments généraux de réponse ») mais répond surtout en *conseiller* (ChatPDF, Scholarcy, Google Lens) au lieu d’expliquer le récépissé. Déjà une erreur de case : il parle de « Récépissé de DT/DICT conjointe » alors que l’OCR a **DT seul**.

**Tool calling : non.**

### 3. 06:34:23 — « ce pdf que je t'ai envoyé il dit quoi exactement »

- **Fenêtre :** 24, 25, 26. Le message porteur du PDF (25) est **encore dans** la fenêtre → **outil non déclaré**.
- Le `system` OCR **n’est plus renvoyé**. Le modèle n’a que le texte utilisateur + sa propre réponse précédente (partielle et déjà un peu fausse).
- **Assistant :** « analyse » générique du régime DT/DICT (délai 1 mois, amende 30 000 €, clôture près d’un compteur, ChatPDF encore). Ces chiffres **ne sont pas** dans l’extrait OCR. Il n’utilise presque plus les champs concrets (Bottraud, Frontignan, ZA…).

**Tool calling : non** (et il n’aurait pas pu : l’outil n’était pas proposé).

### 4. 06:36:59 puis 06:37:05 — Upload image + message porteur

- Vision **réussie**, `echec_analyse = false`. Extrait : toponymes autour de **Teyran** (la Fouillade, les Grèzes, Angerly, la Boissière, Mas du Hautbois, etc.), routes, bois, hydrographie.
- Erreurs d’extraction vision (comparé au PNG réel) : « Fontarèc » au lieu de Fontarède ; « 4,7°C / échelle de température » alors que c’est un **point coté 47** (IGN) ; rose des vents douteuse ; toponymes manquants (Château d’eau, Arènes, Gymn., P parking).
- **Fenêtre :** 26, 27, 28. PDF (message 25) **hors fenêtre** → **outil déclaré** (`obtenir_contenu_piece_jointe`). Image injectée en `system` ce tour-ci.
- **Utilisateur :** expliquer « cette image » qu’un ami lui a demandée.
- **Assistant :** demande **d’envoyer l’image**, tout en citant déjà « la capture d’écran de Teyran » — donc il a **vu** l’extrait vision, mais le traite comme un exemple passé, pas comme le fichier de **ce** message.

**Tool calling : très probablement non.** Une résolution d’outil aurait renvoyé le PDF ; la réponse ne recolle pas le récépissé. L’extrait image était déjà dans le `system` : pas besoin d’outil pour l’image.

### 5. 06:37:46 — « décris l'image que je t'ai envoyé »

- **Fenêtre :** 28, 29, 30. Image (message 29) **encore dans** la fenêtre → extrait vision **non réinjecté**. PDF toujours hors fenêtre → **outil déclaré**.
- **Assistant :** dump détaillé du **récépissé** (Bottraud, Castries, Frontignan, ZA de l’Ancien Pont, ATD, case réseau concerné). Ces champs n’étaient plus dans les 3 derniers messages ni dans le résumé à ce niveau de détail : ils viennent de `contenu_extrait` du PDF.

**Tool calling : oui, très probable — `obtenir_contenu_piece_jointe` avec `piece_jointe_id = 1` (le PDF), pas l’image.**  
Le modèle a choisi le mauvais document. Rien dans l’outil ne dit « id 1 = PDF, id 2 = PNG ».

### 6. 06:38:25 — « je ne te parle pas du récépissé, je te parle de l'image »

- **Fenêtre :** 30, 31, 32. PDF **et** image hors fenêtre → **outil déclaré** (les deux ids sont éligibles).
- **Assistant :** s’excuse et redemande **d’envoyer / coller l’image**. Pas de toponymes IGN, pas de 4,7 °C, pas de Teyran.

**Tool calling : non** (ou appel ignoré / id invalide). S’il avait résolu l’id 2, la réponse finale aurait collé à la carte.

### 7. 06:38:43 — « je te l'ai déjà envoyé dans les messages précédents »

- **Fenêtre :** 32, 33, 34. Outil toujours **déclaré**.
- **Assistant :** parle enfin de Mouline / la Fouillade / les Grèzes / Teyran, mais **mélange** avec Frontignan et la ZA de l’Ancien Pont (le PDF). Ton hypothétique (« je suppose que c’est une vue satellite »). N’utilise pas le détail vision (point 47, Fontarède, château d’eau, parking).

**Tool calling : incertain, plutôt non pour l’image.** Les toponymes cités sont déjà dans le **résumé glissant** (mention courte). Un vrai retour d’outil id 2 aurait donné une description plus proche de l’extrait (et n’aurait pas recollé Frontignan).

## Résumé glissant et profil (après le dernier tour)

- **`resume_contexte` (1360 car.) :** mélange volontairement PDF Cerfa et carte Teyran ; dit que l’utilisateur a « réitéré » la demande d’analyse d’image. C’est cohérent avec la fin du fil, pas avec un oubli total.
- **`profils_travail.admin` (2897 car.) :** le modèle s’est **auto-entraîné** sur ses propres ratés : « analyses visuelles en 30 secondes », « tolérance nulle », « ChatPDF / autonomie ». Ça renforce le ton coach / outils externes au lieu de coller au fichier. **Ce profil a survécu à la suppression de la conversation** et a pesé sur l’essai #6.

## Synthèse : pourquoi le résultat est peu satisfaisant

1. **Le pipeline d’analyse a marché** (OCR + vision, fichiers sur disque, lignes `PieceJointe` correctes).
2. **Le premier message sans fichier a biaisé tout le fil** (sujet = e-mails / PJ, pas le Cerfa ni la carte).
3. **Le contenu extrait n’est vivant qu’un tour** ; dès le message suivant, le chat n’a plus le document, sauf outil.
4. **Un tool call a très probablement eu lieu, mais sur le PDF** alors que tu demandais l’image — et l’outil ne décrit pas les pièces disponibles.
5. **Les tours 4, 6 (et 7 en pratique) n’ont pas utilisé l’outil image** : le modèle redemande le fichier comme un chatbot grand public, alors que l’extrait est déjà en base.
6. **Hallucinations / confusions :** DT vs DT/DICT conjointe ; amende / délais hors document ; Frontignan recollé sur une carte de Teyran ; 47 IGN lu comme 4,7 °C à l’extraction.

Les tool calls ne pourront être affirmés à 100 % que lorsqu’ils seront journalisés (id d’outil, `piece_jointe_id`, nombre d’allers-retours). Ici : **0 certain, 1 très probable (tour 5, PDF), 0 réussi sur l’image.**
