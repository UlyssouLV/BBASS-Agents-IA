# chercher_planning_moduleo

Retrouve des tâches du planning Moduléo par **collaborateur** (participant), **période**, **activité** ou **mot-clé du libellé** quand le modèle le décide (« qui est sur le terrain jeudi ? », « que prévoit Martin cette semaine ? »). Règles communes (éligibilité, statut, panne / refus, lectures, synthèse, inspecteur) : [`../README.md`](../README.md).

**Droit.** Aucun droit de consultation dans Moduléo pour le planning (spec 1.5.1) : tout compte rattaché à un **groupe Planning** lit le planning (routes `planning/tacheplanning…` et `planning/utilisateurplanning/…` en `groupe_planning`, `moduleo/droits/routes.json`). Sans groupe Planning, l'outil n'est pas proposé ; appelé quand même, il reçoit la phrase fixe du garde (« Votre compte n'est rattaché à aucun groupe Moduléo Planning. Aucune lecture n'a été faite… »), trace `garde_des_droits` « refusé, groupe Planning manquant », sans lecture. Le numéro de l'**affaire liée** se lit par `cogeo/affaire/multi` (groupe Cogeo) : sans groupe Cogeo, il n'est pas lu et la fiche dit « Affaire : non autorisée pour votre compte ».

**Paramètres**, combinés en « et » :

- `date_{min,max}` : AAAA-MM-JJ ou JJ/MM/AAAA, transmis en AAAA-MM-JJ (`dateDebut`, `dateFin`). Un jour donné : les deux à ce jour.
- `collaborateur` : un utilisateur Moduléo (`chercher_utilisateur`), puis son utilisateur planning (`chercher_participant`, `planning/utilisateurplanning/utilisateur/{id}`), transmis en `idsParticipants`. Un utilisateur sans utilisateur planning : « Paul Durand n'est pas au planning Moduléo : recherche non lancée. ».
- `activite` : libellé d'une activité (`chercher_activite`, `moduleo/resolution.py`, `idActivite`). Activités lues dans Moduléo (`planning/activite`, route libre) : une activité créée dans Moduléo est reconnue sans changer le code. Libellé exact (casse et accents indifférents), sinon la seule qui contient le nom ; plusieurs : `NomNonResolu` avec les candidates.
- `mot_cle` : transmis tel quel en `libelle`.

`recupererTachesSupprimees` vaut toujours `false`. `nb_max`, 5 par défaut, ramené entre 1 et 10 : il ne borne que les fiches, jamais le nombre ni les participants de la synthèse.

**Sans critère** (`{}`, `{"nb_max": 10}`) : aujourd'hui et les 7 jours suivants (`dateDebut` = aujourd'hui, `dateFin` = aujourd'hui + 7 jours), et le résultat le dit : « 2 tâches au planning du 09/10/2026 au 16/10/2026 (aujourd'hui et les 7 jours suivants). ». Dès qu'un critère est donné, la période par défaut ne s'applique plus.

**Noms non résolus.** Date illisible, collaborateur ou activité qui ne désigne rien ou plusieurs, collaborateur absent du planning : une phrase au modèle, **aucune recherche**, aucune lecture enregistrée, terminée par « Aucune lecture faite dans Moduléo : n'invente aucune tâche, demande au collaborateur un nom, une activité ou une période. ». Trace : `non_resolu`.

**Déroulé.**

1. Noms → ids.
2. Recherche `planning/tacheplanning?libelle=…` (ids).
3. **Toutes** les tâches trouvées : `planning/tacheplanning/multi?ids=` par lots de 200 (`lire_par_lots`), dans l'ordre chronologique (début, puis id).
4. Participants de **toutes** les tâches (`resoudre_participants` : `planning/utilisateurplanning/{id}` puis `moduleo/utilisateur/{id}`) ; activités (`planning/activite`), matériel (`resoudre_equipements`, `moduleo/equipement/{id}`) et numéros d'affaire (`cogeo/affaire/multi`, avec un groupe Cogeo) des seules tâches affichées.
5. Synthèse (`synthese_planning`, `moduleo/fiches.py`) : nombre de tâches et participants avec leur nombre de tâches (le plus de tâches d'abord).

**Au modèle.** La synthèse en tête (« 2 tâches trouvées au planning (mot-clé lot B). Participants : Sophie Bernard (2 tâches), Jean Martin (1 tâche). La première affichée, précise la recherche. »), puis une Fiche Moduléo par tâche (`fiche_tache` : libellé, date et heures « 12/10/2026, 08:00 – 12:00 » ou « du 14/10/2026 08:00 au 15/10/2026 17:00 », participants, activité, matériel, affaire, lieu). Aucune : « Aucune tâche du planning Moduléo ne correspond à cette recherche. », ou « Aucune tâche au planning Moduléo du JJ/MM/AAAA au JJ/MM/AAAA (aujourd'hui et les 7 jours suivants). » sans critère.

**Lectures.** La synthèse est une lecture (référence « planning du 09/10/2026 au 16/10/2026 », ou « planning (<critères>) »), avant celles des tâches (« tâche « Bornage lot B » du 12/10/2026 »). Questions couvertes par gabarit : « Combien de tâches au … ? », « Qui est au … ? » ; « Quand a lieu la … ? », « Qui participe à la … ? », « Quelle activité / Quel matériel / Quelle affaire pour la … ? ».

**Inspecteur** (`outil:chercher_planning_moduleo`) : arguments, `routes`, `trouvees`, `synthese`, `fiches`, `non_resolu`, `erreur` ou `garde_des_droits`.

**Depuis.** 1.5.1 (#192). À confirmer à l'essai réel : `Participants` et `idsParticipants` en ids d'utilisateurs planning (et non d'utilisateurs Moduléo), sens de `dateDebut` / `dateFin` (chevauchement ou début dans la période), heures des tâches sans heure, tâches privées.

Code : `outil.py`.
