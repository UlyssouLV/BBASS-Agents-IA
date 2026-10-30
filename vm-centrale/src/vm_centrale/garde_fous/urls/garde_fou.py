import re
from collections.abc import Iterable

from vm_centrale.garde_fous.retrait import MARQUEUR_NON_TROUVE, Retrait

# Une URL que le modèle écrit sans que le compte l'ait lui-même écrite dans
# la conversation est inventée (essai du 2026-10-05, conversation 76, #110 —
# onze liens « téléchargeables », tous morts). La consigne de style le lui
# interdit déjà ; ce garde-fou garantit le résultat même quand il l'ignore
# (spec 1.3.1). Depuis la 1.4.0, une URL ramenée par l'outil rechercher_web
# dans la conversation est aussi légitime : le titre et l'extrait du moteur
# sont une vraie trace de la page.

# Lien Markdown `[texte](url)`, image `![texte](url)` comprise, avec un
# éventuel titre `"..."` après l'URL. Une paire de parenthèses fermée dans
# l'URL en fait partie (`…/wiki/Loi_(France)`, résultat de moteur courant) ;
# une seule, pas une répétition, pour éviter tout retour arrière coûteux.
_MOTIF_LIEN_MARKDOWN = re.compile(
    r'(!?)\[([^\]\n]*)\]\(\s*<?([^\s<>()]+(?:\([^\s<>()]*\)[^\s<>()]*)?)>?(?:\s+"[^"\n]*")?\s*\)'
)
# URL nue, éventuellement entre chevrons (autolien Markdown). L'espace
# horizontal qui la précède est capturé pour ne pas laisser de double
# espace une fois l'URL retirée ; le lookbehind ne le fait capturer qu'au
# début d'une suite d'espaces (sinon une longue suite sans URL est relue
# depuis chaque espace : 39 s pour 50 000). Même règle de parenthèses : une
# paire fermée en fait partie, une parenthèse seule (URL citée entre
# parenthèses) appartient à la phrase.
_MOTIF_URL_NUE = re.compile(
    r"(?<![ \t])([ \t]*)<?((?:https?://|www\.)[^\s<>()\[\]\"']+(?:\([^\s<>()\[\]\"']*\)[^\s<>()\[\]\"']*)?)>?",
    re.IGNORECASE,
)
# Ponctuation de fin de phrase et mise en forme Markdown (`**`, `_`, `` ` ``)
# collées à une URL nue : appartiennent à la phrase, pas à l'URL (essai
# 1.4.1, conversation 95 : « **https://bbass.fr/** » était retirée).
_PONCTUATION_FINALE = ".,;:!?»*_`"
# Place d'un lien retiré, avant de savoir s'il devient le marqueur ou part
# avec sa parenthèse.
_RETIRE = "\x00"
_MOTIF_PARENTHESE_RETIREE = re.compile(r"[ \t]*\([ \t]*\x00(?:[ \t]*[,;][ \t]*\x00)*[ \t]*\)")
_MOTIF_SUITE_RETIREE = re.compile(r"\x00(?:[ \t]*[,;][ \t]*\x00)*")


def normaliser_url(url: str) -> str:
    # Schéma, « www. », casse et « / » final ignorés : le modèle redonne
    # souvent l'URL du compte sous une forme légèrement différente. Partagée
    # avec lire_pages_web et la Mémoire de la conversation (#140).
    url = url.rstrip(_PONCTUATION_FINALE).lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def urls_ecrites(textes: Iterable[str]) -> list[tuple[int, str]]:
    # (rang du texte, URL) à la première occurrence de chaque URL, dans
    # l'ordre, ponctuation finale retirée. Même règle que le garde-fou :
    # partagée avec la Mémoire de la conversation (spec 1.4.1, #134), pour
    # qu'une URL qui y figure soit une URL que le garde-fou laisse passer.
    vues: set[str] = set()
    urls: list[tuple[int, str]] = []
    for rang, texte in enumerate(textes):
        for correspondance in _MOTIF_URL_NUE.finditer(texte):
            url = correspondance.group(2).rstrip(_PONCTUATION_FINALE)
            if normaliser_url(url) not in vues:
                vues.add(normaliser_url(url))
                urls.append((rang, url))
    return urls


def _urls_du_compte(textes_du_compte: Iterable[str]) -> set[str]:
    return {normaliser_url(url) for _, url in urls_ecrites(textes_du_compte)}


def retirer_urls_inventees(
    reponse: str, textes_du_compte: Iterable[str], urls_trouvees: Iterable[str] = ()
) -> Retrait:
    # `urls_trouvees` : URL des résultats de recherche, comparées telles
    # quelles (pas extraites d'un texte, une URL de moteur peut contenir des
    # parenthèses).
    autorisees = _urls_du_compte(textes_du_compte) | {normaliser_url(url) for url in urls_trouvees}

    # Un lien inventé ne laisse pas son texte, qui passerait pour une source
    # (#131 : « comme le confirme : Leboncoin – Centre d'aide ») : il devient
    # le marqueur, comme une URL nue inventée.
    def _lien(correspondance: re.Match[str]) -> str:
        if normaliser_url(correspondance.group(3)) in autorisees:
            return correspondance.group(0)
        return _RETIRE

    def _url_nue(correspondance: re.Match[str]) -> str:
        espace, url = correspondance.group(1), correspondance.group(2)
        url_sans_ponctuation = url.rstrip(_PONCTUATION_FINALE)
        if normaliser_url(url_sans_ponctuation) in autorisees:
            return correspondance.group(0)
        return espace + _RETIRE + url[len(url_sans_ponctuation):]

    reponse = _MOTIF_LIEN_MARKDOWN.sub(_lien, reponse)
    reponse = _MOTIF_URL_NUE.sub(_url_nue, reponse)
    if _RETIRE not in reponse:
        return Retrait(reponse, False)
    # Une parenthèse qui ne contenait que des liens inventés part entière,
    # espaces qui la précèdent compris : jamais `()` (#131, « **Météo
    # France** () ») ; plusieurs liens inventés à la suite font un marqueur.
    reponse = _MOTIF_PARENTHESE_RETIREE.sub("", reponse)
    reponse = _MOTIF_SUITE_RETIREE.sub(MARQUEUR_NON_TROUVE, reponse)
    return Retrait(reponse, True)
