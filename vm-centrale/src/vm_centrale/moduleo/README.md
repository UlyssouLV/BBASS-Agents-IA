# moduleo

Intégration Moduléo de la VM centrale, commune à tous les outils (et plus tard à n8n, 1.8.0). Spec 1.5.0, [ADR-0017](../../../../docs/adr/0017-lecture-moduleo-par-outil.md).

**Lecture seule.** Les droits d'une clé d'API Moduléo se règlent par catégorie (Affaire, Contact…), pas en lecture / écriture : seul ce client garantit que la VM ne modifie rien sur le serveur du cabinet. Toute écriture future (POST / PUT / DELETE) passe par une nouvelle décision et un serveur Moduléo de test.

| Élément | Rôle | Depuis |
| --- | --- | --- |
| `client.py` | `ClientModuleo(url, api_key, security_code).lire(route, paramètres)` : GET sur `MODULEO_URL` (`config.py`) avec les en-têtes `ApiKey` et `SecurityCode`, délai `MODULEO_HTTP_TIMEOUT`, JSON renvoyé. Refuse **avant tout envoi** (`RequeteInterdite`) toute méthode autre que GET, toute route absente de `ROUTES_GET`, un paramètre absent de la route ou un paramètre de chemin manquant. Paramètres de requête facultatifs (`None` = non envoyé). Délai dépassé, serveur injoignable, autre statut d'erreur ou réponse non JSON : `ModuleoIndisponible` (panne) ; 401 / 403 : `ModuleoRefuse` (refus). Aucune nouvelle tentative. | 1.5.0 (#172) |
| `routes.py` | **Généré** : `ROUTES_GET`, les gabarits de toutes les routes GET du WADL (207 au 2026-10-07), sans le préfixe `api/` déjà porté par `MODULEO_URL`, aucune autre méthode. | 1.5.0 (#172) |
| `docs/wadl.xml`, `docs/documentation.html` | Copies du WADL et de la page de documentation du serveur du cabinet, datées dans l'en-tête de `routes.py` et de l'index. | 1.5.0 (#172) |
| `docs/index-routes.md` | **Généré** : une ligne par route GET, par catégorie de la page de doc (paramètres et type, description en français). Point d'entrée pour ajouter une capacité sans dépendre du serveur de doc. | 1.5.0 (#172) |

Une route s'écrit comme dans le WADL : `client.lire("cogeo/affaire/{idAffaire}", {"idAffaire": 12})`, `client.lire("cogeo/affaire?texte={texte}&…&nbMaxResultats={nbMaxResultats}", {"texte": "Castries", "nbMaxResultats": 5})`.

**Régénérer** (nouvelle version de l'API, autre serveur) : `python scripts/telecharger_doc_moduleo.py` depuis `vm-centrale/`. Retélécharge le WADL et la page depuis `MODULEO_URL/documentation` (publics, sans clé), régénère `routes.py` et `index-routes.md`, puis lancer les tests (`tests/test_client_moduleo.py` vérifie la table contre le WADL versionné). Ne jamais modifier les fichiers générés à la main.
