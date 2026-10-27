# Les groupes Moduléo BBASS sont administrés en base depuis le Panel

En 1.5.1 ([ADR-0018](./0018-droits-moduleo-appliques-par-bbass.md)), le catalogue des cases et les groupes (Admin) sont semés depuis un fichier versionné à chaque démarrage : les droits des groupes présents dans le fichier sont **réécrits**. Le rattachement d'un compte passe par un script. La V1.5.3 ouvre l'administration au compte administrateur dans le Panel (onglet Outils → Moduléo).

Deux besoins s'opposent si l'on garde l'écrasement au boot : **tenir** les réglages faits dans le Panel, et **mettre à jour** le catalogue des cases quand Moduléo ajoute ou retire un droit (toujours via le dépôt, l'API n'exposant pas la matrice d'un groupe).

- le fichier versionné ne porte plus que le **catalogue des cases** (libellés, arborescence, conditions possibles Planning) ; le boot les ajoute / met à jour / retire (une case retirée disparaît aussi des groupes qui l'accordaient) ;
- les **groupes** et leurs **droits accordés** vivent **uniquement en base**, créés et modifiés par le Panel ; le démarrage **ne les réécrit plus** ;
- si la base n'a **aucun** groupe, on sème encore **Admin** (Cogeo et Planning) une fois, pour ne pas laisser une install neuve sans point de départ ;
- « Tous droits (dev) » reste un groupe local créé hors Panel (dev / tests), jamais semé en production au boot ;
- un **journal minimal** (qui, quand, action, cible) enregistre les changements admin, sans export en 1.5.3.

Alternatives écartées :
- **Le Panel écrit aussi dans le fichier versionné** : mélange dépôt et runtime, conflits de merge, et n'aide pas une VM déjà déployée.
- **L'admin édite le catalogue des cases dans le Panel** : source de vérité double avec Moduléo ; trop fragile sans API de matrice.
- **Détection automatique de dérive** vs Moduléo : impossible tant que l'API ne donne pas les droits d'un groupe (ADR-0018).
- **Garder le script comme voie officielle parallèle** : deux sources de vérité pour les rattachements.

## Consequences

- Amende ADR-0018 : pour les **groupes**, la copie ne se met plus à jour « fichier versionné puis Panel » — le Panel (base) est la voie ; le fichier reste pour les **cases**.
- Un redémarrage conserve les groupes réglés dans le Panel.
- Une nouvelle case déployée via `catalogue.json` apparaît à cocher ; elle n'est pas accordée automatiquement aux groupes existants (absent = refus).
- Le script de rattachement n'est plus la voie d'administration du cabinet.
