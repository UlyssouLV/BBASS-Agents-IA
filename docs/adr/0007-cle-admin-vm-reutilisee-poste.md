# La clé d'administration VM, jusqu'ici jamais exposée côté poste, autorise aussi certaines actions d'un compte administrateur

La V1 décrivait la clé d'administration de la VM centrale (`VM_ADMIN_KEY`) comme un secret d'exploitation, « jamais exposé côté poste », utilisé uniquement pour la révocation forcée de tous les jetons d'un compte, sans interface d'administration. V1.1 réutilise cette même clé, saisie depuis l'interface du poste par un compte administrateur, pour confirmer les deux actions les plus sensibles de la gestion des comptes : la suppression définitive d'un compte et la promotion/rétrogradation d'un autre compte administrateur. Une clé dédiée à ces seules actions a été envisagée (elle aurait laissé l'exposition de `VM_ADMIN_KEY` inchangée) mais écartée au profit de la réutilisation de la clé existante.

## Consequences

La portée de `VM_ADMIN_KEY` change : d'un secret connu de la seule équipe technique/exploitation, elle devient connue de chaque compte administrateur. Quiconque la détient peut aussi appeler directement l'endpoint de révocation forcée existant (`DELETE /auth/jeton/{identifiant}`) en dehors de l'interface du poste. Un futur lecteur ne doit pas supposer que cette clé reste un secret réservé à l'exploitation.
