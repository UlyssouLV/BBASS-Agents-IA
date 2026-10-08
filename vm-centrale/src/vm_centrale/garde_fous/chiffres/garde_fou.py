import re
from collections.abc import Iterable

from vm_centrale.garde_fous.urls.garde_fou import _MOTIF_LIEN_MARKDOWN, _MOTIF_URL_NUE

# Le modèle récite des chiffres appris à l'entraînement même quand la
# consigne lui interdit d'inventer (essai du 2026-10-05, conversation 78 :
# rapport et statistiques absents du Companion Report). Ce garde-fou retire
# un chiffre qui n'est écrit ni dans les messages du compte, ni dans un
# extrait que la VM détient (pièce jointe, plus tard page ramenée par
# l'outil de recherche). Un entier d'un seul chiffre n'est pas contrôlé,
# sauf s'il est suivi d'une unité de durée (« 8 ans ») : « 3 pistes » reste
# une tournure, pas une donnée. Un nombre écrit dans une URL n'est jamais
# touché : les URL sont du ressort du seul garde-fou URL (#128, conversation
# 87 — « 2025-03/202503-guide… » devenait « 2025-/-guide… »).

_MOTIF_NOMBRE = re.compile(
    r"(?<!\w)(\d{1,3}(?:[ \u00a0]\d{3})+|\d+)([.,]\d+)?([ \t]?%)?"
)
# Chiffres groupés par des espaces simples (« 831 193 453 00022 ») : un
# numéro (SIRET, TVA, téléphone) que le modèle regroupe autrement que la
# source (essai 1.4.1, conversation 93 : « 83119345300022 » devenait « 22 »).
# Au moins trois groupes séparés par `.` ou `-` aussi : Moduléo stocke
# « 05.61.12.92.00 », le modèle écrit « 05 61 12 92 00 » (test humain
# 1.5.0, conversation 113, #180) ; deux groupes à point restent un décimal.
_MOTIF_SEQUENCE = re.compile(r"(?<![\w.,])\d+(?:(?:[  ]\d+)+|(?:[.-]\d+){2,})")
_MOTIF_GROUPE = re.compile(r"\d+")
_MOTIF_UNITE = re.compile(
    r"[ \t]+(ans|an|années|année|semaines|semaine|jours|jour|mois|heures|heure)\b",
    re.IGNORECASE,
)
# Fin de phrase : `.`, `!` ou `?` suivis d'un blanc (jamais le point d'un
# décimal « 1.5 » ni d'un domaine « exemple.fr »).
_MOTIF_FIN_DE_PHRASE = re.compile(r"[.!?…]+(?=\s|$)")
_MOTIF_PUCE = re.compile(r"[ \t]*(?:[-*+]|\d+[.)])[ \t]+")
_MOTIF_PUCE_VIDE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]*(?:\n|$)", re.MULTILINE)


def _cle(correspondance: re.Match[str]) -> str:
    entier = correspondance.group(1).replace(" ", "").replace("\u00a0", "")
    decimal = correspondance.group(2)
    if decimal is None:
        return entier
    fraction = decimal[1:].rstrip("0")
    if not fraction:
        return entier
    return f"{entier}.{fraction}"


def _est_une_donnee(correspondance: re.Match[str], texte: str) -> bool:
    if correspondance.group(2) is not None or "%" in (correspondance.group(3) or ""):
        return True
    if len(_cle(correspondance)) >= 2:
        return True
    return _MOTIF_UNITE.match(texte, correspondance.end()) is not None


def _chiffres_seuls(sequence: str) -> str:
    return "".join(_MOTIF_GROUPE.findall(sequence))


def _sequences_a_points(texte: str) -> list[re.Match[str]]:
    # « 05.61.12.92.00 », « 2024-03-11 » : au moins trois groupes à `.` ou `-`.
    return [
        correspondance
        for correspondance in _MOTIF_SEQUENCE.finditer(texte)
        if re.search(r"[.-]", correspondance.group(0))
    ]


