import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import trafilatura

from vm_centrale.models import ResultatRechercheWeb
from vm_centrale.moteur_recherche import MoteurIndisponible, ResultatRecherche
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.telechargement_pages import PageIndisponible, TelechargeurPages

_NOM = "rechercher_web"
_NOMBRE_RESULTATS = 5
_NOMBRE_PAGES_TELECHARGEES = 3
# Plafond global des pages nettoyées (spec 1.4.0, étape 4) : environ 80 % de
# la fenêtre du modèle d'extraction (MODELE_CHAT). Fenêtre de
# `mistral-small-latest` relevée le 2026-10-06 : 128k tokens (Small 3.x) ou
# 256k (Small 4) selon les sources, la plus petite est retenue. Pas de
# tokenizer Mistral en local : estimation prudente à 3 caractères par token.
_FENETRE_EXTRACTION_TOKENS = 131_072
_CARACTERES_PAR_TOKEN = 3
_PLAFOND_CARACTERES_PAGES = int(_FENETRE_EXTRACTION_TOKENS * 0.8 * _CARACTERES_PAR_TOKEN)
_RECHERCHE_INDISPONIBLE = (
    "Recherche indisponible : le moteur de recherche ne répond pas. Réponds sans "
    "résultat de recherche et sans lien."
)
_AUCUN_RESULTAT = (
    "Aucun résultat pour cette recherche. Reformule la requête, ou réponds sans "
    "résultat de recherche et sans lien."
)

logger = logging.getLogger(__name__)

# Toujours le même schéma, éligible à chaque appel de chat principal (spec
# 1.4.0, décision n° 3) : c'est le modèle qui décide de chercher.
_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche sur Internet. À utiliser quand la réponse demande une "
            "information à trouver : une page ou un texte officiel, un texte "
            "réglementaire, une actualité, un classement, une donnée récente. "
            "Renvoie les résultats trouvés (titre, URL, extrait) : seules ces "
            "URL peuvent être citées."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "requete": {
                    "type": "string",
                    "description": (
                        "La recherche, formulée comme dans un moteur de "
                        "recherche : mots-clés précis, sans phrase de politesse. "
                        "Seule cette chaîne part vers le moteur."
                    ),
                },
                "besoin": {
                    "type": "string",
                    "description": (
                        "Ce qu'on cherche et pourquoi, en une ou deux phrases, "
                        "pour savoir quoi retenir des pages trouvées."
                    ),
                },
            },
            "required": ["requete", "besoin"],
        },
    },
}


def _declarer(contexte: ContexteTour) -> dict:
    return _SCHEMA


@dataclass
class _Page:
    # Une page téléchargée, pour le message `tool` et l'échange local
    # d'inspecteur. `texte` : texte principal nettoyé, vide si la page est
    # ignorée.
    url: str
    statut: int | None = None
    texte: str = ""
    erreur: str | None = None
    retiree_par_plafond: bool = False

    @property
    def texte_lu(self) -> str:
        # Ce que le modèle lit, et donc la source du garde-fou chiffres :
        # jamais une page retirée par le plafond.
        return "" if self.retiree_par_plafond else self.texte

    def trace(self) -> dict:
        return {
            "url": self.url,
            "statut": self.statut,
            "taille": len(self.texte),
            "retiree_par_plafond": self.retiree_par_plafond,
            "erreur": self.erreur,
        }


def _lire_page(url: str, telechargeur: TelechargeurPages) -> _Page:
    # Une page en échec (délai, statut HTTP, contenu non HTML, PDF compris)
    # est ignorée : son extrait de moteur reste (spec 1.4.0, étape 2).
    try:
        page = telechargeur.telecharger(url)
    except PageIndisponible as erreur:
        return _Page(url, erreur=str(erreur))
    if page.statut != 200:
        return _Page(url, statut=page.statut, erreur=f"statut HTTP {page.statut}")
    if "html" not in page.type_contenu.lower():
        return _Page(url, statut=page.statut, erreur=f"contenu non HTML ({page.type_contenu or 'inconnu'})")
    # Texte principal, sans menus, publicités ni scripts ; jamais coupé.
    texte = (trafilatura.extract(page.corps) or "").strip()
    if not texte:
        return _Page(url, statut=page.statut, erreur="aucun texte principal")
    return _Page(url, statut=page.statut, texte=texte)


