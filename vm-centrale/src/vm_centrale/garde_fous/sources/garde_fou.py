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


@dataclass(frozen=True)
class LectureSource:
    # Une fiche lue par un outil d'un logiciel du cabinet (spec 1.5.0,
    # table `lectures_outils`) : citée sans lien, « Moduléo, affaire
    # 2024-123 ».
    citation: str
    texte: str


def ajouter_sources(
    reponse: str, textes_du_compte: Iterable[str], sources: Iterable[PageSource | LectureSource]
) -> str:
    # `textes_du_compte` : messages du compte et extraits des pièces jointes.
    # Un chiffre qui y figure n'a pas besoin de source. `sources` : pages et
    # lectures d'outil dans l'ordre de la conversation, la plus récente en
    # dernier.
    sources = list(sources)
    pages = [source for source in sources if isinstance(source, PageSource)]
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
    # Clé → texte cité : URL normalisée d'une page, citation d'une lecture.
    citees: dict[str, str] = {}
    for source in reversed(sources):
        trouves = chiffres & chiffres_des_sources([source.texte])
        if not trouves:
            continue
        chiffres -= trouves
        if isinstance(source, LectureSource):
            citees.setdefault(source.citation, source.citation)
            continue
        cle = normaliser_url(source.url)
        citees.setdefault(cle, f"[{_texte_du_lien(titres[cle], source.url)}]({source.url})")
    # Une citation que le modèle a déjà écrite n'est pas répétée (test
    # humain 1.5.0, conversation 113, #180).
    liens = [lien for lien in reversed(citees.values()) if not _deja_citee(lien, reponse)]
    if not liens:
        return reponse
    # Citation d'une lecture → logiciel cité (« Moduléo, affaire X » →
    # « Moduléo ») : un « Moduléo » écrit seul devient la citation complète.
    logiciels = {
        source.citation: source.citation.partition(", ")[0] for source in sources if isinstance(source, LectureSource)
    }
    return (
        _completer_le_bloc(reponse.rstrip(), liens, logiciels)
        or f"{reponse.rstrip()}\n\nSources : {', '.join(liens)}"
    )


def _deja_citee(citation: str, reponse: str) -> bool:
    # Citation entière, suivie d'une fin de ligne ou d'un séparateur :
    # « Moduléo, affaire 2024-12 » n'est pas dans « …, affaire 2024-123 »,
    # ni « contact Dupont » dans « contact Dupont SARL ». Un lien Markdown
    # se ferme sur sa parenthèse : jamais le début d'un autre.
    if citation.endswith(")"):
        return citation in reponse
    motif = rf"{re.escape(citation)}(?=[ \t]*(?:$|[,;)\]]|\.(?:\s|$)))"
    return re.search(motif, reponse, re.MULTILINE) is not None


def _est_une_annee(chiffre: str) -> bool:
    return chiffre.isdigit() and 1900 <= int(chiffre) <= 2100


def _completer_le_bloc(reponse: str, liens: list[str], logiciels: dict[str, str]) -> str | None:
    # Le bloc de sources que le modèle a écrit à la fin de sa réponse reçoit
    # les pages manquantes, au même format (ligne ou liste à puces).
    # `logiciels` : citation d'une lecture → logiciel qu'elle cite.
    lignes = reponse.split("\n")
    puces, marque = 0, None
    while puces < len(lignes) and (puce := _MOTIF_PUCE.match(lignes[-1 - puces])):
        marque = marque or puce.group(1)
        puces += 1
    if puces == len(lignes):
        return None
    ligne_entete = len(lignes) - 1 - puces
    entete = _MOTIF_ENTETE.match(lignes[ligne_entete])
    if entete is None:
        return None
    contenu = entete.group(4)
    for logiciel in dict.fromkeys(logiciels[lien] for lien in liens if lien in logiciels):
        siens = [lien for lien in liens if logiciels.get(lien) == logiciel]
        # « Moduléo » seul : en début de ligne ou après « , » / « ; », suivi
        # de la fin de ligne ou d'un séparateur qui n'ouvre pas une référence
        # (« Moduléo, affaire 2024-123 » n'est pas seul).
        seul = re.compile(rf"(?:^|(?<=[,;] )){re.escape(logiciel)}(?=[ \t]*(?:$|[,;](?![ \t]*[a-zà-ÿ])))")
        if seul.search(contenu):
            contenu = seul.sub(lambda _: ", ".join(siens), contenu, count=1)
        elif (puce_seule := _puce_seule(lignes, ligne_entete + 1, logiciel)) is not None:
            index, marque_seule = puce_seule
            lignes[index:index + 1] = [f"{marque_seule}{lien}" for lien in siens]
        else:
            continue
        liens = [lien for lien in liens if lien not in siens]
    lignes[ligne_entete] = f"{entete.group(1)}Sources{entete.group(3)}{contenu}"
    if not liens:
        return "\n".join(lignes)
    if marque is not None:
        lignes += [f"{marque}{lien}" for lien in liens]
    else:
        separateur = ", " if contenu else " "
        lignes[-1] = lignes[-1].rstrip() + separateur + ", ".join(liens)
    return "\n".join(lignes)


def _puce_seule(lignes: list[str], debut: int, logiciel: str) -> tuple[int, str] | None:
    # Index et marque de la puce « - Moduléo » du bloc, s'il y en a une.
    for index in range(debut, len(lignes)):
        puce = _MOTIF_PUCE.match(lignes[index])
        if puce is not None and lignes[index][puce.end(1):].strip() == logiciel:
            return index, puce.group(1)
    return None


def _texte_du_lien(titre: str, url: str) -> str:
    # Des crochets dans le titre fermeraient le lien Markdown trop tôt.
    titre = titre.strip().replace("[", "(").replace("]", ")")
    return titre or url
