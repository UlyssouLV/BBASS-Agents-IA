import re

# Id Moduléo d'un élément lu (spec 1.5.2, #203) : sur la ligne de référence
# de sa fiche, pour que le modèle puisse désigner l'élément dans une
# écriture. Jamais à l'écran : la VM retire ce motif exact de la réponse
# avant le poste et la base. Un id reformulé autrement (« n° 1234 ») n'est
# pas filtré (risque accepté par la spec).

_MOTIF = r"\[id Moduléo \d+\]"
# Tournure qui introduit l'id (#254) : « enregistrée sous l'[id Moduléo 4]. »
# s'affichait « enregistrée sous l'. » ; retirée avec lui : « enregistrée. ».
_PREPOSITION = r"(?:sous|avec|par|portant)"
_ARTICLE = r"(?:l['’]|le[ \t]+|la[ \t]+|son[ \t]+|sa[ \t]+)"
_NOM = r"(?:id|identifiant|numéro|n°|référence)(?:[ \t]+Moduléo)?[ \t]*"
_TOURNURE = rf"(?i:[ \t]+(?:{_PREPOSITION}[ \t]+)?(?:{_ARTICLE}?{_NOM}|{_ARTICLE})|[ \t]+{_PREPOSITION})"
# Entre parenthèses, avec elles : « Affaire 2024-123 ([id Moduléo 1234]). »
# → « Affaire 2024-123. ». En début de ligne, avec les espaces qui le
# suivent ; ailleurs, avec sa tournure ou les espaces qui le précèdent :
# « l'affaire 2024-123 [id Moduléo 1234] est » → « l'affaire 2024-123 est ».
_A_RETIRER = re.compile(rf"(?m)[ \t]*\([ \t]*{_MOTIF}[ \t]*\)|^{_MOTIF}[ \t]*|(?:{_TOURNURE})?[ \t]*{_MOTIF}")


def id_moduleo(id_element: int) -> str:
    return f"[id Moduléo {id_element}]"


def retirer_ids_moduleo(texte: str) -> str:
    return _A_RETIRER.sub("", texte)
