import re

# Id Moduléo d'un élément lu (spec 1.5.2, #203) : sur la ligne de référence
# de sa fiche, pour que le modèle puisse désigner l'élément dans une
# écriture. Jamais à l'écran : la VM retire ce motif exact de la réponse
# avant le poste et la base. Un id reformulé autrement (« n° 1234 ») n'est
# pas filtré (risque accepté par la spec).

_MOTIF = r"\[id Moduléo \d+\]"
# En début de ligne, avec les espaces qui le suivent ; ailleurs, avec ceux
# qui le précèdent : « l'affaire 2024-123 [id Moduléo 1234] est » →
# « l'affaire 2024-123 est ».
_A_RETIRER = re.compile(rf"(?m)^{_MOTIF}[ \t]*|[ \t]*{_MOTIF}")


def id_moduleo(id_element: int) -> str:
    return f"[id Moduléo {id_element}]"


def retirer_ids_moduleo(texte: str) -> str:
    return _A_RETIRER.sub("", texte)
