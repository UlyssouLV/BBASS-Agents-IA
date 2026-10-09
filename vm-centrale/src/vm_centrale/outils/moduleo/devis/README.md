# chercher_devis_moduleo

Retrouve des devis Moduléo par **texte** ou par **filtres en noms** quand le modèle le décide, avec les **totaux calculés par la VM** sur tout ce qui est trouvé. Règles communes (éligibilité, statut, panne / refus, lectures, inspecteur) : [`../README.md`](../README.md).

**Droit.** « Devis, factures et avoirs › Consulter les devis » (garde des droits, `moduleo/droits/routes.json`) : sans lui, l'outil n'est pas proposé, et un appel quand même reçoit la phrase fixe du garde, sans lecture.

**Paramètres**, combinés en « et » :

- `texte` : un mot du numéro ou de l'objet.
- `emis` : `true` (émis) ou `false` (pas encore émis), transmis en `emis=true|false`.
- `date_{emission,reponse}_{min,max}` : AAAA-MM-JJ ou JJ/MM/AAAA, transmis en AAAA-MM-JJ (`dateEmissionMin`…).
- `service` : tous les services qui portent ce nom (`idsService`).
- `responsable`, `redacteur` : un utilisateur (`idsResponsable`, `idsRedacteur`).
- `affaire` : un numéro d'affaire (`cogeo/affaire/numeroAffaire`). La recherche de devis n'a pas de filtre d'affaire : les devis de l'affaire (`cogeo/affaire/{id}/devis`), croisés avec la recherche s'il y a d'autres filtres.

`nb_max`, 5 par défaut, ramené entre 1 et 10 : il ne borne que les fiches, jamais les totaux. Pas de filtre d'état : les valeurs d'`Etat` d'un devis ne sont pas encore relevées, et Moduléo ignorerait un nom inconnu.

**Sans critère** (`{}`, `{"nb_max": 10}`) : les devis émis ces 30 derniers jours (`emis=true`, `dateEmissionMin` = aujourd'hui − 30 jours), et le résultat le dit : « 12 devis émis depuis le 09/09/2026 (30 derniers jours), total … ». Dès qu'un critère est donné, la période par défaut ne s'applique plus.

**Noms non résolus.** Date illisible, numéro d'affaire inconnu, nom qui ne désigne rien, plusieurs utilisateurs : une phrase au modèle, **aucune recherche**, aucune lecture enregistrée, terminée par « Aucune lecture faite dans Moduléo : n'invente aucun devis, demande au collaborateur un numéro, un nom ou une période. ». Trace : `non_resolu`.

**Déroulé.**

1. Noms → ids (`moduleo/resolution.py`, `id_affaire` de `../commun.py`).
2. Recherche `cogeo/devis?texte=…` (ids), ou devis de l'affaire.
3. **Tous** les devis trouvés : `cogeo/devis/multi?ids=` par lots de 200 (limite de la route), triés du plus récent au plus ancien (date d'émission, de création pour un devis non émis, puis id).
4. Les `nb_max` premiers : leurs affaires (`cogeo/affaire/multi`, client de l'affaire), responsable et rédacteur (`moduleo/utilisateur/{id}`), client (`cogeo/contact/multi`). Le client est celui de l'affaire : le destinataire du devis (`cogeo/destinataire`) exige le droit des factures.
5. Synthèse (`synthese_devis`, `moduleo/fiches.py`) : nombre, total HT et TTC de tous les devis trouvés.

**Au modèle.** La synthèse en tête (« 7 devis trouvés (texte « Bornage »), total 700,00 € HT, 840,00 € TTC. Les 5 plus récents affichés, précise la recherche. »), puis une Fiche Moduléo par devis (`fiche_devis` : numéro, objet, affaire, client, dates de création, d'émission ou « non émis », de réponse, d'expiration, état s'il n'est pas 0, en chiffre tant qu'il n'est pas relevé, responsable, rédacteur, montants HT / TTC). Aucun : « Aucun devis Moduléo ne correspond à cette recherche. », ou « Aucun devis émis dans Moduléo depuis le JJ/MM/AAAA (30 derniers jours). » sans critère.

**Lectures.** La synthèse est une lecture (référence « devis émis du 09/09/2026 au 09/10/2026 », ou « devis (<critères>) »), avant celles des fiches (« devis D-2026-042 ») : un total cité par le modèle reste dans la réponse et cite la synthèse, un total inventé est retiré par le garde-fou chiffres. Questions couvertes par gabarit : objet, montant, « Où en est le devis … ? », affaire et client, suivi ; « Combien de devis … ? », « Quel est le montant total des devis … ? ».

**Inspecteur** (`outil:chercher_devis_moduleo`) : arguments, `routes`, `trouvees`, `synthese`, `fiches`, `non_resolu`, `erreur` ou `garde_des_droits`.

**Depuis.** 1.5.1 (#189). À confirmer à l'essai réel : valeurs d'`Etat` d'un devis, sens exact de `emis`, ordre et format des dates attendus par l'API.

Code : `outil.py`.
