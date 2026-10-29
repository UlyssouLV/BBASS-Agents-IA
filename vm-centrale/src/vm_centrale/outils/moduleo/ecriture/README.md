# decrire_ecriture_moduleo, ecrire_moduleo

Les deux outils génériques de l'écriture Moduléo (spec 1.5.2, #204, [ADR-0019](../../../../../../docs/adr/0019-ecriture-moduleo-confirmee-serveur-de-test.md)) : pas un outil par route. Règles communes (statut, panne, inspecteur) : [`../README.md`](../README.md) ; client, garde, Carte de confirmation et Journal des écritures : [`vm_centrale/moduleo/README.md`](../../../moduleo/README.md).

**Éligibilité.** Les deux outils sont proposés ensemble, seulement si `ClientModuleo.ecriture_ouverte()` (`MODULEO_ECRITURE` actif, `MODULEO_URL` dans `serveurs_test.json`) et si au moins une route d'écriture peut s'ouvrir au compte (`ecriture_possible`, garde des droits : route classée, non fermée, groupe ou droit présent, ou `siens_ecriture` avec un utilisateur Moduléo lié). POST depuis #204 ; PUT et DELETE depuis #205, avec leur carte détaillée.

**Route.** Toujours « MÉTHODE gabarit », tel que listé : `POST moduleo/telephone`, `POST cogeo/localisant?idAffaire={idAffaire}`.

**`decrire_ecriture_moduleo(route)`.** Aucun appel à Moduléo : `ROUTES_ECRITURE` (WADL versionné). Renvoie « MÉTHODE route : description », « Paramètres : nom (type), … » ou « aucun », puis l'exemple de corps JSON du WADL, ou « Pas de corps. ». Route inconnue, fermée ou hors des droits du compte : « Route d'écriture Moduléo inconnue ou fermée : « … ». Choisis une route listée dans la description de ecrire_moduleo, sous la forme « MÉTHODE route ». Rien n'a été écrit. »

**`ecrire_moduleo(route, parametres, corps)`.** Description : une ligne par route ouverte au compte (« POST moduleo/telephone — Crée un numéro de téléphone. »). `parametres` et `corps` : objets, ou texte JSON. Déroulé :

1. Route inconnue : la phrase de `decrire_ecriture_moduleo`. Une route connue mais hors des droits du compte va au garde, pour que la phrase dise le droit manquant.
2. Statut « Consultation Moduléo : préparation de l'écriture ».
3. `ClientModuleo.verifier_ecriture` : tout ce que vérifierait `ecrire()`, sans rien envoyer. `RequeteInterdite` (paramètre manquant, corps absent…) : « Écriture non proposée : <détail> Rien n'a été écrit. », rien au journal. `DroitManquant` : la phrase du garde (« … Rien n'a été écrit. … »), une ligne `refusee` sans carte au Journal des écritures, `garde_des_droits` dans la trace. Panne pendant la relecture d'un élément `siens` : « Moduléo est indisponible pour le moment. ».
4. Carte en noms (`moduleo/carte.py`, lectures du compte, gardées et tracées dans `routes`) :
   - **POST** : paramètres puis corps.
   - **PUT / DELETE** (#205) : l'élément visé est d'abord relu (`moduleo/relecture.py`, route GET de `RELECTURES`, garde des droits compris). Introuvable (404, `multi` vide, id absent) : « L'élément visé n'existe pas dans Moduléo : écriture non proposée. Rien n'a été écrit. », rien au journal. Relecture refusée par le garde : « Votre compte ne peut pas lire l'élément visé dans Moduléo : écriture non proposée. Rien n'a été écrit. Demandez à un compte administrateur si vous en avez besoin. », une ligne `refusee` sans carte au journal (ex. `PUT moduleo/tacheafaire/{idTacheAFaire}` avec « Supprimer / Éditer les tâches à faire dont il n'est pas le créateur » sans « Voir les tâches à faire des autres »). Panne : « Moduléo est indisponible pour le moment. ».
   - **PUT** avec corps : les seuls champs du corps qui changent l'élément relu, `avant` → `valeur` en noms, un champ vide valant « (vide) » ; les champs qui portent l'id de l'élément lui-même ne sont pas montrés. Aucun changement : « Écriture non proposée : le corps ne change aucun champ de l'élément visé. Rien n'a été écrit. », rien au journal. Le corps proposé reçoit `ProprietesModifiees` : les seules clés que la carte annonce, à la place de la liste du modèle, pour que Moduléo ne remette pas à vide les champs absents (#251, section **PUT partiel** du README du module). PUT sans corps (émettre, accepter, refuser un devis ; changer l'archive d'une affaire) : ses paramètres en noms, après la relecture.
   - **DELETE** : `rubrique` « Sera supprimé » et la fiche de lecture de l'élément sans son id Moduléo (temps passé, tâche du planning), sinon ses champs en noms.
5. Écriture proposée enregistrée (`moduleo/ecritures.py`, `proposer`, flush), événement SSE `carte` (`ContexteTour.publier_carte`).
6. Au modèle : « Écriture proposée au collaborateur, en attente de sa confirmation. Rien n'a été écrit. Ne dis jamais que l'écriture est faite : seul le collaborateur la confirme, sur la carte. »

**Rien n'est envoyé à Moduléo** par ces outils : seule la route `POST /ecritures-moduleo/{id}` (`routers/ecritures_moduleo.py`), au clic du collaborateur, appelle `ecrire()`.

**Inspecteur.** Échange `outil:ecrire_moduleo` : arguments ; `route`, `parametres`, `corps`, `carte` (telle qu'envoyée au poste), `routes` (lectures de la résolution des noms) ; ou `garde_des_droits` / `erreur`.
