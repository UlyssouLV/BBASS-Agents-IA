# chercher_factures_moduleo

Retrouve des factures Moduléo par **texte** ou par **filtres en noms** quand le modèle le décide, avec leurs **échéances et règlements**, le **reste à payer** quand Moduléo permet de le déduire et les **totaux calculés par la VM** sur tout ce qui est trouvé. Règles communes (éligibilité, statut, panne / refus, lectures, totaux, inspecteur) : [`../README.md`](../README.md).

**Droit.** « Devis, factures et avoirs › Consulter les factures et les avoirs » (garde des droits, `moduleo/droits/routes.json`) : sans lui, l'outil n'est pas proposé, et un appel quand même reçoit la phrase fixe du garde, sans lecture. Toutes les routes lues (factures, destinataires, règlements, échéances, avoirs d'une facture) relèvent de ce droit.

**Paramètres**, combinés en « et » :

- `texte` : un mot du numéro ou de l'objet.
- `emise` : `true` (émise) ou `false` (pas encore émise), transmis en `emise=true|false`.
- `date_emission_{min,max}` : AAAA-MM-JJ ou JJ/MM/AAAA, transmis en AAAA-MM-JJ (`dateEmissionMin`, `dateEmissionMax`).
- `service` : tous les services qui portent ce nom (`idsService`).
- `responsable`, `redacteur` : un utilisateur (`idsResponsable`, `idsRedacteur`).
- `affaire` : un numéro d'affaire (`id_affaire`, `../commun.py`). La recherche de factures n'a pas de filtre d'affaire : les factures de l'affaire (`cogeo/affaire/{id}/factures`), croisées avec la recherche s'il y a d'autres filtres.

`nb_max`, 5 par défaut, ramené entre 1 et 10 : il ne borne que les fiches, jamais les totaux.

**Sans critère** (`{}`, `{"nb_max": 10}`) : les factures émises ces 30 derniers jours (`emise=true`, `dateEmissionMin` = aujourd'hui − 30 jours), et le résultat le dit : « 12 factures émises depuis le 09/09/2026 (30 derniers jours), total … ». Dès qu'un critère est donné, la période par défaut ne s'applique plus.

**Noms non résolus.** Date illisible, numéro d'affaire inconnu, nom qui ne désigne rien, plusieurs utilisateurs : une phrase au modèle, **aucune recherche**, aucune lecture enregistrée, terminée par « Aucune lecture faite dans Moduléo : n'invente aucune facture, demande au collaborateur un numéro, un nom ou une période. ». Trace : `non_resolu`.

**Reste à payer.** TTC de la facture moins ses règlements (`MontantTTC`), affiché **seulement** quand Moduléo permet de le déduire : facture émise, montants lus, tous ses `IdsReglements` lus (`cogeo/reglement/{id}`, un 404 n'est pas une panne mais rend le reste non déductible), aucun avoir sur la facture (`cogeo/avoir/facture?idFacture=`), aucun règlement avec pénalités (`MontantReglementPenalitesTTC`) ni `TypeReglement` autre que 0. Sinon, pas de ligne « Reste à payer » : jamais estimé. Échéances : celle de chaque règlement (`IdEcheance`, `cogeo/echeance/{id}`) ; Moduléo n'a pas de route des échéances d'une facture.

**Déroulé.**

1. Noms → ids (`moduleo/resolution.py`, `id_affaire`).
2. Recherche `cogeo/facture?texte=…` (ids), ou factures de l'affaire.
3. **Toutes** les factures trouvées : `cogeo/facture/multi?ids=` par lots de 200 (`lire_par_lots`), triées du plus récent au plus ancien (date d'émission, de création pour une facture non émise, puis id).
4. Règlements et avoirs de chaque facture émise, en parallèle (16 lectures au plus) : de **toutes** jusqu'à 50 factures émises ; au-delà, des seules fiches affichées, et le total du reste à payer n'est pas calculé. Échéances : pour les fiches affichées.
5. Les `nb_max` premières : leurs affaires (`cogeo/affaire/multi`), destinataires (`cogeo/destinataire/multi`), responsable et rédacteur (`moduleo/utilisateur/{id}`), clients (`cogeo/contact/multi`). Client : le contact destinataire de la facture, sinon le client de l'affaire.
6. Synthèse (`synthese_factures`, `moduleo/fiches.py`) : nombre, total HT et TTC de toutes les factures trouvées, reste à payer des factures émises.

**Au modèle.** La synthèse en tête (« 7 factures trouvées (texte « Bornage »), total 700,00 € HT, 840,00 € TTC, reste à payer 700,00 €. Les 5 plus récentes affichées, précise la recherche. » ; « reste à payer sur les émises … » quand l'ensemble compte des factures non émises ; « reste à payer non calculé (avoir ou règlement à vérifier dans Moduléo) » ou « … non calculé au-delà de 50 factures émises »), puis une Fiche Moduléo par facture (`fiche_facture` : numéro, objet, affaire, client, dates de création et d'émission ou « non émise », responsable, rédacteur, montants HT / TTC, « Échéances et règlements » une ligne par règlement avec date, montant, mode et échéance, ou « aucun règlement », reste à payer). Aucune : « Aucune facture Moduléo ne correspond à cette recherche. », ou « Aucune facture émise dans Moduléo depuis le JJ/MM/AAAA (30 derniers jours). » sans critère.

**Lectures.** La synthèse est une lecture (référence « factures émises du 09/09/2026 au 09/10/2026 », ou « factures (<critères>) »), avant celles des fiches (« facture F-2026-118 ») : un total ou un reste cité par le modèle reste dans la réponse et cite sa lecture, un total inventé est retiré par le garde-fou chiffres. Questions couvertes par gabarit : objet, montant, « La facture … est-elle payée ? » (émission, réglé, reste à payer), affaire et client, suivi ; « Combien de factures … ? », « Quel est le montant total des factures … ? », « Quel est le reste à payer des factures … ? ».

**Inspecteur** (`outil:chercher_factures_moduleo`) : arguments, `routes`, `trouvees`, `synthese`, `fiches`, `non_resolu`, `erreur` ou `garde_des_droits`.

**Depuis.** 1.5.1 (#190). À confirmer à l'essai réel : sens exact de `emise`, nature des `IdsReglements` d'une facture, valeurs de `TypeReglement`, ordre et format des dates attendus par l'API.

Code : `outil.py`.
