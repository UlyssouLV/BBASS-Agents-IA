# Outils Moduléo

Les outils que le modèle peut appeler pour lire Moduléo, le logiciel de gestion du cabinet (spec 1.5.0, [ADR-0017](../../../../../docs/adr/0017-lecture-moduleo-par-outil.md)). Un paquet par outil (`__init__.py` exporte `OUTIL`, `outil.py`, `README.md`), inscrit dans `outils/registre.py`. L'accès à Moduléo (client GET seul, routes, résolution des noms, fiches) est commun à tous les outils et vit dans `vm_centrale/moduleo/`.

**Règles communes.**

- **Éligibilité** : proposés sur chaque appel de chat principal, pour tous les comptes, seulement si Moduléo est configuré (`ContexteTour.client_moduleo`, rempli par `get_client_moduleo`) ; sans config, absents du payload `tools`, sans erreur.
- **Statut** : « Consultation Moduléo » (`CONSULTATION_MODULEO`, `statut_tour.py`) avant la première lecture.
- **Panne / refus** : phrase fixe au modèle, « Moduléo est indisponible pour le moment. » (panne, réponse inexploitable) ou « Moduléo refuse l'accès à cette donnée. » (401 / 403) ; détail dans la trace de l'inspecteur ; jamais de 500, aucune nouvelle tentative, aucune lecture enregistrée.
- **Lectures** : une ligne `lectures_outils` (outil `moduleo`) par Fiche Moduléo renvoyée, source des garde-fous chiffres et sources sur toute la conversation (`vm_centrale/lectures_outils.py`).
- **Inspecteur** : échange `local` `outil:<nom>` : arguments, `fiches`, `routes` (route et paramètres de chaque lecture), `erreur` éventuelle. Jamais la clé ni le SecurityCode : ils restent dans les en-têtes de `ClientModuleo`.

| Outil | Ce qu'il fait | Depuis |
| --- | --- | --- |
| `chercher_affaires_moduleo` ([`affaires/`](affaires/README.md)) | Retrouve des affaires par numéro, par texte ou par filtres en noms (état, dates, site, service, responsable, chargé d'affaire, dossier de production) ; une Fiche Moduléo par affaire. | 1.5.0 (#174, #175) |
