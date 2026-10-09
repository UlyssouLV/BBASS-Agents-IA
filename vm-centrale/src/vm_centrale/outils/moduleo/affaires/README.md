# chercher_affaires_moduleo

Retrouve des affaires Moduléo par **numéro**, par **texte** ou par **filtres en noms** quand le modèle le décide. Règles communes (éligibilité, statut, panne / refus, lectures, inspecteur) : [`../README.md`](../README.md).

**Paramètres.** `numero` (prioritaire : les autres sont alors ignorés), sinon `texte` (un mot de l'objet, de l'adresse ou du client) et / ou des filtres, combinés en « et » :

- `etat` : un état de l'interface Moduléo (Créée, En attente, Acceptée, Production, Suspendue, Prod. terminée, Clôturée, Annulée ; casse, accents et accord indifférents), transmis en `etatAffaire` par le nom de l'énumération (`Acceptee`…, `moduleo/enumerations.py`). Un autre état (« en retard ») : une phrase au modèle qui liste les états, aucune recherche, car Moduléo ignore un nom inconnu et renverrait toutes les affaires (test humain 1.5.0, conversation 113, #180).
- `date_{creation,ouverture,livraison,cloture}_{min,max}` : AAAA-MM-JJ ou JJ/MM/AAAA, transmis en AAAA-MM-JJ (`dateOuvertureMin`…).
- `site`, `service` : tous les sites / services qui portent ce nom (`idsSite`, `idsService`).
- `responsable`, `charge_affaire` : un utilisateur (`idsResponsable`, `idsActeurEnCharge`).
- `suivi_par` : un utilisateur, responsable **ou** chargé d'affaire ; remplace les deux précédents.
- `dossier_production` : un dossier de production (`idDossierProduction`).

`avec_parcelles` (booléen, `true` en texte accepté ; #193) : ajoute à la fiche les parcelles de l'affaire et leurs propriétaires. **Jamais d'office** : Moduléo n'a qu'une route par parcelle et par propriétaire, et les propriétaires sont des données personnelles. **Une seule affaire** : si la recherche en trouve plusieurs, « Les parcelles ne se lisent que pour une seule affaire, et N affaires correspondent : demande au collaborateur le numéro de l'affaire voulue. » (suivie de la phrase « Aucune lecture faite… »), sans fiche ni lecture de parcelle.

`nb_max`, 5 par défaut, ramené entre 1 et 10. Rien de tout cela (`{}`, `{"nb_max": 10}`) : les affaires créées ces 90 derniers jours (`dateCreationMin` = aujourd'hui − 90 jours), « N affaires créées depuis le JJ/MM/AAAA, M plus récentes affichées. » en tête, ou « Aucune affaire créée dans Moduléo depuis le JJ/MM/AAAA. » (test humain 1.5.0, conversation 115, #182 : « les dernières affaires » n'appelait jamais Moduléo).

**Noms non résolus.** État inconnu, date illisible, nom qui ne désigne rien, ou plusieurs utilisateurs / dossiers de production : une phrase au modèle (« Aucun site Moduléo ne correspond à « Lyon » : recherche non lancée. », « Plusieurs utilisateurs Moduléo correspondent à « Martin » : Jean Martin, Paul Martin. Demande lequel… »), **aucune recherche** sans le filtre demandé, aucune lecture enregistrée. Toute phrase de l'outil qui n'a rien lu se termine par « Aucune lecture faite dans Moduléo : n'invente aucune affaire, demande au collaborateur un numéro, un nom ou une période. » (#182, conversation 115 : le modèle avait inventé 10 affaires après un refus). Trace : `non_resolu`.

**Déroulé.**

1. Noms → ids (`moduleo/resolution.py`) : `moduleo/utilisateur?nom=&prenom=`, `moduleo/site?nom=`, `moduleo/service?nom=`, `fileo/dossierproduction?texteRecherche=`.
2. Recherche : `cogeo/affaire/numeroAffaire?numAffaire=` (un id ; 404 ou 0 : aucune affaire), ou `cogeo/affaire?texte=…&nbMaxResultats=200` avec les filtres (les ids, pour compter les affaires trouvées au-delà de `nb_max`). `suivi_par` : deux recherches (responsable, puis chargé d'affaire), ids réunis sans doublon. Ids triés par ordre décroissant : les plus récentes d'abord (#182, ordre à confirmer à l'essai réel).
3. Les `nb_max` plus récentes : `cogeo/affaire/multi?ids=`, puis `cogeo/affaire/{id}/intervenants` par affaire et `cogeo/intervenant/multi?ids=` pour tous.
4. Noms de tout l'appel, dédoublonnés (`moduleo/resolution.py`) : responsable et chargé d'affaire (`moduleo/utilisateur/{id}`), client, représentant, intervenants et leurs représentants (`cogeo/contact/multi`), commune (`moduleo/commune/multi`).
5. Avec `avec_parcelles`, pour l'affaire trouvée : `cogeo/affaire/{id}/parcelles`, puis `cogeo/parcelle/{id}` par parcelle, `cogeo/parcelle/{id}/proprietaires` et `cogeo/proprietaire/{id}` par propriétaire (son `IdContact`), chacune à travers le garde. Noms des propriétaires et communes des parcelles résolus avec ceux de l'étape 4, dans les mêmes lectures `multi`. Propriétaires : droit « Rechercher des contacts » (données personnelles, `droits/routes.json`) ; sans lui, ils ne sont pas lus et la fiche porte « Propriétaires : non autorisés pour votre compte ».
6. Une Fiche Moduléo par affaire (`moduleo/fiches.py`), enregistrée dans `lectures_outils` (référence « affaire <numéro> »).

**Au modèle.** Les fiches, séparées par une ligne vide. Avec `avec_parcelles`, la fiche se termine par « Parcelles : » et une ligne par parcelle (« - AB 123, Castries (34160), lieu-dit Les Plans, contenance 1 234 m², propriétaires : SCI Les Oliviers, Paul Durand » ; préfixe cadastral vide ou « 000 » non affiché), ou « Parcelles : aucune dans Moduléo ». Références et contenances sont dans la fiche, donc gardées par les garde-fous. Une fiche qui nomme un client, un représentant ou un intervenant se termine par « Coordonnées du client et des intervenants : absentes de cette fiche, à lire avec chercher_contacts_moduleo à partir de leur nom, seulement si le collaborateur les demande. » ; la description de l'outil le dit aussi. La VM n'appelle jamais l'outil contacts d'elle-même : seul le modèle le fait, sur demande du collaborateur (#183, conversation 116 : le modèle répondait « pas disponibles dans Moduléo » sans le lire ; garde-fou [`contact_non_lu/`](../../../garde_fous/contact_non_lu/README.md)). Plus d'affaires que de fiches : « N affaires trouvées, M affichées, précise la recherche. » en tête (« Au moins 200 » au plafond des ids). Aucune : « Aucune affaire Moduléo ne correspond à cette recherche. »

**Inspecteur** (`outil:chercher_affaires_moduleo`) : arguments, `routes`, `trouvees`, `fiches`, `non_resolu` ou `erreur`.

**Depuis.** 1.5.0 (#174), filtres en noms (#175), affaires récentes sans critère et plus récentes d'abord (#182), renvoi vers `chercher_contacts_moduleo` pour les coordonnées (#183), parcelles à la demande (#193). Valeurs d'`Etat` relevées sur le serveur réel et affichées en libellés (#180). À confirmer à l'essai réel (#178) : format de date attendu par l'API, recherche par nom exacte ou partielle, unité de `ContenanceCadatrale` (affichée en m²), `TypeDroit` d'un propriétaire (non affiché).

Code : `outil.py`.
