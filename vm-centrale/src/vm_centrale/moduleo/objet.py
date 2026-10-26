import re

# Objet d'un devis, d'une facture ou d'une affaire (#198) : `Objet` est du
# RTF (`{\rtf1\ansi\ansicpg1252…\fs17 R\'e9tablissement…\par }`), `ObjetBrut`
# du texte simple ; les deux gardent les champs de modèle Moduléo `$…$` non
# remplis (`$Affaire.Commune$ : Section $Affaire.GE.Cbl.SectionParc$`). Le
# modèle et le garde-fou chiffres ne voient ni code RTF ni champ `$…$`.

_CHAMP_DE_MODELE = re.compile(r"\$[A-Za-z][\w.]*\$")
_MARQUE = "\x00"
# La ponctuation qui ne sert qu'à un champ retiré : « lot B, $Affaire.Commune$ ».
_AVANT_LE_CHAMP = re.compile(rf"[\s,;:]*{_MARQUE}")
_BORDS = " \t\r\n\f\v ,;:–-"

# Groupes RTF sans texte affiché : polices, couleurs, styles, propriétés.
_DESTINATIONS_IGNOREES = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer", "generator"}
_MOT_DE_CONTROLE = re.compile(r"\\([a-z]+)(-?\d+)? ?")


def objet_lisible(element: dict) -> str:
    # `ObjetBrut`, ou à défaut l'`Objet` débarrassé du RTF ; une ligne qui
    # n'a que des champs de modèle (et leur libellé) disparaît. Le tout sur
    # une ligne (#180).
    brut = element.get("ObjetBrut")
    texte = brut if isinstance(brut, str) and brut.strip() else _sans_rtf(element.get("Objet") or "")
    lignes = (_sans_champs_de_modele(ligne) for ligne in texte.splitlines())
    return " ".join(" ".join(ligne for ligne in lignes if ligne).split())


def _sans_champs_de_modele(ligne: str) -> str:
    if not _CHAMP_DE_MODELE.search(ligne):
        return ligne.strip()
    reste = _CHAMP_DE_MODELE.sub(_MARQUE, ligne)
    # « $Affaire.Commune$ : Section $…$ » : un libellé seul ne dit rien.
    if len(re.findall(r"\w+", reste)) <= 1:
        return ""
    return _AVANT_LE_CHAMP.sub("", reste).replace(_MARQUE, "").strip(_BORDS)


def _sans_rtf(texte: str) -> str:
    if not texte.lstrip().startswith(r"{\rtf"):
        return texte
    morceaux: list[str] = []
    ignores = [False]  # par groupe `{…}` ouvert
    i = 0
    while i < len(texte):
        c = texte[i]
        if c == "{":
            ignores.append(ignores[-1])
            i += 1
        elif c == "}":
            if len(ignores) > 1:
                ignores.pop()
            i += 1
        elif c in "\r\n":
            i += 1
        elif c != "\\":
            if not ignores[-1]:
                morceaux.append(c)
            i += 1
        else:
            i, sortie, ignorer = _controle(texte, i)
            if ignorer:
                ignores[-1] = True
            elif not ignores[-1]:
                morceaux.append(sortie)
    return "".join(morceaux)


def _controle(texte: str, i: int) -> tuple[int, str, bool]:
    # Le contrôle RTF qui commence à `texte[i]` (« \ ») : (indice suivant,
    # texte produit, groupe à ignorer).
    suivant = texte[i + 1 : i + 2]
    if suivant == "'":
        return i + 4, bytes.fromhex(texte[i + 2 : i + 4]).decode("cp1252", errors="replace"), False
    if suivant in ("\\", "{", "}"):
        return i + 2, suivant, False
    if suivant == "*":
        return i + 2, "", True
    if suivant in ("\r", "\n"):
        return i + 2, "\n", False
    if suivant == "~":
        return i + 2, " ", False
    mot = _MOT_DE_CONTROLE.match(texte, i)
    if not mot:
        return i + 2, "", False
    nom, valeur = mot.group(1), mot.group(2)
    fin = mot.end()
    if nom in _DESTINATIONS_IGNOREES:
        return fin, "", True
    if nom in ("par", "line"):
        return fin, "\n", False
    if nom == "tab":
        return fin, " ", False
    if nom == "u" and valeur:
        # « \u233? » : le caractère, puis son remplaçant (un caractère ou
        # « \'hh ») sauté.
        caractere = chr(int(valeur) % 0x10000)
        return fin + (4 if texte[fin : fin + 2] == "\\'" else 1), caractere, False
    return fin, "", False