def _lire_pages(resultats: list[ResultatRecherche], telechargeur: TelechargeurPages) -> list[_Page]:
    urls = [resultat.url for resultat in resultats[:_NOMBRE_PAGES_TELECHARGEES]]
    # En parallèle : le délai est celui de la page la plus lente, pas la
    # somme (PAGES_HTTP_TIMEOUT au plus chacune).
    with ThreadPoolExecutor(max_workers=_NOMBRE_PAGES_TELECHARGEES) as executeur:
        pages = list(executeur.map(lambda url: _lire_page(url, telechargeur), urls))
    # Plafond global seulement (décision n° 6) : tant que le total le
    # dépasse, la dernière page lue est retirée entière, jamais coupée.
    lues = [page for page in pages if page.texte]
    while lues and sum(len(page.texte) for page in lues) > _PLAFOND_CARACTERES_PAGES:
        lues.pop().retiree_par_plafond = True
    return pages


def _contenu_pour_le_modele(requete: str, resultats: list[ResultatRecherche], pages: list[_Page]) -> str:
    # En attendant l'appel d'extraction, le modèle reçoit la liste des
    # résultats et le texte nettoyé des pages lues.
    lignes = [f"Résultats de la recherche « {requete} » :"]
    for numero, resultat in enumerate(resultats, start=1):
        lignes.append(f"{numero}. {resultat.titre}\n   URL : {resultat.url}\n   Extrait : {resultat.extrait}")
    lues = [page for page in pages if page.texte_lu]
    if lues:
        lignes.append("\nTexte des pages lues :")
        lignes.extend(f"\n--- Page : {page.url} ---\n{page.texte_lu}" for page in lues)
    return "\n".join(lignes)


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    # `besoin` ne part jamais vers le moteur (ADR-0013) : il servira à
    # l'appel d'extraction.
    requete = str(arguments.get("requete") or "").strip()
    if not requete:
        return ResultatOutil(_AUCUN_RESULTAT, trace={"resultats": []})
    try:
        resultats = contexte.moteur_recherche.rechercher(requete)[:_NOMBRE_RESULTATS]
    except MoteurIndisponible as erreur:
        # Jamais de 500 (spec 1.4.0, décision n° 17) : le modèle lit la panne
        # dans le message `tool` et répond sans recherche.
        logger.warning("Moteur de recherche indisponible : %s", erreur)
        return ResultatOutil(_RECHERCHE_INDISPONIBLE, trace={"erreur": str(erreur)})
    if not resultats:
        return ResultatOutil(_AUCUN_RESULTAT, trace={"resultats": []})

    pages = _lire_pages(resultats, contexte.telechargeur_pages)
    textes = {page.url: page.texte_lu for page in pages}
    maintenant = datetime.now(timezone.utc)
    contexte.db.add_all(
        ResultatRechercheWeb(
            conversation_id=contexte.conversation_id,
            requete=requete,
            url=resultat.url,
            titre=resultat.titre,
            extrait_moteur=resultat.extrait,
            # Source du garde-fou chiffres : jamais une page retirée par le
            # plafond, que le modèle n'a pas lue.
            texte_nettoye=textes.get(resultat.url, ""),
            date_creation=maintenant,
        )
        for resultat in resultats
    )
    # Flush (jamais commit) : les garde-fous du même tour relisent ces URL en
    # base, et un tour qui échoue plus loin les annule avec le reste.
    contexte.db.flush()
    return ResultatOutil(
        _contenu_pour_le_modele(requete, resultats, pages),
        trace={
            "resultats": [asdict(resultat) for resultat in resultats],
            "pages": [page.trace() for page in pages],
        },
    )


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
