# Le catalogue et les groupes Moduléo BBASS vivent en base

En 1.5.1 ([ADR-0018](./0018-droits-moduleo-appliques-par-bbass.md)), le catalogue des cases et les groupes (Admin) sont semés depuis un fichier versionné **à chaque démarrage** : les droits des groupes présents dans le fichier sont **réécrits**. Le rattachement d'un compte passe par un script. La V1.5.3 ouvre l'administration des **groupes** au compte administrateur dans le Panel (onglet Outils → Moduléo).

Les cases du catalogue ne sont **pas** des droits Moduléo « vivants » : l'API n'expose pas la matrice d'un groupe, BBASS ne fait que recopier des libellés pour que l'admin coche comme dans Moduléo. Les **réécrire depuis un fichier à chaque boot** n'apporte rien une fois la base remplie, et **écraser les groupes** empêcherait le Panel.

- **Cases et groupes** vivent **uniquement en base** après le passage 1.5.3.
- **Migration unique** : au déploiement 1.5.3 (ou premier démarrage encore vide de cases), on importe une dernière fois depuis `catalogue.json` (référentiel figé de la 1.5.1), puis le **boot ne relit plus** ce fichier pour synchroniser cases ni groupes.
- Les **groupes** et leurs **droits accordés** sont créés et modifiés **seulement** par le Panel ; le démarrage ne les réécrit plus.
- Si la base n'a **aucun** groupe, on sème encore **Admin** (Cogeo et Planning) une fois (à partir des droits déjà en base / du dump de migration).
- Le Panel **ne crée pas / n'édite pas** le catalogue des cases : inventer une case BBASS sans lien avec Moduléo n'a aucune valeur. Une évolution du catalogue Moduléo (nouveau libellé) est une **intervention dév** (migration / script one-shot), pas un geste admin.
- « Tous droits (dev) » reste hors Panel.
- Un **journal minimal** enregistre les changements admin sur groupes et rattachements.

Alternatives écartées :
- **Continuer à synchroniser les cases depuis le fichier à chaque boot** : double source de vérité inutile une fois la base peuplée ; risque de retirer des cases encore utilisées sans geste explicite.
- **L'admin édite le catalogue des cases dans le Panel** : aucune valeur sans lien API vers les vrais droits Moduléo (ADR-0018).
- **Détection automatique de dérive** vs Moduléo : impossible tant que l'API ne donne pas les droits d'un groupe.
- **Garder le script de rattachement comme voie officielle** : deux sources de vérité.

## Consequences

- Amende ADR-0018 : ni les **groupes** ni le **catalogue des cases** ne sont plus tenus à jour par un rechargement fichier à chaque démarrage ; la base est la source de vérité runtime.
- Un redémarrage conserve cases, groupes et rattachements.
- `catalogue.json` peut rester dans le dépôt comme **source de la migration unique** / archive, plus comme chargeur de boot.
- Le script de rattachement n'est plus la voie d'administration du cabinet.
