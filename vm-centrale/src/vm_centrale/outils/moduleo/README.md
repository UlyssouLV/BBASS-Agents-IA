# Outils Moduléo

Les outils que le modèle peut appeler pour lire Moduléo, le logiciel de gestion du cabinet (spec 1.5.0, [ADR-0017](../../../../../docs/adr/0017-lecture-moduleo-par-outil.md)). Un paquet par outil (`__init__.py` exporte `OUTIL`, `outil.py`, `README.md`), inscrit dans `outils/registre.py`. L'accès à Moduléo (client GET seul, routes, résolution des noms, fiches) est commun à tous les outils et vit dans `vm_centrale/moduleo/` ; le déroulé commun d'un appel (statut, trace des routes, panne / refus, plafond et « N trouvés », lectures) est `commun.py` (`lire_fiches`, #176).

**Règles communes.**

- **Éligibilité** : proposés sur chaque appel de chat principal, pour tous les comptes, seulement si Moduléo est configuré (`ContexteTour.client_moduleo`, rempli par `get_client_moduleo`) ; sans config, absents du payload `tools`, sans erreur.
- **Statut** : « Consultation Moduléo » (`CONSULTATION_MODULEO`, `statut_tour.py`) avant la première lecture.
- **Panne / refus** : phrase fixe au modèle, « Moduléo est indisponible pour le moment. » (panne, réponse inexploitable) ou « Moduléo refuse l'accès à cette donnée. » (401 / 403) ; détail dans la trace de l'inspecteur ; jamais de 500, aucune nouvelle tentative, aucune lecture enregistrée.
- **Lectures** : une ligne `lectures_outils` (outil `moduleo`) par Fiche Moduléo renvoyée, source des garde-fous chiffres et sources sur toute la conversation (`vm_centrale/lectures_outils.py`). Avec elle, ses questions couvertes (`questions_couvertes.lecture_outil_id`, origine `initiale`, écrites par `moduleo/fiches.py` sans appel Mistral, jamais une source des garde-fous) ; la Mémoire de la conversation liste la lecture avec son tour, sa date et ces questions, et dit de rappeler Moduléo pour l'état actuel ou une lecture ancienne (#177).
- **Sans lecture** : un nom non résolu ne lance aucune recherche ; la phrase au modèle se termine par la phrase « Aucune lecture faite dans Moduléo… » de l'outil (`lire_fiches`, `sans_lecture`), qui interdit d'inventer et dit de demander un critère (#182).
- **Inspecteur** : échange `local` `outil:<nom>` : arguments, `fiches`, `routes` (route et paramètres de chaque lecture), `erreur` éventuelle. Jamais la clé ni le SecurityCode : ils restent dans les en-têtes de `ClientModuleo`.

| Outil | Ce qu'il fait | Depuis |
| --- | --- | --- |
| `chercher_affaires_moduleo` ([`affaires/`](affaires/README.md)) | Retrouve des affaires par numéro, par texte ou par filtres en noms (état, dates, site, service, responsable, chargé d'affaire, dossier de production) ; une Fiche Moduléo par affaire. | 1.5.0 (#174, #175) |
| `chercher_contacts_moduleo` ([`contacts/`](contacts/README.md)) | Retrouve des contacts par texte, type de contact, type de donneur d'ordre ou qualifications en noms ; une Fiche Moduléo par contact (type, nom, téléphones, emails, adresses, numéros des affaires où il est client ou intervenant). | 1.5.0 (#176) |
