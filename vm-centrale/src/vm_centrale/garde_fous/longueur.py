import re

# Le résumé glissant et le profil de travail sont renvoyés au modèle à chaque
# tour : sans borne, ils grossissent et gardent ce que le compte a abandonné
# (#110, conversation 76). Le prompt résumé+profil énonce déjà les plafonds ;
# ce garde-fou les garantit même quand le modèle les ignore (spec 1.3.1).

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
