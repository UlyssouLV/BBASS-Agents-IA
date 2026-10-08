# moduleo

Intégration Moduléo de la VM centrale, commune à tous les outils (et plus tard à n8n, 1.8.0). Spec 1.5.0, [ADR-0017](../../../../docs/adr/0017-lecture-moduleo-par-outil.md).

**Lecture seule.** Les droits d'une clé d'API Moduléo se règlent par catégorie (Affaire, Contact…), chacune en lecture ou en lecture et écriture : la clé BBASS ne coche que la lecture. Ce client est la seconde barrière : il garantit que la VM ne modifie rien sur le serveur du cabinet, même avec une clé mal réglée. Toute écriture future (POST / PUT / DELETE) passe par une nouvelle décision et un serveur Moduléo de test.

| Élément | Rôle | Depuis |
| --- | --- | --- |
| `client.py` | `ClientModuleo(url, api_key, security_code).lire(route, paramètres)` : GET sur `MODULEO_URL` (`config.py`) avec les en-têtes `ApiKey` et `SecurityCode`, délai `MODULEO_HTTP_TIMEOUT`, JSON renvoyé. Refuse **avant tout envoi** (`RequeteInterdite`) toute méthode autre que GET, toute route absente de `ROUTES_GET`, un paramètre absent de la route ou un paramètre de chemin manquant. Paramètres de requête facultatifs (`None` = non envoyé). Délai dépassé, serveur injoignable, autre statut d'erreur ou réponse non JSON : `ModuleoIndisponible` (panne) ; 401 / 403 : `ModuleoRefuse` (refus). Aucune nouvelle tentative. 404 : `ModuleoIntrouvable`, une panne pour qui ne l'attend pas (1.5.0, #174). `get_client_moduleo()` : dépendance FastAPI des envois de message, le client configuré ou `None` (lu une fois par processus) ; `LecteurModuleo` : ce que les outils en connaissent, remplacé par `tests/faux_moduleo.py` dans les tests. | 1.5.0 (#172) |
| `configuration.py` | `config_moduleo()` : seul point qui dit si Moduléo est configuré. Renvoie `ConfigModuleo(url, api_key, security_code)` en clair (secrets masqués dans son `repr`), ou `None` si `MODULEO_URL`, `MODULEO_API_KEY_CHIFFREE`, `MODULEO_SECURITY_CODE_CHIFFRE` ou `VM_CLE_MAITRE_FICHIER` manque, si la clé maître est absente ou illisible, ou si un secret ne se déchiffre pas (`vm_centrale/secrets_chiffres.py`, Fernet). Ne lève jamais : journalise la variable en cause, jamais une valeur ; appelé au démarrage de la VM. | 1.5.0 (#173) |
| `resolution.py` | Ids Moduléo → noms, dédoublonnés sur tout un appel d'outil : `resoudre_utilisateurs` (`moduleo/utilisateur/{id}`, une lecture par id : nom, téléphones, email), `resoudre_contacts` (`cogeo/contact/multi`), `resoudre_communes` (`moduleo/commune/multi`, « Castries (34160) »). Un id inconnu (404, absent d'une réponse `multi`) n'a pas de nom. Noms → ids, pour les filtres (#175) : `chercher_utilisateur` (`moduleo/utilisateur?nom=&prenom=` ; « Martin », « Sophie », « Jean Martin », « Martin Jean », « Le Gall » : premier essai qui trouve), `chercher_sites` / `chercher_services` (`moduleo/site?nom=`, `moduleo/service?nom=` ; tous les ids du nom, séparés par une virgule), `chercher_dossier_production` (`fileo/dossierproduction?texteRecherche=`), `chercher_qualifications` (`cogeo/qualification/all` ; libellé exact, sinon le seul qui contient le nom, #176). Aucun élément, ou plusieurs utilisateurs / dossiers de production / qualifications : `NomNonResolu`, dont le message (candidats nommés, 10 au plus) va tel quel au modèle. | 1.5.0 (#174, #175, #176) |
| `fiches.py` | Fiche Moduléo : `fiche_affaire` (numéro, objet, état, dates au format JJ/MM/AAAA, adresse, commune, client, représentant, responsable et chargé d'affaire avec leurs coordonnées, intervenants avec leur qualité et leur représentant), en noms, jamais un id ni la réponse brute ; un champ vide n'a pas de ligne ; référence « affaire 2024-123 », citée par la ligne « Sources : ». `fiche_contact` (type, nom, téléphones, emails et adresses avec leur lieu, numéros des affaires dont il est client ou intervenant, 20 au plus par rôle), référence « contact Étude Dupont », #176. Chaque fiche porte ses questions couvertes, écrites par gabarit champ par champ, sans appel Mistral (objet, état, dates, lieu, client, suivi, intervenants d'une affaire ; « Comment joindre », adresse, affaires d'un contact) ; un champ vide n'a pas de question, #177. Depuis #180 : état et type de contact en libellés (`enumerations.py`), un champ tient sur une ligne (retours à la ligne en espaces), pas de ligne « Adresse » qui ne fait que répéter la commune. | 1.5.0 (#174, #176, #177, #180) |
| `enumerations.py` | Énumérations Moduléo : entier du JSON, nom en filtre, libellé de l'interface (tableau ci-dessous). `libelle` (fiche ; valeur inconnue en chiffre), `nom_api` (filtres `etat` et `type_contact` des outils, casse, accents, ponctuation et accord indifférents ; `None` si inconnu : l'outil refuse la recherche, car Moduléo ignore un nom inconnu sans erreur et renverrait tout). | 1.5.0 (#180) |
| `routes.py` | **Généré** : `ROUTES_GET`, les gabarits de toutes les routes GET du WADL (207 au 2026-10-07), sans le préfixe `api/` déjà porté par `MODULEO_URL`, aucune autre méthode. | 1.5.0 (#172) |
| `docs/wadl.xml`, `docs/documentation.html` | Copies du WADL et de la page de documentation du serveur du cabinet, datées dans l'en-tête de `routes.py` et de l'index. | 1.5.0 (#172) |
| `docs/index-routes.md` | **Généré** : une ligne par route GET, par catégorie de la page de doc (paramètres et type, description en français). Point d'entrée pour ajouter une capacité sans dépendre du serveur de doc. | 1.5.0 (#172) |

**Énumérations** (#180). Relevées le 2026-10-08 sur le serveur du cabinet par `python scripts/relever_enumerations_moduleo.py` (depuis `vm-centrale/`, lecture seule, `.env` du compte administrateur) : pour chaque nom candidat, une recherche filtrée par ce nom, puis la valeur JSON des éléments trouvés. Un nom inconnu est ignoré par Moduléo (même résultat que sans filtre) : le script le signale. L'ordre ne suit ni l'interface ni le WADL, et les filtres d'état sont au féminin (`Acceptee`, pas `Accepte` du WADL).

| `Etat` (JSON) | `etatAffaire` (filtre) | Interface |
| --- | --- | --- |
| 4 | `Creee` | Créée |
| 8 | `EnAttente` | En attente |
| 7 | `Acceptee` | Acceptée |
| 1 | `Production` | Production |
| 9 | `Suspendue` | Suspendue |
| 5 | `Terminee` | Prod. terminée |
| 2 | `Cloturee` | Clôturée |
| 6 | `Annulee` | Annulée |

| `TypeContact` (JSON) | `typeContact` (filtre) | Interface |
| --- | --- | --- |
| 1 | `Personne` | Personne |
| 3 | `Societe` | Société |
| 4 | `Collectivite` | Collectivité |
| 5 | `GroupeContacts` | Groupe de contacts |

`Etat` 3 et `TypeContact` 2 n'ont pas été rencontrés : affichés en chiffre. Relancer le script après une mise à jour de Moduléo.

Une route s'écrit comme dans le WADL : `client.lire("cogeo/affaire/{idAffaire}", {"idAffaire": 12})`, `client.lire("cogeo/affaire?texte={texte}&…&nbMaxResultats={nbMaxResultats}", {"texte": "Castries", "nbMaxResultats": 5})`.

**Régénérer** (nouvelle version de l'API, autre serveur) : `python scripts/telecharger_doc_moduleo.py` depuis `vm-centrale/`. Retélécharge le WADL et la page depuis `MODULEO_URL/documentation` (publics, sans clé), régénère `routes.py` et `index-routes.md`, puis lancer les tests (`tests/test_client_moduleo.py` vérifie la table contre le WADL versionné). Ne jamais modifier les fichiers générés à la main.

**Secrets** (ADR-0017) : la clé d'API et le SecurityCode sont chiffrés dans `.env`, la clé maître est un fichier hors du dépôt (`VM_CLE_MAITRE_FICHIER`). `python scripts/chiffrer_secret.py MODULEO_API_KEY_CHIFFREE` depuis `vm-centrale/` crée la clé maître si le fichier n'existe pas (jamais ne l'écrase), demande le secret sans l'afficher et imprime la ligne à coller dans `.env` ; idem pour `MODULEO_SECURITY_CODE_CHIFFRE`. Perdre la clé maître oblige à rechiffrer avec une nouvelle clé d'API ou un nouveau code créés dans Moduléo.
