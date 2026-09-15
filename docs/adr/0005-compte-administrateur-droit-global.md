# Compte administrateur : un droit global, jamais limité à un pôle

V1 posait « un seul rôle plat pour tous les comptes ». V1.1 introduit `est_admin` sur `Compte` : un droit de gérer les autres comptes (créer, modifier, supprimer, promouvoir/rétrograder un autre compte administrateur, forcer une déconnexion). Ce droit est global — un compte administrateur agit sur n'importe quel compte, quel que soit son pôle ou son agence. On a écarté un droit limité au pôle de l'administrateur pour ne pas construire une logique d'autorisation scindée par pôle avant qu'un agent réel n'en ait besoin. Le pôle nommé « Administration » (un des six pôles du cabinet, voir `CONTEXT.md`) est une valeur de pôle ordinaire, sans lien avec ce droit — les deux sens du mot ne doivent jamais être confondus.

## Consequences

Une évolution future vers une autorité limitée à un pôle (ex. dans le cadre des droits par agent pôle par pôle) devra rouvrir cette décision plutôt que de la contourner : `est_admin` reste un booléen global, pas la base d'un système de permissions scopées.
