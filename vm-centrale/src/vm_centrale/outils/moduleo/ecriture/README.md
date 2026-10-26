# decrire_ecriture_moduleo, ecrire_moduleo

Les deux outils génériques de l'écriture Moduléo (spec 1.5.2, #204, [ADR-0019](../../../../../../docs/adr/0019-ecriture-moduleo-confirmee-serveur-de-test.md)) : pas un outil par route. Règles communes (statut, panne, inspecteur) : [`../README.md`](../README.md) ; client, garde, Carte de confirmation et Journal des écritures : [`vm_centrale/moduleo/README.md`](../../../moduleo/README.md).

**Éligibilité.** Les deux outils sont proposés ensemble, seulement si `ClientModuleo.ecriture_ouverte()` (`MODULEO_ECRITURE` actif, `MODULEO_URL` dans `serveurs_test.json`) et si au moins une route d'écriture d'une méthode ouverte peut s'ouvrir au compte (`ecriture_possible`, garde des droits : route classée, non fermée, groupe ou droit présent, ou `siens_ecriture` avec un utilisateur Moduléo lié). Méthodes ouvertes (`_METHODES_OUVERTES`) : **POST** en 1.5.2 (#204) ; PUT et DELETE attendent leur carte détaillée (#205).

**Route.** Toujours « MÉTHODE gabarit », tel que listé : `POST moduleo/telephone`, `POST cogeo/localisant?idAffaire={idAffaire}`.

**`decrire_ecriture_moduleo(route)`.** Aucun appel à Moduléo : `ROUTES_ECRITURE` (WADL versionné). Renvoie « MÉTHODE route : description », « Paramètres : nom (type), … » ou « aucun », puis l'exemple de corps JSON du WADL, ou « Pas de corps. ». Route inconnue, d'une méthode non ouverte, fermée ou hors des droits du compte : « Route d'écriture Moduléo inconnue ou fermée : « … ». Choisis une route listée dans la description de ecrire_moduleo, sous la forme « MÉTHODE route ». Rien n'a été écrit. »

**`ecrire_moduleo(route, parametres, corps)`.** Description : une ligne par route ouverte au compte (« POST moduleo/telephone — Crée un numéro de téléphone. »). `parametres` et `corps` : objets, ou texte JSON. Déroulé :

1. Route inconnue (ou méthode non ouverte) : la phrase de `decrire_ecriture_moduleo`. Une route connue mais hors des droits du compte va au garde, pour que la phrase dise le droit manquant.
2. Statut « Consultation Moduléo : préparation de l'écriture ».
3. `ClientModuleo.verifier_ecriture` : tout ce que vérifierait `ecrire()`, sans rien envoyer. `RequeteInterdite` (paramètre manquant, corps absent…) : « Écriture non proposée : <détail> Rien n'a été écrit. », rien au journal. `DroitManquant` : la phrase du garde (« … Rien n'a été écrit. … »), une ligne `refusee` sans carte au Journal des écritures, `garde_des_droits` dans la trace. Panne pendant la relecture d'un élément `siens` : « Moduléo est indisponible pour le moment. ».
4. Lignes de la carte en noms (`moduleo/carte.py`, lectures du compte, gardées et tracées dans `routes`).
5. Écriture proposée enregistrée (`moduleo/ecritures.py`, `proposer`, flush), événement SSE `carte` (`ContexteTour.publier_carte`).
6. Au modèle : « Écriture proposée au collaborateur, en attente de sa confirmation. Rien n'a été écrit. Ne dis jamais que l'écriture est faite : seul le collaborateur la confirme, sur la carte. »

**Rien n'est envoyé à Moduléo** par ces outils : seule la route `POST /ecritures-moduleo/{id}` (`routers/ecritures_moduleo.py`), au clic du collaborateur, appelle `ecrire()`.

**Inspecteur.** Échange `outil:ecrire_moduleo` : arguments ; `route`, `parametres`, `corps`, `carte` (telle qu'envoyée au poste), `routes` (lectures de la résolution des noms) ; ou `garde_des_droits` / `erreur`.