def _cles_autorisees(textes_source: Iterable[str]) -> set[str]:
    # Dans « 05.61.12.92.00 », chaque groupe est un entier, jamais les
    # décimaux « 05.61 » ou « 12.92 » (#180) ; « 2024-03-11 » autorise
    # toujours « 2024 » et « 11 ».
    cles: set[str] = set()
    for texte in textes_source:
        a_points = _sequences_a_points(texte)
        plages = [sequence.span() for sequence in a_points]
        cles |= {
            _cle(correspondance)
            for correspondance in _MOTIF_NOMBRE.finditer(texte)
            if not (correspondance.group(2) and _dans(correspondance.start(), plages))
        }
        cles |= {groupe for sequence in a_points for groupe in _MOTIF_GROUPE.findall(sequence.group(0))}
        cles |= {_chiffres_seuls(correspondance.group(0)) for correspondance in _MOTIF_SEQUENCE.finditer(texte)}
    return cles


def _plages_des_urls(texte: str) -> list[tuple[int, int]]:
    # Partie `url` d'un lien Markdown et URL nue ; le texte d'un lien
    # `[texte](url)` reste contrôlé.
    return [
        correspondance.span(3) for correspondance in _MOTIF_LIEN_MARKDOWN.finditer(texte)
    ] + [correspondance.span(2) for correspondance in _MOTIF_URL_NUE.finditer(texte)]


def _dans(position: int, plages: list[tuple[int, int]]) -> bool:
    return any(debut <= position < fin for debut, fin in plages)


def chiffres_controles(reponse: str) -> set[str]:
    # Les chiffres que ce garde-fou contrôle dans la réponse (hors URL),
    # comparables à chiffres_des_sources : partagé avec le garde-fou
    # sources (#160), pour la même définition d'un chiffre.
    plages_des_urls = _plages_des_urls(reponse)
    nombres = {
        _cle(correspondance)
        for correspondance in _MOTIF_NOMBRE.finditer(reponse)
        if not _dans(correspondance.start(), plages_des_urls) and _est_une_donnee(correspondance, reponse)
    }
    return nombres | {
        _chiffres_seuls(correspondance.group(0))
        for correspondance in _MOTIF_SEQUENCE.finditer(reponse)
        if not _dans(correspondance.start(), plages_des_urls)
    }


def chiffres_des_sources(textes_source: Iterable[str]) -> set[str]:
    return _cles_autorisees(textes_source)


def retirer_chiffres_hors_source(reponse: str, textes_source: Iterable[str]) -> str:
    autorisees = _cles_autorisees(textes_source)
    plages_des_urls = _plages_des_urls(reponse)
    # Une suite qui commence dans une URL (« …/2011101 12 % ») n'est pas un
    # numéro : la retirer entière couperait l'URL.
    sequences = [
        correspondance.span()
        for correspondance in _MOTIF_SEQUENCE.finditer(reponse)
        if not _dans(correspondance.start(), plages_des_urls)
    ]
    # Une suite de chiffres groupés dont les chiffres, mis bout à bout,
    # sont dans une source reste entière, quel que soit le groupement.
    sequences_autorisees = [
        (debut, fin) for debut, fin in sequences if _chiffres_seuls(reponse[debut:fin]) in autorisees
    ]

    a_retirer: list[tuple[int, int]] = []
    for correspondance in _MOTIF_NOMBRE.finditer(reponse):
        if _dans(correspondance.start(), plages_des_urls):
            continue
        if any(debut <= correspondance.start() and correspondance.end() <= fin for debut, fin in sequences_autorisees):
            continue
        if not _est_une_donnee(correspondance, reponse) or _cle(correspondance) in autorisees:
            continue
        a_retirer.append(correspondance.span())
    if not a_retirer:
        return reponse
    # Un chiffre retiré dans une suite d'au moins trois groupes (SIRET,
    # téléphone) emporte toute la suite : jamais un fragment (« 22 ») qui
    # passerait pour une donnée. Deux nombres côte à côte (« En 2023 15
    # salariés ») sont deux données : chacun est jugé seul.
    for debut, fin in sequences:
        if len(_MOTIF_GROUPE.findall(reponse, debut, fin)) < 3:
            continue
        if any(debut <= position < fin for position, _ in a_retirer):
            a_retirer.append((debut, fin))

    # Le plus petit bloc qui contient le chiffre part avec lui, jamais un
    # fragment vide (#160, conversation 103 : « (soit 1,5 à 3 mois) »
    # devenait « (soit à 3 mois) »).
    blocs = [_bloc(reponse, debut, fin) for debut, fin in a_retirer]
    nettoyee, curseur = [], 0
    for debut, fin in sorted(blocs):
        if fin <= curseur:
            continue
        nettoyee.append(reponse[curseur:max(debut, curseur)])
        curseur = fin
    nettoyee.append(reponse[curseur:])
    texte = re.sub(r"[ 	]{2,}", " ", "".join(nettoyee))
    # Une puce vidée part avec sa ligne ; une phrase seule sur sa ligne ne
    # laisse pas de paragraphe vide.
    texte = _MOTIF_PUCE_VIDE.sub("", texte)
    return re.sub(r"\n{3,}", "\n\n", texte).strip()


