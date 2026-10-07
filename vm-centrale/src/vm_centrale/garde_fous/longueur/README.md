# longueur

`plafonner` plafonne un texte à la dernière fin de phrase (`.`, `!`, `?`, `…`) sous un maximum ; coupe brute seulement s'il n'y a aucune fin de phrase sous le maximum.

**Appelant.** `routers/conversations.py`, `envoyer_message`, sur `resume_contexte` (1 500 caractères) et sur `profil_travail` (800 caractères), en dur, avant persistance. Les résumés déjà en base ne sont pas touchés ; les profils hérités sont vidés une fois par `scripts/vider_profils_travail.py`.

**Depuis.** 1.3.1. Origine : #110, conversation 76 : le résumé glissant gardait le rapport inventé et le sujet abandonné (« oublie Citrix ») ; le profil empilait onze deltas, doublons et traits de l'assistant.

Code : `garde_fou.py`.
