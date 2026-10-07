import re
from collections.abc import Iterable
from dataclasses import dataclass

from vm_centrale.garde_fous.chiffres import chiffres_controles, chiffres_des_sources
from vm_centrale.garde_fous.urls import normaliser_url, urls_ecrites

# Au test humain 1.4.3 (conversation 103, #160), la réponse donnait « 6 à 12
# semaines » sans dire de quelle page venait le chiffre. Ce garde-fou cite
# les pages d'où viennent les chiffres gardés, quelle que soit la réponse.
# Au test humain 2 (conversations 105 et 106, #162), « 2026 » faisait citer
# presque toutes les pages, et le modèle écrivait son propre bloc de sources
# avant le nôtre : une page par chiffre, années ignorées, un seul bloc.

# « Sources : », « **Source :** », « Sources** : » en tête de ligne.
_MOTIF_ENTETE = re.compile(r"^([ \t]*[*_]{0,2})(Sources?)([*_]{0,2}[ \t]*:[*_]{0,2}[ \t]*)(.*)$")
_MOTIF_PUCE = re.compile(r"^([ \t]*[-*+][ \t]+)\S")


@dataclass(frozen=True)
class PageSource:
    # Une page de la conversation et son texte nettoyé, jamais l'extrait du
    # moteur : une page qu'on n'a pas lue n'est pas citée (#162).
    url: str
    titre: str
    texte: str


def ajouter_sources(reponse: str, textes_du_compte: Iterable[str], pages: Iterable[PageSource]) -> str:
    # `textes_du_compte` : messages du compte et extraits des pièces jointes.
    # Un chiffre qui y figure n'a pas besoin de page pour source. `pages` :
    # dans l'ordre de la conversation, la plus récente en dernier.
    pages = list(pages)
    chiffres = {
        chiffre
        for chiffre in chiffres_controles(reponse) - chiffres_des_sources(textes_du_compte)
        if not _est_une_annee(chiffre)
    }
    deja_en_lien = {normaliser_url(url) for _, url in urls_ecrites([reponse])}
    chiffres -= chiffres_des_sources(page.texte for page in pages if normaliser_url(page.url) in deja_en_lien)
    # Une page lue plusieurs fois garde le premier titre connu.
    titres: dict[str, str] = {}
    for page in pages:
        cle = normaliser_url(page.url)
        titres[cle] = titres.get(cle) or page.titre
    citees: dict[str, PageSource] = {}
    for page in reversed(pages):
        trouves = chiffres & chiffres_des_sources([page.texte])
        if not trouves:
            continue
        chiffres -= trouves
        cle = normaliser_url(page.url)
        citees.setdefault(cle, PageSource(page.url, titres[cle], page.texte))
    if not citees:
        return reponse
    liens = [f"[{_texte_du_lien(page)}]({page.url})" for page in reversed(citees.values())]
    return _completer_le_bloc(reponse.rstrip(), liens) or f"{reponse.rstrip()}\n\nSources : {', '.join(liens)}"


def _est_une_annee(chiffre: str) -> bool:
    return chiffre.isdigit() and 1900 <= int(chiffre) <= 2100


def _completer_le_bloc(reponse: str, liens: list[str]) -> str | None:
    # Le bloc de sources que le modèle a écrit à la fin de sa réponse reçoit
    # les pages manquantes, au même format (ligne ou liste à puces).
    lignes = reponse.split("\n")
    puces, marque = 0, None
    while puces < len(lignes) and (puce := _MOTIF_PUCE.match(lignes[-1 - puces])):
        marque = marque or puce.group(1)
        puces += 1
    if puces == len(lignes):
        return None
    entete = _MOTIF_ENTETE.match(lignes[-1 - puces])
    if entete is None:
        return None
    lignes[-1 - puces] = f"{entete.group(1)}Sources{entete.group(3)}{entete.group(4)}"
    if marque is not None:
        lignes += [f"{marque}{lien}" for lien in liens]
    else:
        separateur = ", " if entete.group(4) else " "
        lignes[-1] = lignes[-1].rstrip() + separateur + ", ".join(liens)
    return "\n".join(lignes)


def _texte_du_lien(page: PageSource) -> str:
    # Des crochets dans le titre fermeraient le lien Markdown trop tôt.
    titre = page.titre.strip().replace("[", "(").replace("]", ")")
    return titre or page.url
