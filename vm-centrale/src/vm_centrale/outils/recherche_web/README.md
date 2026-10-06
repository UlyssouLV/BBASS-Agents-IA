# rechercher_web

Cherche sur Internet quand le modèle le décide. `requete` seule part vers `MoteurRecherche` (`moteur_recherche.py`, SearXNG par défaut). `besoin` ne va qu'à l'appel d'extraction (ADR-0013).

**Éligibilité.** Toujours, sur chaque appel de chat principal (premier message compris). Jamais sur le titrage ni le résumé et profil.

**Déroulé.**

1. Les 5 premiers résultats (titre, URL, extrait du moteur). Moteur injoignable : « Recherche indisponible… ». Aucun résultat, ou requête vide : « Aucun résultat… ». Jamais une erreur HTTP.
2. Les 3 premières pages, en parallèle (`TelechargeurPages`, `telechargement_pages.py`, 10 s au plus par page). Échec (délai, statut HTTP, contenu non HTML, PDF compris) : la page est ignorée, son extrait de moteur reste.
3. Texte principal via trafilatura, jamais coupé page par page. Plafond global d'environ 80 % de la fenêtre du modèle d'extraction, estimé en caractères (3 caractères ≈ 1 token, 131 072 tokens) : au-delà, la dernière page lue est retirée entière.
4. Résultats et texte nettoyé des pages lues dans `resultats_recherche_web` (source du garde-fou chiffres). Une page retirée par le plafond n'est pas une source.
5. Appel d'extraction (`mistral-small-latest`, ADR-0014) : consigne fixe `CONSIGNE_EXTRACTION`, puis `besoin` et les pages lues, jamais le contexte de la conversation. Ligne `Consommation` `extraction_web` et échange d'inspecteur `extraction_web` (origine `mistral`). Aucune page lue : pas d'appel. Extraction en échec : « Extraction indisponible… ».
6. Le modèle principal reçoit la liste (titre, URL) et l'extrait, jamais le texte des pages. L'extrait n'est pas une source des garde-fous. Sans extraction réussie, la liste part avec les extraits du moteur.

**Inspecteur local** (`outil:rechercher_web`) : arguments, résultats bruts (`resultats`) ou `erreur`, pages (URL, statut, taille, `retiree_par_plafond`, erreur), contenu renvoyé au modèle.

**Depuis.** 1.4.0. Spec 1.4.0, ADR-0013 : le relais `chat/completions` n'a pas l'outil `web_search` de Mistral ; le modèle décide de chercher (décision n° 3).

Code : `outil.py`. D'autres modules de cet outil (plafond, extraction, …) peuvent vivre à côté sans changer le registre (`OUTIL` et `CONSIGNE_EXTRACTION` restent exportés par ce paquet).
