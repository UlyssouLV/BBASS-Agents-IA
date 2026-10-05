# Garde-fous

Corrections que le code applique à ce que le modèle produit **malgré sa consigne**. Une consigne seule ne garantit rien : chaque garde-fou garantit dans le code un résultat que le prompt demande déjà.

Chaque garde-fou est une fonction pure (texte en entrée, texte en sortie), appelée à un seul endroit. Ajouter, déplacer ou retirer un garde-fou met à jour ce fichier dans le même commit (`agents/domain.md`, « Centralised packages »).

| Garde-fou | Ce qu'il corrige | Où il est appelé | Depuis | Origine |
| --- | --- | --- | --- | --- |
| `titre.nettoyer_titre` | Retire la mise en forme Markdown (`#`, `**`, `__`, `*`, `_`) du titre généré : le titre s'affiche en texte brut côté poste. Un `*` ou `_` incident (`10*2`, `mon_profil`) est conservé. | `routers/conversations.py`, `creer_conversation`, sur la réponse de titrage. Jamais sur un renommage manuel. | 1.2.2 (déplacé ici en 1.3.1) | Validation manuelle 1.2.2 : le titrage reprenait le gras de la réponse résumée. |
| `urls.retirer_urls_inventees` | Retire de la réponse de chat toute URL absente des textes du compte (tous ses messages `user` de la conversation en base, plus le nouveau message du tour). Lien Markdown `[texte](url)` : le texte reste, le lien part. URL nue : supprimée. Comparaison sans schéma, `www.`, casse ni `/` final. | `routers/conversations.py`, `_reponse_sans_url_inventee`, sur la réponse finale de chat (y compris après un tour de tool calling) de `creer_conversation` et `envoyer_message`, avant titrage, persistance et réponse au poste. | 1.3.1 | #110, conversation 76 : rapport OCDE et onze liens « téléchargeables » inventés, sans accès à Internet. |
