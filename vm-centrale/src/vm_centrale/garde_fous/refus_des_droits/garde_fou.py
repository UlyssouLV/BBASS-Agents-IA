import re

# Le garde des droits Moduléo renvoie une phrase fixe qui nomme le droit
# manquant. Au second passage de #206 (#262), le modèle la reformulait
# (« Je n'ai pas accès à la recherche des contacts ») : le droit n'était
# plus nommé et « Rien n'a été écrit » disparaissait.

_PHRASES = re.compile(r"[^.!?]+[.!?]*\s*")
# Une phrase du modèle qui redit le refus à sa façon : le vocabulaire des
# droits, et un refus. « L'accès à la parcelle passe par le droit de
# passage. » parle du métier.
_REFORMULATION = re.compile(r"\b(?:droits?|acc[eè]s|autoris\w*|administrateurs?|permissions?)\b", re.IGNORECASE)
_REFUS = re.compile(
    r"\b(?:n['’]|ne\b|pas\b|sans\b|aucun|manqu\w*|refus\w*|interdi\w*|n[ée]cessit\w*|requi\w*|faut\b"
    r"|demand\w*|contact\w*|obten\w*)",
    re.IGNORECASE,
)


def montrer_refus_des_droits(reponse: str, refus: list[str]) -> str:
    # `refus` : les phrases du garde renvoyées par les outils du tour, dans
    # l'ordre. Chacune absente de la réponse passe en tête ; les phrases du
    # modèle qui les reformulent partent.
    manquantes = [phrase for phrase in dict.fromkeys(refus) if phrase not in reponse]
    if not manquantes:
        return reponse
    lignes = (
        "".join(phrase for phrase in _PHRASES.findall(ligne) if not _redit_le_refus(phrase)).rstrip()
        for ligne in reponse.split("\n")
    )
    reste = re.sub(r"\n{3,}", "\n\n", "\n".join(lignes)).strip()
    return "\n\n".join([*manquantes, reste] if reste else manquantes)


def _redit_le_refus(phrase: str) -> bool:
    return bool(_REFORMULATION.search(phrase) and _REFUS.search(phrase))
