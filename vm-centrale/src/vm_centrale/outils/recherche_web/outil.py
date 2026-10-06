import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import trafilatura

from vm_centrale.config import MODELE_CHAT
from vm_centrale.inspecteur import payload_depuis_erreur, reponse_depuis_erreur
from vm_centrale.models import QuestionCouverte, ResultatRechercheWeb
from vm_centrale.moteur_recherche import MoteurIndisponible, ResultatRecherche
from vm_centrale.outils.base import AppelMistralOutil, ContexteTour, Outil, ResultatOutil
from vm_centrale.questions_couvertes import QUESTIONS_MAX as _QUESTIONS_MAX
from vm_centrale.questions_couvertes import REPONSE_MAX as _REPONSE_MAX
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
# Consigne fixe de l'appel d'extraction (spec 1.4.0, étape 5, décision
# n° 18), sans consigne de style : il ne reçoit que le besoin et les pages,
# jamais le contexte de la conversation (ADR-0014). Sortie JSON depuis la
# 1.4.1 : l'extrait et les questions couvertes.
CONSIGNE_EXTRACTION = (
    "À partir de ces pages, extrais seulement ce qui répond au besoin. Indique "
    "l'URL de chaque information. N'ajoute rien qui ne soit pas écrit dans les "
    "pages. Si rien ne répond au besoin, dis-le. Une information absente des "
    "pages est « non trouvé », jamais une estimation.\n\n"
    "Réponds en JSON : `extrait`, ce texte ; `questions_couvertes`, jusqu'à "
    f"{_QUESTIONS_MAX} questions auxquelles les pages répondent, chacune avec "
    f"sa réponse (`reponse`, {_REPONSE_MAX} caractères au plus) et l'URL de la "
    "page qui y répond (`source`)."
)
_SCHEMA_EXTRACTION = {
    "type": "json_schema",
    "json_schema": {
        "name": "extraction_web",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "extrait": {"type": "string"},
                "questions_couvertes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "reponse": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "required": ["question", "reponse", "source"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["extrait", "questions_couvertes"],
            "additionalProperties": False,
        },
    },
}
_EXTRACTION_INDISPONIBLE = (
    "Extraction indisponible : le texte des pages n'a pas pu être lu. Seuls le "
    "titre, l'URL et l'extrait du moteur de chaque résultat sont disponibles."
)
_AUCUNE_PAGE_LUE = (
    "Aucune page n'a pu être lue. Seuls le titre, l'URL et l'extrait du moteur "
    "de chaque résultat sont disponibles."
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
            "Renvoie la liste des résultats trouvés (titre, URL) et ce que les "
            "pages lues disent du besoin, avec l'URL de chaque information : "
            "seules ces URL peuvent être citées."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "requete": {
                    "type": "string",
                    "description": (
                        "La recherche, formulée comme dans un moteur de "
                        "recherche : mots-clés précis, sans phrase de politesse. "
                        "Pour une actualité, l'année de la date du jour donnée "
                        "dans la consigne. Seule cette chaîne part vers le moteur."
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
    # Une page téléchargée, pour l'appel d'extraction et l'échange local
    # d'inspecteur. `texte` : texte principal nettoyé, vide si la page est
    # ignorée.
    url: str
    statut: int | None = None
    texte: str = ""
    erreur: str | None = None
    retiree_par_plafond: bool = False

    @property
    def texte_lu(self) -> str:
        # Ce que l'appel d'extraction lit, et donc la source du garde-fou
        # chiffres : jamais une page retirée par le plafond.
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


def _liste_resultats(requete: str, resultats: list[ResultatRecherche], avec_extraits: bool) -> str:
    lignes = [f"Résultats de la recherche « {requete} » :"]
    for numero, resultat in enumerate(resultats, start=1):
        ligne = f"{numero}. {resultat.titre}\n   URL : {resultat.url}"
        if avec_extraits:
            ligne += f"\n   Extrait : {resultat.extrait}"
        lignes.append(ligne)
    return "\n".join(lignes)


@dataclass(frozen=True)
class _QuestionLue:
    question: str
    reponse: str
    source: str


@dataclass(frozen=True)
class _Extraction:
    extrait: str
    questions: tuple[_QuestionLue, ...]


def _lire_extraction(contenu: str) -> _Extraction:
    # Lève ValueError, KeyError ou TypeError si le JSON n'a pas la forme
    # demandée. Seules les _QUESTIONS_MAX premières questions comptent.
    donnees = json.loads(contenu)
    extrait = donnees["extrait"]
    questions = donnees["questions_couvertes"]
    if not isinstance(extrait, str) or not isinstance(questions, list):
        raise TypeError("extrait ou questions_couvertes mal formés")
    lues = []
    for question in questions[:_QUESTIONS_MAX]:
        champs = (question["question"], question["reponse"], question["source"])
        if not all(isinstance(champ, str) for champ in champs):
            raise TypeError("question couverte mal formée")
        lues.append(_QuestionLue(champs[0].strip(), champs[1].strip()[:_REPONSE_MAX], champs[2].strip()))
    return _Extraction(extrait, tuple(lues))


def _extraire(besoin: str, lues: list[_Page], contexte: ContexteTour) -> tuple[_Extraction | None, AppelMistralOutil]:
    # Appel d'extraction (ADR-0014) : le besoin et les pages lues, rien
    # d'autre. Son extrait va au modèle principal mais n'est jamais
    # enregistré comme source des garde-fous (décision n° 12) : il peut
    # inventer. Renvoie None si l'appel échoue (décision n° 17) ou si sa
    # réponse n'est pas le JSON demandé (spec 1.4.1), jamais d'exception.
    pages = "\n".join(f"\n--- Page : {page.url} ---\n{page.texte_lu}" for page in lues)
    messages = [
        {"role": "system", "content": CONSIGNE_EXTRACTION},
        {"role": "user", "content": f"Besoin : {besoin}\n\nPages :\n{pages}"},
    ]
    try:
        reponse = contexte.client_mistral.chat(messages, response_format=_SCHEMA_EXTRACTION)
    except Exception as erreur:
        logger.warning("Appel d'extraction en échec : %s", erreur)
        return None, AppelMistralOutil(
            type_appel="extraction_web",
            modele=MODELE_CHAT,
            requete_payload=payload_depuis_erreur(erreur),
            reponse_payload=reponse_depuis_erreur(erreur),
            usage=None,
            erreur=str(erreur),
        )
    appel = AppelMistralOutil(
        type_appel="extraction_web",
        modele=MODELE_CHAT,
        requete_payload=reponse.payload_envoye,
        reponse_payload=reponse.reponse_brute,
        usage=reponse.usage,
    )
    try:
        return _lire_extraction(reponse.contenu), appel
    except (ValueError, KeyError, TypeError) as erreur:
        # Appel payé et tracé tel quel : seule sa sortie est inutilisable.
        logger.warning("Appel d'extraction hors du JSON attendu : %s", erreur)
        return None, appel


def _enregistrer_questions(
    questions: tuple[_QuestionLue, ...], lignes: list[ResultatRechercheWeb], contexte: ContexteTour
) -> None:
    # Sur le résultat de la page source (spec 1.4.1). Une source qui n'est
    # pas une page lue (URL inventée, page en échec ou retirée par le
    # plafond) : question ignorée.
    pages_lues: dict[str, ResultatRechercheWeb] = {}
    for ligne in lignes:
        if ligne.texte_nettoye:
            pages_lues.setdefault(ligne.url, ligne)
    maintenant = datetime.now(timezone.utc)
    contexte.db.add_all(
        QuestionCouverte(
            conversation_id=contexte.conversation_id,
            resultat_recherche_web_id=pages_lues[question.source].id,
            question=question.question,
            reponse=question.reponse,
            source=question.source,
            trouvee=True,
            origine="initiale",
            date_creation=maintenant,
        )
        for question in questions
        if question.source in pages_lues and question.question
    )
    contexte.db.flush()


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    # `besoin` ne part jamais vers le moteur (ADR-0013) : il ne va qu'à
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
    lignes = [
        ResultatRechercheWeb(
            conversation_id=contexte.conversation_id,
            requete=requete,
            url=resultat.url,
            titre=resultat.titre,
            extrait_moteur=resultat.extrait,
            # Source du garde-fou chiffres : jamais une page retirée par le
            # plafond, que l'appel d'extraction n'a pas lue.
            texte_nettoye=textes.get(resultat.url, ""),
            date_creation=maintenant,
        )
        for resultat in resultats
    ]
    contexte.db.add_all(lignes)
    # Flush (jamais commit) : les garde-fous du même tour relisent ces URL en
    # base, et un tour qui échoue plus loin les annule avec le reste.
    contexte.db.flush()

    trace = {
        "resultats": [asdict(resultat) for resultat in resultats],
        "pages": [page.trace() for page in pages],
    }
    lues = [page for page in pages if page.texte_lu]
    if not lues:
        # Rien à extraire : pas d'appel payé pour rien, le modèle garde les
        # extraits du moteur.
        contenu = f"{_liste_resultats(requete, resultats, avec_extraits=True)}\n\n{_AUCUNE_PAGE_LUE}"
        return ResultatOutil(contenu, trace=trace)

    extraction, appel = _extraire(str(arguments.get("besoin") or "").strip(), lues, contexte)
    if extraction is None:
        contenu = f"{_liste_resultats(requete, resultats, avec_extraits=True)}\n\n{_EXTRACTION_INDISPONIBLE}"
    else:
        # L'extrait et la liste (titre, URL), jamais le texte des pages
        # (spec 1.4.0, étape 6).
        contenu = (
            f"{_liste_resultats(requete, resultats, avec_extraits=False)}\n\n"
            f"Extrait des pages lues, pour ce besoin :\n{extraction.extrait}"
        )
        _enregistrer_questions(extraction.questions, lignes, contexte)
    return ResultatOutil(contenu, trace=trace, appels_mistral=(appel,))


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
