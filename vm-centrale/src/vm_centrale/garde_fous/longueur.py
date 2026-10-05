import re

# Le résumé glissant est renvoyé au modèle à chaque tour : sans borne, il
# grossit et garde ce que le compte a abandonné (#110, conversation 76). Le
# prompt résumé+profil énonce déjà le plafond ; ce garde-fou le garantit même
# quand le modèle l'ignore (spec 1.3.1).

# Fin de phrase : « . », « ! », « ? » ou « … », éventuellement suivie de
# guillemets ou parenthèses fermants, puis d'un blanc ou de la fin du texte.
_MOTIF_FIN_DE_PHRASE = re.compile(r"[.!?…][\"'»)\]]*(?=\s|$)")


def plafonner(texte: str, maximum: int) -> str:
    if len(texte) <= maximum:
        return texte
    debut = texte[: maximum + 1]
    fins = [fin.end() for fin in _MOTIF_FIN_DE_PHRASE.finditer(debut) if fin.end() <= maximum]
    if not fins:
        # Aucune fin de phrase sous le plafond : seule une coupe brute le tient.
        return texte[:maximum].rstrip()
    return texte[: fins[-1]]
