# lire_pages_web

Lit, pour un `besoin`, une ou plusieurs pages de la conversation, sans relancer de recherche : une page trouvée par une recherche (`resultats_recherche_web`), ou une page dont le compte a écrit l'URL, téléchargée au premier appel seulement.

**Éligibilité.** Dès qu'une recherche de la conversation a ramené un résultat, ou que le compte a écrit une URL dans un message `user` de la conversation ou dans le message du tour (les URL sont dans la Mémoire de la conversation). Jamais sur le titrage ni le résumé et profil.

**Exécution.** Arguments `urls` et `besoin`. Un bloc par URL, dans l'ordre, chacun précédé de son URL :

1. URL ni dans les résultats de la conversation, ni écrite par le compte (même règle que le garde-fou URL, `garde_fous/urls.py` ; comparaison sans schéma, `www.`, casse ni `/` final) : « Page introuvable. », sans appel d'extraction, jamais une erreur HTTP.
2. URL écrite par le compte, pas encore en base : téléchargée et nettoyée par la chaîne de `rechercher_web` (`recherche_web.outil.lire_page` : statut 200, HTML, `trafilatura`), en parallèle, puis enregistrée dans `resultats_recherche_web` avec `provenance = utilisateur`, la requête, le titre et l'extrait du moteur vides, et le texte nettoyé (vide en échec). Jamais retéléchargée ensuite dans la conversation, lue ou non. PDF, page refusée, délai dépassé : « page non lue (PDF, page refusée ou délai dépassé). », sans appel ni erreur. Une page lue sert de source au garde-fou chiffres comme une page trouvée. Pages téléchargées dans la trace de l'échange local (`pages_telechargees`).
3. Page non lue à la recherche (texte nettoyé vide : PDF, refus, délai) : l'extrait du moteur seulement, sans appel ni téléchargement.
4. Page lue : un appel d'extraction isolé par page (`mistral-small-latest`, en parallèle, une seule fois par page même citée deux fois) : consigne fixe `CONSIGNE_LECTURE_PAGE`, le besoin et le texte nettoyé enregistré, jamais le contexte de la conversation (ADR-0014). Sortie JSON stricte : `trouvee`, `reponse`, `source`. Consigne : « non trouvé » plutôt qu'une estimation. Ligne `Consommation` `extraction_web` et échange d'inspecteur `extraction_web` (origine `mistral`).
5. Résultat enregistré dans `questions_couvertes` sur le résultat de la page : question = besoin, origine `besoin` (hors des 8 questions initiales), réponse coupée à 300 caractères, source = URL de la page. Non trouvé : `trouvee = faux`, affiché « non présent selon l'extraction » dans la Mémoire de la conversation. Jamais une source des garde-fous. Échec de l'appel ou réponse hors du JSON attendu : « Extraction indisponible… », rien d'enregistré.

Une URL ramenée par plusieurs recherches : la dernière page lue, sinon le dernier résultat. Mémoire de la conversation : l'URL écrite par le compte porte « (pas encore lue) », « (lue) » ou « (page non lue) », et les questions couvertes de sa page ; une page `utilisateur` n'y est jamais listée comme une recherche. `besoin` vide : « Besoin manquant… », sans appel.

**Inspecteur local** (`outil:lire_pages_web`) : arguments, contenu renvoyé au modèle ; puis un échange `extraction_web` par page lue.

**Depuis.** 1.4.1 (#139). Spec 1.4.1 : retrouver une information déjà trouvée ou poser une nouvelle question à une page lue sans relancer de recherche. URL écrites par le compte (téléchargées au premier appel, provenance `utilisateur`) : #140, spec 1.4.1 (« Le modèle ne peut pas non plus lire la page »).

Code : `outil.py`. D'autres modules de cet outil peuvent vivre à côté sans changer le registre (`OUTIL` et `CONSIGNE_LECTURE_PAGE` restent exportés par ce paquet).
