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


def _cles_autorisees(textes_source: Iterable[str]) -> set[str]:
    return {
        _cle(correspondance)
        for texte in textes_source
        for correspondance in _MOTIF_NOMBRE.finditer(texte)
    }


def _plages_des_urls(texte: str) -> list[tuple[int, int]]:
    # Partie `url` d'un lien Markdown et URL nue ; le texte d'un lien
    # `[texte](url)` reste contrôlé.
    return [
        correspondance.span(3) for correspondance in _MOTIF_LIEN_MARKDOWN.finditer(texte)
    ] + [correspondance.span(2) for correspondance in _MOTIF_URL_NUE.finditer(texte)]


def retirer_chiffres_hors_source(reponse: str, textes_source: Iterable[str]) -> str:
    autorisees = _cles_autorisees(textes_source)
    plages_des_urls = _plages_des_urls(reponse)

    def _remplacer(correspondance: re.Match[str]) -> str:
        if any(debut <= correspondance.start() < fin for debut, fin in plages_des_urls):
            return correspondance.group(0)
        if not _est_une_donnee(correspondance, reponse):
            return correspondance.group(0)
        if _cle(correspondance) in autorisees:
            return correspondance.group(0)
        return ""

    nettoyee = _MOTIF_NOMBRE.sub(_remplacer, reponse)
    if nettoyee == reponse:
        return reponse
    return re.sub(r"[ \t]{2,}", " ", nettoyee)
