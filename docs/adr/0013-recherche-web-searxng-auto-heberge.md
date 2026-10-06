# La recherche web passe par un SearXNG auto-hébergé sur la VM, et la requête sort vers les moteurs amont

La V1.4.0 donne au modèle de chat un outil de recherche web ([spec 1.4.0](../specs/v1.4.0-recherche-web-dans-le-chat.md)). Le relais reste sur `chat/completions` : l'outil `web_search` intégré de Mistral n'existe que dans l'API Conversations, écartée en 1.1.1 (pas de Zero Data Retention, clé unique du cabinet). Il faut donc un moteur que la VM centrale interroge elle-même.

On retient **SearXNG**, méta-moteur libre, **auto-hébergé** comme service du `docker-compose.yml` de la VM (à côté de PostgreSQL, [ADR-0008](0008-postgresql-vm-centrale.md)) : image à version épinglée, `settings.yml` versionné (format JSON, limiteur coupé, écoute sur localhost seulement). Il est gratuit, sans compte, clé ni quota. Il n'a pas d'index propre : il interroge Google, Bing, DuckDuckGo, Wikipedia et d'autres, puis fusionne les résultats. Leur qualité est donc celle de ces moteurs. La VM l'appelle derrière une interface `MoteurRecherche` pour pouvoir changer de moteur sans toucher au reste.

Alternatives écartées :
- **API payantes** (Brave Search, Tavily, Serper) : coût à la requête, ou quota gratuit révocable avec compte et carte bancaire.
- **Bibliothèque `ddgs`** (DuckDuckGo) : gratuite, mais API non officielle, limitée en débit, qui peut casser du jour au lendemain.
- **Aspirer les pages de résultats de Google ou Bing** : interdit par leurs conditions d'utilisation, bloqué par captcha, cassé à chaque changement de page.

**Aucun filtre** n'est appliqué à la requête : chercher une personne ou une entreprise doit rester possible, et un filtre de noms ne serait pas fiable. Les données clients du cabinet viendront de Moduléo (1.5.0), pas d'Internet.

## Consequences

- **La requête du modèle sort du cabinet** vers les moteurs amont, via SearXNG. Seule la chaîne `requete` part (le `besoin` reste entre la VM et Mistral), mais elle peut contenir un nom tiré de la conversation. Elle est visible après coup dans l'inspecteur.
- **Le téléchargement des pages trouvées** sort aussi du cabinet, depuis la VM.
- **Pas de garantie de service** : à fort volume, un moteur amont peut bloquer SearXNG, qui bascule alors sur les autres. Le volume d'un cabinet reste raisonnable. Un moteur injoignable donne un texte d'outil « recherche indisponible », jamais une erreur.
- Aucun coût de recherche, donc **aucune ligne Consommation** pour SearXNG.
- Un service de plus à démarrer et maintenir sur la VM (démarré par les lanceurs comme PostgreSQL).
- Passer à un moteur payant plus tard revient à écrire une autre implémentation de `MoteurRecherche` et à réintroduire une ligne Consommation.
