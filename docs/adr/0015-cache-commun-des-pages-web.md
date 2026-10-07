# Les pages web lues sont gardées 24 h dans un cache commun à tous les comptes

Jusqu'à la V1.4.2, le texte nettoyé d'une page web ne vit que dans la Conversation qui l'a lue. Une même page est retéléchargée par chaque Conversation qui y arrive : délai, charge sur le site, refus possibles (limite de débit, 403) d'une page lue une heure plus tôt. La V1.4.3 ([spec 1.4.3](../specs/v1.4.3-cache-des-pages-web.md)) ajoute un **cache commun** sur la VM centrale :

- une table propre, indépendante des Conversations, avec une ligne par **URL exacte** (texte nettoyé, titre, date de téléchargement) ;
- seules les pages **lues avec succès** y entrent, jamais un échec ;
- une copie est valable **24 h**, puis ignorée et écrasée au prochain téléchargement ;
- le cache est **partagé entre tous les comptes et tous les pôles**.

Le partage est sûr parce que la VM télécharge sans cookie ni authentification : toute page qu'elle lit est publique. Un compte ne profite d'une page en cache que s'il arrive à la même URL, par une recherche ou en l'écrivant ; une URL qui porte un jeton secret ne fuit donc pas. Ce qui est partagé, c'est le **texte de la page**, jamais ce qu'un compte en a tiré : l'extrait et les Questions couvertes portent le `besoin`, donc l'intention, d'un compte, et restent dans sa Conversation.

Chaque Conversation garde sa **propre copie** du texte (`resultats_recherche_web`), une photo datée qui ne suit jamais le cache : les réponses déjà données, les Questions couvertes et le garde-fou chiffres restent cohérents avec ce que le modèle a lu. Elle ne change que sur une relecture forcée demandée dans la Conversation.

Alternatives écartées :
- **Chercher dans les `resultats_recherche_web` des autres Conversations** : le cache disparaîtrait avec une Conversation supprimée, et une Conversation lirait les lignes d'une autre.
- **Un cache par compte ou par pôle** : peu de réutilisation, pour protéger des pages déjà publiques.
- **Partager aussi l'extrait et les Questions couvertes** : fuite de l'intention d'un compte, et une erreur d'un modèle répandue dans d'autres Conversations.
- **Pointeur de la Conversation vers le cache** : la copie changerait en silence par l'action d'un autre compte, et les réponses déjà données ne correspondraient plus à la page.
- **URL normalisée** (règle du garde-fou URL) : un chemin peut tenir compte de la casse, `http` et `https` peuvent servir des pages différentes.
- **Validation par `ETag` / `Last-Modified`** : en-têtes souvent faux ou absents.

## Consequences

- Une page de moins de 24 h n'est plus retéléchargée : réponse plus rapide, aucun gain de facture (un téléchargement ne coûte rien chez Mistral).
- Une page peut être servie dans une version vieille de 24 h au plus ; le collaborateur peut demander une relecture à jour (`lire_pages_web` avec `retelecharger`).
- Aucune purge pendant une requête : un script `purger_cache_pages.py` supprime les copies expirées, à brancher sur une crontab au déploiement.
- Supprimer une Conversation ne supprime pas les pages qu'elle a mises en cache.
