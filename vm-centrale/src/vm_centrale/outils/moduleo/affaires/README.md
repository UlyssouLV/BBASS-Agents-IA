# chercher_affaires_moduleo

Retrouve des affaires Moduléo par **numéro** ou par **texte** quand le modèle le décide. Règles communes (éligibilité, statut, panne / refus, lectures, inspecteur) : [`../README.md`](../README.md).

**Paramètres.** `numero` (prioritaire), sinon `texte` (un mot de l'objet, de l'adresse ou du client) ; `nb_max`, 5 par défaut, ramené entre 1 et 10. Ni l'un ni l'autre : une phrase demande un numéro ou un texte, sans lecture.

**Déroulé.**

1. Recherche : `cogeo/affaire/numeroAffaire?numAffaire=` (un id ; 404 ou 0 : aucune affaire), ou `cogeo/affaire?texte=…&nbMaxResultats=200` (les ids, pour compter les affaires trouvées au-delà de `nb_max`).
2. Les `nb_max` premières : `cogeo/affaire/multi?ids=`, puis `cogeo/affaire/{id}/intervenants` par affaire et `cogeo/intervenant/multi?ids=` pour tous.
3. Noms de tout l'appel, dédoublonnés (`moduleo/resolution.py`) : responsable et chargé d'affaire (`moduleo/utilisateur/{id}`), client, représentant, intervenants et leurs représentants (`cogeo/contact/multi`), commune (`moduleo/commune/multi`).
4. Une Fiche Moduléo par affaire (`moduleo/fiches.py`), enregistrée dans `lectures_outils` (référence « affaire <numéro> »).

**Au modèle.** Les fiches, séparées par une ligne vide. Plus d'affaires que de fiches : « N affaires trouvées, M affichées, précise la recherche. » en tête (« Au moins 200 » au plafond des ids). Aucune : « Aucune affaire Moduléo ne correspond à cette recherche. »

**Inspecteur** (`outil:chercher_affaires_moduleo`) : arguments, `routes`, `trouvees`, `fiches`, ou `erreur`.

**Depuis.** 1.5.0 (#174). Filtres en noms (état, dates, site, service, responsable, chargé d'affaire, dossier de production) : #175. Valeurs d'`Etat` affichées telles que Moduléo les renvoie, à confirmer à l'essai réel (#178).

Code : `outil.py`.
