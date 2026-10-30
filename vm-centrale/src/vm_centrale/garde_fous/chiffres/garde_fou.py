import re
from collections.abc import Iterable

from vm_centrale.garde_fous.retrait import MARQUEUR_NON_TROUVE, Retrait
from vm_centrale.garde_fous.urls.garde_fou import _MOTIF_LIEN_MARKDOWN, _MOTIF_URL_NUE

# Le modèle récite des chiffres appris à l'entraînement même quand la
# consigne lui interdit d'inventer (essai du 2026-10-05, conversation 78 :
# rapport et statistiques absents du Companion Report). Ce garde-fou retire
# un chiffre qui n'est écrit ni dans les messages du compte, ni dans un
# extrait que la VM détient (pièce jointe, plus tard page ramenée par
# l'outil de recherche). Un entier d'un seul chiffre n'est pas contrôlé,
# sauf s'il est suivi d'une unité de durée ou monétaire (« 8 ans »,
# « 5 € ») : « 3 pistes » reste
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
# Unité de durée ou monétaire (« 3 jours », « 5 € », spec 1.6.3) ; « € »
# peut être collé au nombre.
_MOTIF_UNITE = re.compile(
    r"[ \t\u00a0\u202f]+(ans|an|années|année|semaines|semaine|jours|jour|mois|heures|heure|euros|euro|eur)\b"
    r"|[ \t\u00a0\u202f]*€",
    re.IGNORECASE,
)


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


def retirer_chiffres_hors_source(
    reponse: str, textes_source: Iterable[str], expressions_permises: Iterable[re.Pattern[str]] = ()
) -> Retrait:
    # `expressions_permises` : écrites telles quelles dans la réponse (la
    # date du jour en lettres), leurs chiffres ne sont pas contrôlés ; hors
    # d'elles, les mêmes chiffres le restent.
    autorisees = _cles_autorisees(textes_source)
    plages_des_urls = _plages_des_urls(reponse) + [
        correspondance.span() for motif in expressions_permises for correspondance in motif.finditer(reponse)
    ]
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
        # Le nombre seul, sans son « % ».
        fin_du_nombre = correspondance.end(2) if correspondance.group(2) else correspondance.end(1)
        a_retirer.append((correspondance.start(), fin_du_nombre))
    if not a_retirer:
        return Retrait(reponse, False)
    # Un chiffre retiré dans une suite d'au moins trois groupes (SIRET,
    # téléphone) emporte toute la suite : jamais un fragment (« 22 ») qui
    # passerait pour une donnée. Deux nombres côte à côte (« En 2023 15
    # salariés ») sont deux données : chacun est jugé seul.
    for debut, fin in sequences:
        if len(_MOTIF_GROUPE.findall(reponse, debut, fin)) < 3:
            continue
        if any(debut <= position < fin for position, _ in a_retirer):
            a_retirer.append((debut, fin))

    # Seul le chiffre devient le marqueur : la phrase, son unité (« € »,
    # « % ») et les espaces autour restent, pour qu'on lise ce qui manque
    # (spec 1.6.3 ; avant, il emportait sa phrase ou sa parenthèse, #160).
    remplacee, curseur = [], 0
    for debut, fin in sorted(a_retirer):
        if fin <= curseur:
            continue
        if debut >= curseur:
            remplacee += [reponse[curseur:debut], MARQUEUR_NON_TROUVE]
        curseur = fin
    remplacee.append(reponse[curseur:])
    return Retrait("".join(remplacee), True)
