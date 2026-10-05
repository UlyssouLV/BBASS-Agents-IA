import re
from collections.abc import Iterable

# Le modèle n'a aucun accès à Internet : une URL qu'il écrit sans que le
# compte l'ait lui-même écrite dans la conversation est inventée (essai du
# 2026-10-05, conversation 76, #110 — onze liens « téléchargeables », tous
# morts). La consigne de style le lui interdit déjà ; ce garde-fou garantit
# le résultat même quand il l'ignore (spec 1.3.1).

# Lien Markdown `[texte](url)`, image `![texte](url)` comprise, avec un
# éventuel titre `"..."` après l'URL.
_MOTIF_LIEN_MARKDOWN = re.compile(
    r'(!?)\[([^\]\n]*)\]\(\s*<?([^\s<>()]+)>?(?:\s+"[^"\n]*")?\s*\)'
)
# URL nue, éventuellement entre chevrons (autolien Markdown). L'espace
# horizontal qui la précède est capturé pour ne pas laisser de double
# espace une fois l'URL retirée.
_MOTIF_URL_NUE = re.compile(
    r"([ \t]*)<?((?:https?://|www\.)[^\s<>()\[\]\"']+)>?", re.IGNORECASE
)
# Ponctuation de fin de phrase collée à une URL nue : appartient à la
# phrase, pas à l'URL.
_PONCTUATION_FINALE = ".,;:!?»"


def _normaliser(url: str) -> str:
    # Schéma, « www. », casse et « / » final ignorés : le modèle redonne
    # souvent l'URL du compte sous une forme légèrement différente.
    url = url.rstrip(_PONCTUATION_FINALE).lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def _urls_du_compte(textes_du_compte: Iterable[str]) -> set[str]:
    return {
        _normaliser(correspondance.group(2))
        for texte in textes_du_compte
        for correspondance in _MOTIF_URL_NUE.finditer(texte)
    }


def retirer_urls_inventees(reponse: str, textes_du_compte: Iterable[str]) -> str:
    autorisees = _urls_du_compte(textes_du_compte)

    def _lien(correspondance: re.Match[str]) -> str:
        if _normaliser(correspondance.group(3)) in autorisees:
            return correspondance.group(0)
        return correspondance.group(2)

    def _url_nue(correspondance: re.Match[str]) -> str:
        espace, url = correspondance.group(1), correspondance.group(2)
        url_sans_ponctuation = url.rstrip(_PONCTUATION_FINALE)
        if _normaliser(url_sans_ponctuation) in autorisees:
            return correspondance.group(0)
        return url[len(url_sans_ponctuation):]

    reponse = _MOTIF_LIEN_MARKDOWN.sub(_lien, reponse)
    return _MOTIF_URL_NUE.sub(_url_nue, reponse)
