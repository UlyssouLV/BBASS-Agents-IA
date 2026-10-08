# Les droits Moduléo sont recopiés dans BBASS et appliqués par un garde fermé par défaut

En 1.5.0 ([ADR-0017](./0017-lecture-moduleo-par-outil.md)), une seule clé d'API et le SecurityCode d'un utilisateur de test servent à tous les comptes : ce que voit le chat est ce que voit cet utilisateur. La V1.5.1 ([spec 1.5.1](../specs/v1.5.1-lire-plus-de-donnees-moduleo.md)) ouvre devis, factures, temps passés et planning ; avec ce modèle, tout collaborateur lirait le chiffre d'affaires du cabinet et les heures de ses collègues.

Dans Moduléo, les droits d'un utilisateur viennent de son groupe Cogeo et de son groupe Planning. Deux faits ferment les autres voies : **les droits de la clé d'API font foi sur ceux des groupes utilisateur**, et **l'API n'expose pas la matrice des droits d'un groupe** (seulement les groupes d'un utilisateur, un groupe par id et les droits de la clé en cours).

- BBASS garde **une seule clé d'API de lecture** sur la VM, pour tous les comptes ;
- le **catalogue des droits** Cogeo et Planning (libellés repris de Moduléo) et les **droits de chaque groupe** sont **recopiés** dans la base de BBASS ; un compte est rattaché à au plus un groupe Cogeo, un groupe Planning, et à son utilisateur Moduléo ; sans groupe, aucun outil Moduléo ;
- un **garde des droits** passe avant tout appel à l'API : le client exige les droits du compte, chaque route GET est classée (droit exigé ou libre), une route non classée est refusée, un outil sans droit n'est pas proposé au modèle et l'appel est revérifié ; les fiches retirent les champs qu'un sous-droit interdit ; droits lus une fois par tour, vérifiés en mémoire.

Alternatives écartées :
- **Un SecurityCode par collaborateur, une seule clé** : Moduléo appliquerait les droits de la clé, pas ceux des groupes de l'utilisateur ; les droits réels ne seraient pas respectés.
- **Une clé d'API par collaborateur**, réglée dans Moduléo : plus sûre (une fuite de la VM ne livre pas tout), mais chaque clé se règle à la main et doublonne les groupes ; gardée comme piste si Kipaware change la priorité des droits.
- **Filtrer sans recopier**, en lisant les droits dans l'API : impossible, la matrice d'un groupe n'est pas exposée.
- **Garde ouvert par défaut** (seules les routes sensibles listées) : une route ajoutée par une mise à jour de l'API serait lisible sans décision.

## Consequences

- Ce que voit le chat dépend du groupe du compte, plus de l'utilisateur de test (amende ADR-0017).
- La copie peut dériver : quand un droit change dans Moduléo, il faut le changer dans BBASS (fichier versionné en 1.5.1, Panel d'administration en 1.5.3). Un groupe ou un droit absent vaut refus.
- La clé de la VM lit tout ce que ses catégories permettent : sa protection (chiffrement Fernet, clé maître hors du dépôt) porte toute la sécurité côté VM. Elle reste en lecture seule ; toute écriture (1.5.2) passe par une nouvelle décision et le serveur de test.
- Les restrictions par affaire (« Limiter l'accès à des affaires aux autres collaborateurs ») ne sont pas recopiées : hors périmètre tant qu'elles ne le sont pas.
- `MISTRAL_API_KEY` est chiffrée avec la même clé maître (fin de l'exception notée dans ADR-0017) ; la clé maître devient obligatoire pour démarrer la VM.
