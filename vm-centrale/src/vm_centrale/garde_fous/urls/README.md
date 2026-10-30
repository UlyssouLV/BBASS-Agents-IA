# urls

`retirer_urls_inventees` remplace par le marqueur « [non trouvé] » toute URL de la réponse de chat absente des textes du compte (tous ses messages `user` de la conversation en base, plus le nouveau message du tour) et des résultats de recherche de la conversation (table `resultats_recherche_web`, ce tour compris, page téléchargée ou non : depuis 1.4.0).

**Règles.**

- Lien Markdown `[texte](url)` et URL nue inventés deviennent le marqueur : le texte du lien ne reste pas, il passerait pour une source (depuis 1.6.3 ; avant, le texte restait : « comme le confirme : Leboncoin – Centre d'aide – Facturation », #131). Plusieurs liens inventés à la suite (séparés par `,` ou `;`) font un seul marqueur. Une parenthèse qui ne contenait que des liens inventés part entière, espaces qui la précèdent compris : jamais `()` (`**Météo France** ([www.meteofrance.com](…))` devenait `**Météo France** ()`).
- Le résultat (`Retrait`) dit si une URL a été retirée : phrase fixe en fin de réponse (voir [l'index](../README.md)).
- Comparaison sans schéma, `www.`, casse ni `/` final (`normaliser_url`).
- Une paire de parenthèses dans l'URL en fait partie (`…/wiki/Loi_(France)`), une parenthèse seule appartient à la phrase.
- La ponctuation finale et la mise en forme Markdown collées à une URL nue (`**https://…/**`, `_`, `` ` ``) appartiennent à la phrase (depuis 1.4.1 : essai, conversation 95, une URL du compte en gras était retirée).

**Appelant.** `routers/conversations.py`, `_reponse_sans_url_inventee`, sur la réponse finale de chat (y compris après un tour de tool calling) de `creer_conversation` et `envoyer_message`, avant titrage, persistance et réponse au poste.

**Depuis.** 1.3.1 (résultats de recherche : 1.4.0). Origine : #110, conversation 76 : rapport OCDE et onze liens « téléchargeables » inventés, sans accès à Internet. Résultats autorisés : spec 1.4.0, décision n° 11 (le titre et l'extrait du moteur sont une vraie trace de la page).

**Repérage des URL du compte.** `urls_ecrites` n'est pas un garde-fou : il est partagé avec `routers/conversations._memoire_de_la_conversation`, qui liste dans la Mémoire de la conversation les URL écrites par le compte avec la même règle que `retirer_urls_inventees` (spec 1.4.1, #134). `normaliser_url` et `urls_ecrites` servent aussi à `lire_pages_web`.

Code : `garde_fou.py`. Ses motifs d'URL (`_MOTIF_LIEN_MARKDOWN`, `_MOTIF_URL_NUE`) sont repris par le garde-fou [`chiffres/`](../chiffres/README.md).
