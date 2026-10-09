# chercher_temps_passes_moduleo

Retrouve des temps passés Moduléo par **période** ou par **filtres en noms** quand le modèle le décide, avec les **totaux d'heures calculés par la VM** sur tout ce qui est trouvé : général, par collaborateur, par code activité. Règles communes (éligibilité, statut, panne / refus, lectures, totaux, inspecteur) : [`../README.md`](../README.md).

**Droit.** « Temps passés et frais des temps passés › Consulter les temps passés et les frais des temps passés des autres collaborateurs » (garde des droits, `moduleo/droits/routes.json`) :

- avec lui, les temps de tous les collaborateurs ;
- sans lui, **seulement les temps de l'utilisateur Moduléo lié au compte** (`rattachements_moduleo.id_utilisateur_moduleo`, `affecter_groupes_moduleo.py --utilisateur`) : section `siens` de `routes.json`. Le garde n'autorise la recherche que si `idsUtilisateurs` ne désigne que cet utilisateur, et relit l'`IdUtilisateur` de chaque temps reçu par `cogeo/tempspasse/multi` (un serveur qui ignorerait le filtre ne livre rien). Sans `collaborateur`, l'outil envoie l'id du compte et le résultat dit « vos temps seulement » ; un autre collaborateur demandé part tel quel et reçoit la phrase fixe du garde (« Votre compte n'a pas le droit Moduléo « Consulter les temps passés … des autres collaborateurs ». Aucune lecture n'a été faite… »), trace `garde_des_droits` ; seule la résolution de son nom (route libre) a été lue ;
- sans lui et sans lien : l'outil n'est pas proposé, et un appel quand même reçoit la même phrase, sans lecture.

**Prix** (vérification par champ, #188) : « Prix de vente » avec « Affaires, groupes et archivage › Voir l'onglet prix de revient › Voir le prix de vente des temps passés », « Prix de revient » avec « … › Voir le prix de revient des temps passés » ; sans le sous-droit, la ligne devient « Prix de vente : non autorisés pour votre compte ». Affichés tels que lus (`PrixVenteCollaborateur`, `PrixRevientCollaborateur`), jamais additionnés.

**Paramètres**, combinés en « et » :

- `date_{min,max}` : AAAA-MM-JJ ou JJ/MM/AAAA, transmis en AAAA-MM-JJ (`dateMin`, `dateMax`).
- `collaborateur` : un utilisateur (`chercher_utilisateur`, `idsUtilisateurs`).
- `code_activite` : nom ou code d'un code activité (`chercher_code_activite`, `moduleo/resolution.py`, `idCodeActivite`). Codes lus dans Moduléo (`cogeo/codeactivite`, puis `cogeo/codeactivite/{id}`, routes libres) : un code créé dans Moduléo est reconnu sans changer le code. Nom ou code exact (casse et accents indifférents), sinon le seul qui contient le nom ; plusieurs : `NomNonResolu` avec les candidats.
- `affaire` : un numéro d'affaire (`id_affaire`, `../commun.py`, `idAffaire`).

`nb_max`, 5 par défaut, ramené entre 1 et 10 : il ne borne que le détail, jamais les totaux.

**Sans critère** (`{}`, `{"nb_max": 10}`) : les 7 derniers jours (`dateMin` = aujourd'hui − 7 jours, `dateMax` = aujourd'hui), et le résultat le dit : « 14 temps passés saisis du 02/10/2026 au 09/10/2026 (7 derniers jours), total … ». Dès qu'un critère est donné, la période par défaut ne s'applique plus.

**Noms non résolus.** Date illisible, numéro d'affaire inconnu, collaborateur ou code activité qui ne désigne rien ou plusieurs : une phrase au modèle, **aucune recherche**, aucune lecture enregistrée, terminée par « Aucune lecture faite dans Moduléo : n'invente aucun temps passé, demande au collaborateur un nom, une affaire ou une période. ». Trace : `non_resolu`.

**Déroulé.**

1. Noms → ids.
2. Recherche `cogeo/tempspasse?dateMin=…` (ids), sans `nbMaxResultat`.
3. **Tous** les temps trouvés : `cogeo/tempspasse/multi?ids=` par lots de 200 (`lire_par_lots`), triés du plus récent au plus ancien (date, puis id).
4. Noms des collaborateurs (`moduleo/utilisateur/{id}`) et des codes activité (`cogeo/codeactivite/{id}`) de **tous** les temps (totaux) ; numéros d'affaire des seules lignes affichées (`cogeo/affaire/multi`).
5. Synthèse (`synthese_temps_passes`, `moduleo/fiches.py`) : nombre de lignes, total d'heures, par collaborateur et par code activité (le plus d'heures d'abord ; « sans code activité » pour une ligne sans code).

**Au modèle.** La synthèse en tête (« 3 temps passés trouvés (affaire 2024-123), total 7,5 h. Par collaborateur : Jean Martin 6 h, Sophie Bernard 1,5 h. Par code activité : Relevé terrain 6 h, Bureau 1,5 h. Le plus récent affiché, précise la recherche. »), puis une Fiche Moduléo par ligne (`fiche_temps_passe` : date, collaborateur, affaire, code activité, heures, kilomètres, lieu, commentaire, prix). Aucun : « Aucun temps passé Moduléo ne correspond à cette recherche. », ou « Aucun temps passé saisi dans Moduléo du JJ/MM/AAAA au JJ/MM/AAAA (7 derniers jours). » sans critère.

**Lectures.** La synthèse est une lecture (référence « temps passés du 02/10/2026 au 09/10/2026 », ou « temps passés (<critères>) »), avant celles des lignes (« temps passé du 07/10/2026, Jean Martin, affaire 2024-123 ») : un total cité reste dans la réponse et cite sa lecture, un total inventé est retiré par le garde-fou chiffres. Questions couvertes par gabarit : « Combien d'heures dans les … ? », « … par collaborateur … ? », « … par code activité … ? » ; « Combien d'heures pour le temps passé … ? », « Quel code activité pour le … ? ».

**Inspecteur** (`outil:chercher_temps_passes_moduleo`) : arguments, `routes`, `trouvees`, `synthese`, `fiches`, `non_resolu`, `erreur` ou `garde_des_droits`.

**Depuis.** 1.5.1 (#191). À confirmer à l'essai réel : sens des prix (taux horaire ou prix de la ligne), format des dates attendu par l'API, limite éventuelle de la recherche sans `nbMaxResultat`.

Code : `outil.py`.
