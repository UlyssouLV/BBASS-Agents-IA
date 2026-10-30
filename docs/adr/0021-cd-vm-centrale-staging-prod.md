# CD de la VM centrale : images GHCR, staging et prod, mise à jour au redémarrage

Jusqu'à la V1.6.0, la VM centrale ne tournait que depuis un clone du dépôt (`lancer-vm.*` : venv Python sur la machine, Postgres et SearXNG par Docker, compte de test semé). La CI prouvait qu'un SHA était vert ([ADR-0020](./0020-ci-argos-compartimentee.md)), mais rien ne reliait une Release à ce qui tourne à Castries. La V1.6.1 ([spec](../specs/v1.6.1-cd-vm-castries.md)) livre la VM en conteneurs et la met à jour sans le dépôt :

- **Machine** : Ubuntu Server 26.04 LTS (support jusqu'en 2031, 2036 avec Ubuntu Pro, gratuit jusqu'à 5 machines), Docker Engine + Compose. Cohérent avec ArgOS et le pack.
- **Images** : `vm-centrale` et `searxng`, construites par la CI à chaque Release et publiées **publiques** sur GHCR avec le tag `vX.Y.Z`. Le dépôt est public et les images ne contiennent aucun secret : une image privée imposerait un token à renouveler sans rien protéger.
- **Deux Environnements sur la même VM** (staging en 8001, prod en 8000), séparés par dossier (`/opt/bbass/<env>`, `/etc/bbass/<env>/cle-maitre`), une clé maître chacun. Staging lit le serveur de test Moduléo.
- **Promotion par étiquette** : une Release pose `staging` ; le workflow manuel « Promouvoir en prod » pose `prod` sur les mêmes images, sans rebuild, et refuse une version jamais passée par `staging`. Retour arrière = promouvoir l'ancienne version.
- **Mise à jour en pull** : `mettre-a-jour <env>` ou un redémarrage de la VM télécharge l'étiquette de l'Environnement, sauvegarde la base si la version change, vérifie `GET /sante` et remet les images précédentes en cas d'échec. Les fichiers de déploiement voyagent dans l'image ; le `.env` n'est jamais écrasé.
- **Secrets** : format Fernet inchangé ([ADR-0017](./0017-lecture-moduleo-par-outil.md), [ADR-0018](./0018-droits-moduleo-appliques-par-bbass.md)) ; l'installateur demande les clés en clair et les chiffre lui-même.
- **Tâches planifiées** : une convention unique — une sous-commande `tache <nom>` + une ligne dans `taches-planifiees.conf` → un timer systemd `bbass-<env>-<nom>` généré.

Alternatives écartées :

- **Paquet Python + service systemd (sans image)** : Python et `uv` à maintenir sur le serveur, procédure différente pour BBASS et pour Postgres / SearXNG déjà conteneurisés.
- **Images construites sur la VM** : exige les sources sur la machine ; ce qui tourne ne serait plus les octets testés par la CI.
- **Push depuis GitHub (runner auto-hébergé à Castries)** ou **pull automatique périodique** : la VM n'est pas joignable depuis Internet ([ADR-0003](./0003-v1-scope-castries-seule.md)) et le cabinet garde le choix de l'heure de bascule. Reporté (Plus tard).
- **Debian** : légèrement plus légère, gain marginal pour 3 conteneurs ; casse la cohérence avec ArgOS. **Windows Server** : conteneurs Linux mal supportés.
- **Alembic** : pas encore nécessaire, le schéma n'a jamais fait qu'ajouter tables et colonnes ([ADR-0008](./0008-postgresql-vm-centrale.md)). Déclencheur : la première version qui renomme ou supprime une colonne.
- **Cron, ou conteneur dédié aux tâches** : systemd est déjà là pour le démarrage, et donne un journal par tâche.

## Consequences

- La restauration d'une sauvegarde reste **manuelle** : un retour automatique écraserait des messages écrits depuis la mise à jour.
- Staging et prod partagent la machine : un staging gourmand ralentit la prod. Passer à deux VM ne change que l'emplacement des dossiers.
- Sauvegardes sur le même disque que la base : elles protègent contre une mise à jour ratée, pas contre la perte de la VM (copie hors VM : Plus tard).
- Le check `build-image-vm` s'ajoute aux checks requis du ruleset `main` (geste humain ci-dessous).

## Guide — ajouter `build-image-vm` au ruleset `main`

Geste **humain** (admin du dépôt), même écran que le guide de l'[ADR-0020](./0020-ci-argos-compartimentee.md) : **Settings** → **Rules** → **Rulesets** → ruleset de `main` → **Require status checks to pass** → ajouter `build-image-vm` (nom tel qu'affiché sur la PR de la 1.6.1) → sauver.

## Guide — rendre les images publiques (une fois par paquet)

Geste **humain** (propriétaire du dépôt), une seule fois, après la première exécution de **Publier les images VM** : un paquet GHCR nouveau naît privé, et la VM tire les images sans token. Le workflow le vérifie et échoue tant que les deux paquets ne sont pas publics.

Pour `bbass-vm-centrale` puis `bbass-vm-searxng` : profil GitHub → **Packages** → le paquet → **Package settings** → **Danger Zone** → **Change visibility** → **Public**. Puis relancer le workflow échoué (**Re-run jobs**) : il reconstruit `vX.Y.Z` et pose `staging`.

## Guide — promouvoir en prod, revenir en arrière

**Actions** → **Promouvoir en prod** → **Run workflow** → version `vX.Y.Z`. Le workflow pose `prod` sur les images `vX.Y.Z` (même digest) et refuse une version qui n'a jamais porté `staging` (trace : tag `staging-vX.Y.Z`, posé par **Publier les images VM**). Revenir en arrière : promouvoir l'ancienne version. Chaque promotion reste dans l'historique **Actions** (titre : version et auteur ; date du run).