def _bloc(texte: str, debut: int, fin: int) -> tuple[int, int]:
    # La parenthèse qui entoure le chiffre s'il y en a une sur sa ligne,
    # espaces qui la précèdent compris ; sinon sa phrase.
    debut_ligne = texte.rfind("\n", 0, debut) + 1
    fin_ligne = texte.find("\n", fin)
    if fin_ligne == -1:
        fin_ligne = len(texte)
    ouvrante = _parenthese(texte, debut - 1, debut_ligne - 1, -1, "(", ")")
    fermante = _parenthese(texte, fin, fin_ligne, 1, ")", "(")
    if ouvrante is not None and fermante is not None:
        while ouvrante > debut_ligne and texte[ouvrante - 1] in " \t":
            ouvrante -= 1
        return ouvrante, fermante + 1
    return _phrase(texte, debut, fin, debut_ligne, fin_ligne)


def _parenthese(texte: str, depart: int, borne: int, pas: int, cherchee: str, inverse: str) -> int | None:
    # Position de la parenthèse `cherchee` qui ferme le niveau du chiffre,
    # en sautant les paires complètes (lien Markdown, « (art. 3) »).
    profondeur = 0
    for position in range(depart, borne, pas):
        caractere = texte[position]
        if caractere == inverse:
            profondeur += 1
        elif caractere == cherchee:
            if profondeur == 0:
                return position
            profondeur -= 1
    return None


def _phrase(texte: str, debut: int, fin: int, debut_ligne: int, fin_ligne: int) -> tuple[int, int]:
    # Jusqu'au `.`, `!`, `?` ou à la fin de la ligne. Dans une ligne de
    # tableau, la cellule borne la phrase ; dans une puce, la puce reste.
    dans_un_tableau = texte[debut_ligne:fin_ligne].lstrip().startswith("|")
    if dans_un_tableau:
        debut_zone = texte.rfind("|", debut_ligne, debut) + 1
        fin_zone = texte.find("|", fin, fin_ligne)
        if fin_zone == -1:
            fin_zone = fin_ligne
    else:
        puce = _MOTIF_PUCE.match(texte, debut_ligne, fin_ligne)
        debut_zone = puce.end() if puce is not None else debut_ligne
        fin_zone = fin_ligne
    debut_phrase = debut_zone
    for fin_de_phrase in _MOTIF_FIN_DE_PHRASE.finditer(texte, debut_zone, debut):
        debut_phrase = fin_de_phrase.end()
    while debut_phrase < debut and texte[debut_phrase] in " \t":
        debut_phrase += 1
    suivante = _MOTIF_FIN_DE_PHRASE.search(texte, fin, fin_zone)
    if suivante is not None and texte[suivante.end():fin_zone].strip():
        fin_phrase = suivante.end()
        # Les espaces avant la phrase suivante partent avec la phrase.
        while fin_phrase < fin_zone and texte[fin_phrase] in " \t":
            fin_phrase += 1
        return debut_phrase, fin_phrase
    fin_phrase = fin_zone
    if dans_un_tableau:
        # La cellule garde ses espaces : « | Recours | | ».
        while fin_phrase > debut_phrase and texte[fin_phrase - 1] in " \t":
            fin_phrase -= 1
        return debut_phrase, fin_phrase
    # Dernière phrase de la ligne : les espaces qui la précèdent partent.
    while debut_phrase > debut_zone and texte[debut_phrase - 1] in " \t":
        debut_phrase -= 1
    return debut_phrase, fin_phrase
