import re
from collections.abc import Iterable

from vm_centrale.garde_fous.urls import _MOTIF_LIEN_MARKDOWN, _MOTIF_URL_NUE

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
_MOTIF_SEQUENCE = re.compile(r"(?<![\w.,])\d+(?:[  ]\d+)+")
_MOTIF_UNITE = re.compile(
    r"[ \t]+(ans|an|années|année|semaines|semaine|jours|jour|mois|heures|heure)\b",
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
    return sequence.replace(" ", "").replace(" ", "")


def _cles_autorisees(textes_source: Iterable[str]) -> set[str]:
    textes_source = list(textes_source)
    return {
        _cle(correspondance)
        for texte in textes_source
        for correspondance in _MOTIF_NOMBRE.finditer(texte)
    } | {
        _chiffres_seuls(correspondance.group(0))
        for texte in textes_source
        for correspondance in _MOTIF_SEQUENCE.finditer(texte)
    }


def _plages_des_urls(texte: str) -> list[tuple[int, int]]:
    # Partie `url` d'un lien Markdown et URL nue ; le texte d'un lien
    # `[texte](url)` reste contrôlé.
    return [
        correspondance.span(3) for correspondance in _MOTIF_LIEN_MARKDOWN.finditer(texte)
    ] + [correspondance.span(2) for correspondance in _MOTIF_URL_NUE.finditer(texte)]


def _dans(position: int, plages: list[tuple[int, int]]) -> bool:
    return any(debut <= position < fin for debut, fin in plages)


def retirer_chiffres_hors_source(reponse: str, textes_source: Iterable[str]) -> str:
    autorisees = _cles_autorisees(textes_source)
    plages_des_urls = _plages_des_urls(reponse)
    sequences = [correspondance.span() for correspondance in _MOTIF_SEQUENCE.finditer(reponse)]
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
    # Un chiffre retiré dans une suite groupée emporte toute la suite :
    # jamais un fragment (« 22 ») qui passerait pour une donnée.
    for debut, fin in sequences:
        if any(debut <= position < fin for position, _ in a_retirer):
            a_retirer.append((debut, fin))

    nettoyee, curseur = [], 0
    for debut, fin in sorted(a_retirer):
        if fin <= curseur:
            continue
        nettoyee.append(reponse[curseur:max(debut, curseur)])
        curseur = fin
    nettoyee.append(reponse[curseur:])
    return re.sub(r"[ 	]{2,}", " ", "".join(nettoyee))
