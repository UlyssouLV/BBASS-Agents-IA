# Relais central pour la clé API Mistral

Les postes n'appellent jamais Mistral directement : ils passent par un relais porté par la VM centrale de Castries, seule dépositaire de la clé API. On a écarté l'appel direct depuis chaque poste pour éviter de distribuer une clé payante et partagée sur toutes les machines collaborateurs (impossible à révoquer poste par poste, extractible localement). La contrepartie assumée est une dépendance réseau : si la VM centrale est injoignable, le chat cesse de fonctionner pour les postes concernés. L'URL du relais est un paramètre de configuration (pas une valeur en dur), pour qu'une évolution future vers une clé par agence reste un changement de config plutôt qu'une réécriture.

## Consequences

Les limites de débit Mistral (requêtes/seconde, tokens/minute) s'appliquent au niveau du workspace Mistral et sont partagées entre toutes les clés de ce workspace : ajouter des clés ne suffit donc pas toujours à absorber plus de débit, il peut falloir des workspaces Mistral séparés selon le palier souscrit. Si le débit devient limitant, la réponse reste **plusieurs clés (ou workspaces) gérés dans la VM centrale**, jamais une clé distribuée sur les postes : l'architecture ne change pas, seule la logique de répartition entre clés (par agence, par utilisateur, par charge) reste à définir plus tard.
