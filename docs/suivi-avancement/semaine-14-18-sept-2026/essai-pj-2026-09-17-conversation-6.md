# Essai fonctionnel pièces jointes — 17 septembre 2026 (2e, conversation #6)

Compte `admin`, conversation **#6**, titre *Pièces jointes : mode d'emploi*.  
Créée à 08:10:51 UTC, dernière activité 08:17:22 UTC.  
9 tours (18 messages). Même PDF que l’essai #5, **autre image** (vue aérienne « PROJET »).  
Les appels d’outils ne sont **pas** en base : inférés (fenêtre de 3 messages + contenu des réponses).

À comparer avec [essai conversation #5](essai-pj-2026-09-17-conversation-5.md) (même journée, conversation ensuite supprimée). Le **profil de travail `admin` n’a pas été réinitialisé** : il arrive déjà chargé des consignes du premier essai (« tolérance nulle » pour une image floue, analyse en 30 s, etc.).

## Pipeline (toujours OK)

| Pièce jointe | Fichier | Taille | Analyse | `echec_analyse` | Disque |
| --- | --- | --- | --- | --- | --- |
| **#3** → message 39 | `gd_1 (14).pdf` | 352 Ko | OCR, 1839 car. (même texte que #5) | `false` | `admin/6/3-gd_1 (14).pdf` |
| **#4** → message 45 | capture 2026-01-05 (PNG) | 761 Ko | Vision, 464 car. | `false` | `admin/6/4-Capture d'écran 2026-01-05 112655.png` |

Image réelle : vue aérienne **nette** d’un quartier pavillonnaire (toits, piscines, route, passage piéton), rectangle rouge + texte **PROJET** sur une parcelle.  
Extrait vision, fidèle et plus sobre que Teyran : « vue aérienne », bâtiments / arbres / routes, rectangle rouge, mot `PROJET`, capture d’un outil de cartographie. Pas d’hallucination 4,7 °C. Rien sur les piscines ni le passage piéton.

## Améliorations par rapport à l’essai #5

1. **Dès le tour PDF**, le modèle **explique le récépissé** (Bottraud, Frontignan, ZA, date, ATD/Sogelink, réseau concerné) au lieu de renvoyer vers ChatPDF.
2. Les questions suivantes (« à quoi ça sert », « en résumé ») **restent sur le document** : plus de « renvoie-moi le PDF ».
3. L’extrait image est **plus prudent** (moins d’inventions IGN).
4. Après ta correction sur le lien entre PJ, le modèle **admet** qu’aucun lien n’est fiable (tour 9).
5. Réponses PDF plus courtes et structurées.

## Ce qui reste faux / incohérent

1. Premier message **sans fichier** → titre *mode d’emploi*, l’assistant explique comment joindre un fichier (icône trompeuse type ChatGPT).
2. Toujours **DT/DICT mélangés** ; le récépissé est traité comme une **autorisation / « passeport pour creuser »** alors que l’OCR dit seulement : DT coché, au moins un réseau concerné, catégorie vide.
3. **Sanctions / explosion / interdiction de commencer** : hors extrait.
4. Image : l’extrait est **exploitable** (`echec_analyse = false`) ; le chat dit **inutilisable / floue / aucun repère**. Le PNG ne l’est pas. Le profil (« tolérance nulle, signaler le flou ») pousse au refus.
5. Tu dois **insister** (couleurs, vue du ciel) pour qu’il raisonne ; il répond alors en **conditionnel** (« si c’était net ») au lieu de lire l’extrait déjà en base.
6. Question « est-ce lié à l’autre PJ ? » → **oui, confirmation** (rectangle rouge = ZA de l’Ancien Pont à Frontignan). C’est exactement l’erreur de raisonnement que tu as reprise.
7. Le profil s’aggrave encore : « systématise une vérification du lien entre pièces jointes » — il apprend à **forcer** le lien que tu viens de lui interdire.

## Chronologie

### 1. 08:10:51 — Création sans fichier

- **Utilisateur :** « J'aimerais te donner des pieces jointes et que tu me les expliques »
- Chat + titrage. **Pas d’OCR, pas d’outil.**
- Assistant : tutoriel d’upload (glisser, icône trombone, pas de `.exe`).

**Tool calling : non.**

### 2. 08:11:51 / 08:11:56 — PDF

- OCR identique à #5 (DT coché, pas conjointe ; texte coupé au verso).
- **Utilisateur :** document fourni qu’il est censé connaître et qu’il ne connaît pas.
- Fenêtre : 37–38. `message_id` encore `NULL` → **outil non déclaré**. Injection `system` de l’OCR.
- **Assistant :** analyse directe du Cerfa (points concrets). Reste : « DT/DICT », « propriétaire du projet », « hors zone », sanctions.

**Tool calling : non.** Amélioration nette vs tour PDF de #5.

### 3. 08:12:22 — « a quoi sert ce document ? »

- Fenêtre : 38, 39, 40. Message PDF **encore dedans** → **pas d’outil**, pas de réinjection OCR.
- **Assistant :** « autorisation obligatoire », « passeport pour creuser », « sans lui interdiction ». Utile comme vulgarisation, **inexact** au regard du seul extrait.

**Tool calling : non.**

### 4. 08:12:39 — « en résumé »

- Fenêtre : 40, 41, 42. Message 39 **hors fenêtre** → **outil déclaré**.
- **Assistant :** une phrase (accusé de réception + Sogelink). Cohérent avec le tour 3, pas un re-dump OCR.

**Tool calling : probablement non.**

### 5. 08:13:40 / 08:13:44 — Image + « explique ce que l’on voit »

- Vision OK, extrait : vue aérienne, `PROJET`, rectangle rouge.
- Fenêtre : 42, 43, 44. PDF hors fenêtre → **outil déclaré**. Image injectée en `system`.
- **Assistant :** « image inutilisable », floue, aucun nom de rue, rectangle rouge sans intérêt. **Contredit l’extrait** (et le PNG).

**Tool calling : probablement non** (l’image est déjà dans le `system` ; la réponse n’exploite ni l’extrait ni le PDF).

### 6. 08:14:17 — « tu n’as pas une petite idée ? »

- Fenêtre : 44, 45, 46. Image **encore dans** la fenêtre → extrait **non** réinjecté. Outil PDF seulement.
- **Assistant :** « aucune idée », redemande une version nette / une adresse.

**Tool calling : non pour l’image** (encore dans la fenêtre). PDF non ressorti.

### 7. 08:15:08 — couleurs / vue du ciel, hypothèses

- Fenêtre : 46, 47, 48. **Les deux PJ hors fenêtre** → outil déclaré pour 3 et 4.
- **Assistant :** tableau générique rouge/vert/gris/bleu/marron, « si l’image était nette », recoller DT/DICT et « zone en rouge = travaux ». N’utilise pas `PROJET` ni « vue aérienne » de l’extrait.

**Tool calling : non** (ou ignoré). Un retour d’outil id 4 aurait collé à l’extrait.

### 8. 08:15:45 — « est-ce que ça a un lien avec l’autre PJ ? »

- Fenêtre : 48, 49, 50. Outil **déclaré** (3 et 4).
- **Assistant :** **« Oui, les deux documents sont liés. »** Dump OCR (Bottraud, Castries, Frontignan, ZA, 26/05/2026) + nom du PNG + rectangle `PROJET`. Hypothèse **forte** : le rectangle = ZA de l’Ancien Pont.

**Tool calling : très probable pour le PDF (id 3)** — champs trop précis pour n’être que dans les 3 derniers messages. Image : nom de fichier + `PROJET` pouvaient venir du résumé ; lien géographique **inventé**.

### 9. 08:17:22 — correction utilisateur

- Tu refuses le lien sans confirmation ; au mieux une hypothèse.
- Fenêtre : 50, 51, 52. Outil toujours déclaré.
- **Assistant :** reconnaît l’erreur, reformule en « pourrait / rien ne le prouve », redemande GPS / image plus nette / contexte.

**Tool calling : pas nécessaire.** Amélioration : il cède sur la confirmation abusive, tout en gardant l’hypothèse Frontignan.

## Résumé glissant et profil (fin du fil)

- **`resume_contexte` (1369 car.) :** image « floue », rectangle `PROJET`, relance de l’utilisateur, **ne mentionne plus** le dump Frontignan du tour 8. Dit que l’admin « confirme sa maîtrise du récépissé » — ce n’est pas ce que disent tes messages.
- **`profils_travail.admin` (~4,5 ko, maj 08:17:22) :** héritage #5 **plus** : explication opérationnelle des docs admin, interprétation même si flou, **et** « vérification systématique du lien entre PJ ». Ce dernier delta est le contraire de ta consigne du tour 9.

## Tool calling (inféré)

| Tour | Outil proposé ? | Appel probable |
| --- | --- | --- |
| 1 création | non | non |
| 2 PDF | non | non |
| 3 à quoi ça sert | non | non |
| 4 en résumé | oui (PDF hors fenêtre) | non |
| 5 image | oui (PDF) + injection vision | non |
| 6 petite idée | oui (PDF) | non |
| 7 couleurs | oui (PDF + image) | non |
| 8 lien entre PJ | oui (les deux) | **PDF oui** ; image incertain |
| 9 correction | oui | non |

Soit **un tool call très probable (PDF, tour 8)**, aucun qui serve réellement l’image.

## Synthèse

Le pipeline (OCR, vision, disque, rattachement) tient. Le chat **s’améliore** sur le PDF dès le premier tour porteur. Il **pèche encore** sur l’image (refus alors que l’extrait est bon), sur le **lien forcé** entre documents, et sur un **profil de travail** qui accumule les mauvaises leçons d’un essai à l’autre.
