# refus_des_droits

`montrer_refus_des_droits` met en tête de la réponse de chat chaque phrase du garde des droits Moduléo renvoyée par un outil du tour (« Votre compte n'a pas le droit Moduléo « Rechercher des contacts ». Aucune lecture n'a été faite. … », « … Rien n'a été écrit. … »), telle quelle, quand la réponse ne la contient pas déjà. Le modèle peut ajouter du texte autour, mais ne la remplace pas.

**Règles.**

- Une phrase de refus vient d'un résultat d'outil dont la trace porte `garde_des_droits` (lecture, `decrire_ecriture_moduleo`, `ecrire_moduleo`, relecture de l'élément visé) : `routers/conversations._executer_appels_outils` la range dans `ContexteTour.refus_des_droits`.
- Déjà présente mot pour mot dans la réponse : rien ne change.
- Sinon, les phrases de la réponse (coupées sur `.`, `!`, `?`, ligne par ligne) qui nomment un droit, un accès, une autorisation, une permission ou un administrateur partent, et chaque phrase de refus manquante passe en tête, une par paragraphe, sans doublon. Le reste du texte du modèle suit.
- Une phrase fixe de la VM (chiffres, contact non lu, écriture non proposée) cède la place aux phrases du refus, qui disent mieux pourquoi rien n'a été lu ou écrit.

**Appelant.** `routers/conversations.py`, `_reponse_visible`, après `_appliquer_garde_fous` (la phrase ajoutée par le code n'est pas relue comme un texte du modèle) et avant `ajouter_sources` et `mentionner_pages_trop_longues`, sur la réponse finale de chat de `creer_conversation` et `envoyer_message`. La carte au clic (refus à la confirmation) montre déjà la phrase fixe : ce garde-fou ne la concerne pas.

**Depuis.** 1.5.2 (#262). Origine : second passage des tests humains #206, scénarios 20 et 20 bis : l'outil renvoyait bien la phrase qui nomme le droit, mais le chat affichait « Je n'ai pas accès à la recherche des contacts dans Moduléo. Veuillez transmettre cette demande à un administrateur du système. » et « Je ne peux pas modifier cette tâche : votre compte Moduléo n'a pas les droits nécessaires. ».

Limite connue : une phrase du modèle qui parle d'accès ou de droits sur autre chose (« l'accès au chantier se fait par le nord ») part aussi, dans un tour où un outil a été refusé.

Code : `garde_fou.py`.
