# titre

`nettoyer_titre` retire la mise en forme Markdown (`#`, `**`, `__`, `*`, `_`) du titre généré : le titre s'affiche en texte brut côté poste. Un `*` ou `_` incident (`10*2`, `mon_profil`) est conservé.

**Appelant.** `routers/conversations.py`, `creer_conversation`, sur la réponse de titrage. Jamais sur un renommage manuel.

**Depuis.** 1.2.2 (déplacé dans `garde_fous/` en 1.3.1). Origine : validation manuelle 1.2.2 : le titrage reprenait le gras de la réponse résumée.

Code : `garde_fou.py`.
