# Relecture isolée d'une réponse après un retrait de garde-fou

Jusqu'à la V1.6.2, quand le modèle invente un chiffre ou une source, les garde-fous ([V1.3.1](../specs/v1.3.1-chat-ne-fige-plus-ses-inventions.md), [V1.4.0](../specs/v1.4.0-recherche-web-dans-le-chat.md)) retirent ce qui ne figure pas dans les résultats d'outils, et le collaborateur lit une réponse trouée ([#131](https://github.com/UlyssouLV/BBASS-Agents-IA/issues/131)). La V1.6.3 ([spec](../specs/v1.6.3-corriger-les-bugs-existants.md)) ajoute une **relecture** : quand un garde-fou a retiré quelque chose, la VM fait un appel Mistral à part, isolé de la conversation, sur le même principe que l'extraction ([ADR-0014](./0014-recherche-web-en-deux-temps-extraction-isolee.md)).

- **Déclenchement** : seulement si un garde-fou a retiré quelque chose. Une seule relecture par réponse.
- **Entrée** : la question, la réponse avec ses marqueurs « [non trouvé] », les résultats d'outils (extraits, statuts des pages, pièce jointe). Ni l'historique, ni le profil, ni le résumé glissant.
- **Consigne** : réécrire en ne gardant que ce que ces extraits contiennent, dire ce qui n'a pas été trouvé et où on a cherché, n'ajouter aucun chiffre, aucune source, aucun fait. Appel sans outils.
- **Contrôle** : les garde-fous repassent sur la sortie. Rien de retiré : la relecture est retenue. Un retrait, ou un appel en erreur : la réponse d'origine est affichée, avec ses marqueurs et une phrase fixe.
- **Traçabilité** : ligne d'inspecteur (entrée, sortie, retenue ou écartée) et ligne de consommation.

Ce sont les garde-fous, déterministes, qui ont le dernier mot : la relecture n'est retenue que si elle ne leur fait rien retirer.

## Alternatives écartées

- **Marqueurs et phrase fixe seuls** : rien de faux ne passe, mais la réponse reste un brouillon troué. Gardé comme secours.
- **Relecture à chaque réponse qui utilise un outil** : un appel et quelques secondes de plus sur toutes ces réponses, y compris celles que les garde-fous n'ont pas touchées.
- **Remplacer toute la réponse par « Je n'ai pas trouvé » au-delà d'un seuil** : perd ce qui avait bien été trouvé.
- **Relancer le modèle principal dans la conversation** : il garde dans son contexte l'historique qui l'a poussé à inventer, et peut rappeler des outils.
