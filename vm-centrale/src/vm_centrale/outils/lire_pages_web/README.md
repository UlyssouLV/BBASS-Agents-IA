# lire_pages_web

Relit, pour un `besoin`, une ou plusieurs pages déjà trouvées par une recherche de la conversation (`resultats_recherche_web`), sans relancer de recherche ni retélécharger la page.

**Éligibilité.** Dès qu'une recherche de la conversation a ramené un résultat (tours précédents ; les URL sont dans la Mémoire de la conversation). Jamais sur le titrage ni le résumé et profil.

**Exécution.** Arguments `urls` et `besoin`. Un bloc par URL, dans l'ordre, chacun précédé de son URL :

1. URL absente des résultats de recherche de la conversation : « Page introuvable. », sans appel d'extraction, jamais une erreur HTTP.
2. Page non lue à la recherche (texte nettoyé vide : PDF, refus, délai) : l'extrait du moteur seulement, sans appel ni téléchargement.
3. Page lue : un appel d'extraction isolé par page (`mistral-small-latest`, en parallèle, une seule fois par page même citée deux fois) : consigne fixe `CONSIGNE_LECTURE_PAGE`, le besoin et le texte nettoyé enregistré, jamais le contexte de la conversation (ADR-0014). Sortie JSON stricte : `trouvee`, `reponse`, `source`. Consigne : « non trouvé » plutôt qu'une estimation. Ligne `Consommation` `extraction_web` et échange d'inspecteur `extraction_web` (origine `mistral`).
4. Résultat enregistré dans `questions_couvertes` sur le résultat de la page : question = besoin, origine `besoin` (hors des 8 questions initiales), réponse coupée à 300 caractères, source = URL de la page. Non trouvé : `trouvee = faux`, affiché « non présent selon l'extraction » dans la Mémoire de la conversation. Jamais une source des garde-fous. Échec de l'appel ou réponse hors du JSON attendu : « Extraction indisponible… », rien d'enregistré.

Une URL ramenée par plusieurs recherches : la dernière page lue, sinon le dernier résultat. `besoin` vide : « Besoin manquant… », sans appel.

**Inspecteur local** (`outil:lire_pages_web`) : arguments, contenu renvoyé au modèle ; puis un échange `extraction_web` par page lue.

**Depuis.** 1.4.1 (#139). Spec 1.4.1 : retrouver une information déjà trouvée ou poser une nouvelle question à une page lue sans relancer de recherche. Les URL écrites par le compte (téléchargées au premier appel, provenance `utilisateur`) : #140.

Code : `outil.py`. D'autres modules de cet outil peuvent vivre à côté sans changer le registre (`OUTIL` et `CONSIGNE_LECTURE_PAGE` restent exportés par ce paquet).
