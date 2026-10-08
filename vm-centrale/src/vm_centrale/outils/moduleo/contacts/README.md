# chercher_contacts_moduleo

Retrouve des contacts Moduléo et leurs coordonnées quand le modèle le décide (« coordonnées de Dupont », « dans quelles affaires apparaît la SCI Les Oliviers ? »). Règles communes (éligibilité, statut, panne / refus, lectures, inspecteur) : [`../README.md`](../README.md).

**Paramètres**, combinés en « et » :

- `texte` : le nom du contact, ou un mot de son nom.
- `type_contact` : personne, société, collectivité ou groupe de contacts (sans casse ni accent), transmis en `typeContact` par le nom de l'énumération Moduléo (`Personne`, `Societe`, `Collectivite`, `GroupeContacts`, `moduleo/enumerations.py`, relevé #180). Un autre type : une phrase au modèle, aucune lecture.
- `type_donneur_ordre` : transmis tel quel en `typeDonneurOrdreGE`.
- `qualifications` : des noms (« Notaire »), résolus en ids par `chercher_qualifications` (`moduleo/resolution.py`, `cogeo/qualification/all`) : le libellé exact l'emporte, sinon le seul libellé qui contient le nom. Aucun libellé, ou plusieurs : une phrase au modèle (« Plusieurs qualifications Moduléo correspondent à « Expert » : Expert foncier, Géomètre-expert. Demande lequel… »), **aucune recherche**, trace `non_resolu`.

`nb_max`, 5 par défaut, ramené entre 1 et 10. Aucun paramètre : une phrase demande un texte, un type ou une qualification, sans lecture. Toute phrase de l'outil qui n'a rien lu se termine par « Aucune lecture faite dans Moduléo : n'invente aucun contact, demande au collaborateur un nom, un type ou une qualification. » (#182).

**Déroulé.**

1. Qualifications → ids, s'il y en a.
2. Recherche : `cogeo/contact?texte=…&nbMaxResultat=200` (les ids, pour compter les contacts trouvés au-delà de `nb_max`).
3. Les `nb_max` premiers : `cogeo/contact/multi?ids=`.
4. Par contact, **en parallèle** (au plus 16 lectures à la fois) : téléphones (`cogeo/contact/{id}/telephones` puis `moduleo/telephone/{id}`), emails (`…/emails` puis `cogeo/email/{id}`), adresses (`…/adresses` puis `moduleo/adresse/{id}`), affaires (`…/affaires` pour client, `…/affaireintervenant` pour intervenant, puis une lecture `cogeo/affaire/multi?ids=` pour les numéros). Une coordonnée en 404 est sautée ; toute autre panne, dans n'importe quel thread, donne la phrase de panne.
5. Communes des adresses, dédoublonnées sur l'appel (`moduleo/commune/multi`).
6. Une Fiche Moduléo par contact (`fiche_contact`, `moduleo/fiches.py`) : type, nom, téléphones, emails et adresses avec leur lieu (« Bureau », « Siège »), numéros des affaires dont il est client puis intervenant (20 au plus par rôle, « et N autres »). Enregistrée dans `lectures_outils`, référence « contact <nom> » : un téléphone de la fiche reste dans la réponse et la ligne « Sources : » cite « Moduléo, contact <nom> ».

**Au modèle.** Les fiches, séparées par une ligne vide. Plus de contacts que de fiches : « N contacts trouvés, M affichés, précise la recherche. » en tête (« Au moins 200 » au plafond des ids). Aucun : « Aucun contact Moduléo ne correspond à cette recherche. »

**Inspecteur** (`outil:chercher_contacts_moduleo`) : arguments, `routes`, `trouvees`, `fiches`, `non_resolu` ou `erreur`.

**Depuis.** 1.5.0 (#176). `TypeContact` relevé sur le serveur réel (#180) : 1 Personne, 3 Société, 4 Collectivité, 5 Groupe de contacts (`moduleo/README.md`). À confirmer à l'essai réel (#178) : valeurs de `typeDonneurOrdreGE`, combinaison de plusieurs `idsQualifications` (« et » ou « ou »).

Code : `outil.py`.
