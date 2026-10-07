from collections.abc import Iterable
from dataclasses import dataclass

from vm_centrale.garde_fous.chiffres import chiffres_controles, chiffres_des_sources
from vm_centrale.garde_fous.urls import normaliser_url, urls_ecrites

# Au test humain 1.4.3 (conversation 103, #160), la réponse donnait « 6 à 12
# semaines » sans dire de quelle page venait le chiffre. Ce garde-fou cite
# les pages d'où viennent les chiffres gardés, quelle que soit la réponse.


@dataclass(frozen=True)
class PageSource:
    # Une page de la conversation : `textes`, son texte nettoyé et l'extrait
    # du moteur, les mêmes sources que le garde-fou chiffres.
    url: str
    titre: str
    textes: tuple[str, ...]


def ajouter_sources(reponse: str, textes_du_compte: Iterable[str], pages: Iterable[PageSource]) -> str:
    # `textes_du_compte` : messages du compte et extraits des pièces jointes.
    # Un chiffre qui y figure n'a pas besoin de page pour source.
    chiffres = chiffres_controles(reponse) - chiffres_des_sources(textes_du_compte)
    if not chiffres:
        return reponse
    deja_en_lien = {normaliser_url(url) for _, url in urls_ecrites([reponse])}
    # Une même page lue plusieurs fois : une seule mention, avec le premier
    # titre connu.
    regroupees: dict[str, PageSource] = {}
    for page in pages:
        cle = normaliser_url(page.url)
        deja = regroupees.get(cle)
        regroupees[cle] = page if deja is None else PageSource(deja.url, deja.titre or page.titre, deja.textes + page.textes)
    citees = [
        page
        for cle, page in regroupees.items()
        if cle not in deja_en_lien and chiffres & chiffres_des_sources(page.textes)
    ]
    if not citees:
        return reponse
    liens = ", ".join(f"[{_texte_du_lien(page)}]({page.url})" for page in citees)
    return f"{reponse.rstrip()}\n\nSources : {liens}"


def _texte_du_lien(page: PageSource) -> str:
    # Des crochets dans le titre fermeraient le lien Markdown trop tôt.
    titre = page.titre.strip().replace("[", "(").replace("]", ")")
    return titre or page.url
