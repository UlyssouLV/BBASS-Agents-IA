# urls

`retirer_urls_inventees` retire de la réponse de chat toute URL absente des textes du compte (tous ses messages `user` de la conversation en base, plus le nouveau message du tour) et des résultats de recherche de la conversation (table `resultats_recherche_web`, ce tour compris, page téléchargée ou non : depuis 1.4.0).

**Règles.**

- Lien Markdown `[texte](url)` : le texte reste, le lien part. URL nue : supprimée.
- Comparaison sans schéma, `www.`, casse ni `/` final (`normaliser_url`).
- Une paire de parenthèses dans l'URL en fait partie (`…/wiki/Loi_(France)`), une parenthèse seule appartient à la phrase.
- La ponctuation finale et la mise en forme Markdown collées à une URL nue (`**https://…/**`, `_`, `` ` ``) appartiennent à la phrase (depuis 1.4.1 : essai, conversation 95, une URL du compte en gras était retirée).

**Appelant.** `routers/conversations.py`, `_reponse_sans_url_inventee`, sur la réponse finale de chat (y compris après un tour de tool calling) de `creer_conversation` et `envoyer_message`, avant titrage, persistance et réponse au poste.

**Depuis.** 1.3.1 (résultats de recherche : 1.4.0). Origine : #110, conversation 76 : rapport OCDE et onze liens « téléchargeables » inventés, sans accès à Internet. Résultats autorisés : spec 1.4.0, décision n° 11 (le titre et l'extrait du moteur sont une vraie trace de la page).

**Repérage des URL du compte.** `urls_ecrites` n'est pas un garde-fou : il est partagé avec `routers/conversations._memoire_de_la_conversation`, qui liste dans la Mémoire de la conversation les URL écrites par le compte avec la même règle que `retirer_urls_inventees` (spec 1.4.1, #134). `normaliser_url` et `urls_ecrites` servent aussi à `lire_pages_web`.

## Limites connues (#131, correction prévue en 1.4.5)

Constatées au test humain de la 1.4.0 (conversations 90 et 91). La 1.4.0 est livrée avec.

- Le texte d'un lien inventé reste, donc le nom d'une source inventée reste affiché comme source. Quand ce texte est lui-même une URL (`[www.meteofrance.com](…)`), la passe « URL nue » le retire et laisse `()`.

Code : `garde_fou.py`. Ses motifs d'URL (`_MOTIF_LIEN_MARKDOWN`, `_MOTIF_URL_NUE`) sont repris par le garde-fou [`chiffres/`](../chiffres/README.md).
