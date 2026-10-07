import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone

import trafilatura

from vm_centrale.cache_pages import ecrire_copie, lire_copie
from vm_centrale.compte_tokens import compter_tokens
from vm_centrale.config import FICHES_MODELES, MODELE_CHAT
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
# Plafond global des pages nettoyées (spec 1.4.0, étape 4) : 80 % de la
# fenêtre du modèle d'extraction (fiche MODELE_CHAT), en vrais tokens depuis
# la 1.4.2 (tokenizer de la fiche, compte_tokens.py). Aussi celui d'une page
# relue avec un besoin par lire_pages_web.
_FENETRE_EXTRACTION_TOKENS = FICHES_MODELES[MODELE_CHAT].fenetre_tokens
assert _FENETRE_EXTRACTION_TOKENS is not None
PLAFOND_TOKENS_PAGES = int(_FENETRE_EXTRACTION_TOKENS * 0.8)
_RECHERCHE_INDISPONIBLE = (
    "Recherche indisponible : le moteur de recherche ne répond pas. Réponds sans "
    "résultat de recherche et sans lien."
)
_AUCUN_RESULTAT = (
    "Aucun résultat pour cette recherche. Reformule la requête, ou réponds sans "
    "résultat de recherche et sans lien."
)
# Portée d'un fait, dans chaque consigne qui lit une page (extraction,
# lire_pages_web) : au test humain 1.4.3 (conversation 103, #160), « 6 à
# 12 semaines en Savoie » est devenu « en moyenne en France », avec une
# conversion « (1,5 à 3 mois) » absente des pages. Consigne seule : non
# vérifiable de façon fiable par le code.
REGLE_PORTEE = (
    "Un fait garde le lieu, la période et la population que la page lui donne "
    "(« en Savoie » ne devient jamais « en France ») ; aucune conversion ni "
    "aucun calcul absent de la page."
)
# Consigne fixe de l'appel d'extraction (spec 1.4.0, étape 5, décision
# n° 18), sans consigne de style : il ne reçoit que le besoin et les pages,
# jamais le contexte de la conversation (ADR-0014). Sortie JSON depuis la
# 1.4.1 : l'extrait et les questions couvertes. Depuis la 1.4.3 (#160),
# l'extrait est une liste de faits, chacun avec l'URL de sa page : un texte
# unique fondait les pages sans URL en face de chaque fait.
CONSIGNE_EXTRACTION = (
    "À partir de ces pages, extrais seulement ce qui répond au besoin, en faits "
    "courts, chacun avec l'URL de la page qui le dit. N'ajoute rien qui ne soit "
    f"pas écrit dans les pages. {REGLE_PORTEE} Si rien ne répond au besoin, ne "
    "donne aucun fait. Une information absente des pages est « non trouvé », "
    "jamais une estimation.\n\n"
    "Réponds en JSON : `faits`, la liste des faits (`texte`, le fait ; `source`, "
    "l'URL de la page qui le dit) ; `questions_couvertes`, jusqu'à "
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
                "faits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"texte": {"type": "string"}, "source": {"type": "string"}},
                        "required": ["texte", "source"],
                        "additionalProperties": False,
                    },
                },
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
            "required": ["faits", "questions_couvertes"],
            "additionalProperties": False,
        },
    },
}
_EXTRACTION_INDISPONIBLE = (
    "Extraction indisponible : le texte des pages n'a pas pu être lu. Seuls le "
    "titre, l'URL et l'extrait du moteur de chaque résultat sont disponibles."
)
_AUCUN_FAIT = "Les pages lues ne répondent pas à ce besoin."
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
    tokens: int = 0
    # `<title>` de la page (ou, à défaut, son titre principal), vide si
    # inconnu. Enregistré pour une URL écrite par le compte, qui n'a pas de
    # titre de moteur (lire_pages_web, #152).
    titre: str = ""
    # `cache` (copie du cache commun, spec 1.4.3) ou `telechargement`.
    origine: str = "telechargement"
    # Âge de la copie servie par le cache, None sinon.
    age_copie: timedelta | None = None

    @property
    def texte_lu(self) -> str:
        # Ce que l'appel d'extraction lit, et donc la source du garde-fou
        # chiffres : jamais une page retirée par le plafond.
        return "" if self.retiree_par_plafond else self.texte

    def trace(self) -> dict:
        trace = {
            "url": self.url,
            "statut": self.statut,
            "taille": len(self.texte),
            "tokens": self.tokens,
            "retiree_par_plafond": self.retiree_par_plafond,
            "erreur": self.erreur,
            "origine": self.origine,
        }
        if self.age_copie is not None:
            trace["age_copie_secondes"] = int(self.age_copie.total_seconds())
        return trace


def _telecharger(url: str, telechargeur: TelechargeurPages) -> _Page:
    # Une page en échec (délai, statut HTTP, contenu non HTML, PDF compris)
    # est ignorée : son extrait de moteur reste (spec 1.4.0, étape 2).
    # Lancée dans un thread : ne touche pas à la session.
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
    metadonnees = trafilatura.extract_metadata(page.corps)
    titre = ((metadonnees.title if metadonnees is not None else None) or "").strip()
    return _Page(url, statut=page.statut, texte=texte, titre=titre)


def lire_pages(urls: list[str], contexte: ContexteTour, sans_cache: bool = False) -> list[_Page]:
    # Une _Page par URL, dans l'ordre. Cache commun d'abord (spec 1.4.3,
    # ADR-0015) : une copie valide remplace le téléchargement, sauf
    # `sans_cache` (relecture forcée de lire_pages_web, #157). Une page
    # téléchargée et lue avec succès (200, HTML, texte principal non vide)
    # est écrite dans le cache, avant tout plafond ; jamais un échec.
    # Partagée avec lire_pages_web pour une URL écrite par le compte (#140).
    maintenant = datetime.now(timezone.utc)
    copies = {url: None if sans_cache else lire_copie(contexte.db, url, maintenant) for url in urls}
    a_telecharger = [url for url, copie in copies.items() if copie is None]
    telechargees: dict[str, _Page] = {}
    if a_telecharger:
        # En parallèle : le délai est celui de la page la plus lente, pas la
        # somme (PAGES_HTTP_TIMEOUT au plus chacune). La session reste dans
        # ce thread.
        with ThreadPoolExecutor(max_workers=len(a_telecharger)) as executeur:
            lues = executeur.map(lambda url: _telecharger(url, contexte.telechargeur_pages), a_telecharger)
            telechargees = dict(zip(a_telecharger, lues))
    for url, page in telechargees.items():
        if page.texte:
            ecrire_copie(contexte.db, url, page.texte, page.titre, maintenant)
    pages = []
    for url in urls:
        copie = copies[url]
        if copie is None:
            # Une copie par occurrence : le plafond marque chaque page à part.
            pages.append(replace(telechargees[url]))
        else:
            pages.append(
                _Page(url, statut=200, texte=copie.texte, titre=copie.titre, origine="cache", age_copie=copie.age)
            )
    return pages


def _lire_pages(resultats: list[ResultatRecherche], contexte: ContexteTour) -> list[_Page]:
    pages = lire_pages([resultat.url for resultat in resultats[:_NOMBRE_PAGES_TELECHARGEES]], contexte)
    # Plafond global seulement (décision n° 6) : tant que le total le
    # dépasse, la dernière page lue est retirée entière, jamais coupée.
    lues = [page for page in pages if page.texte]
    for page in lues:
        page.tokens = compter_tokens(page.texte, MODELE_CHAT)
    while lues and sum(page.tokens for page in lues) > PLAFOND_TOKENS_PAGES:
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
class _Fait:
    texte: str
    source: str


@dataclass(frozen=True)
class _Extraction:
    faits: tuple[_Fait, ...]
    questions: tuple[_QuestionLue, ...]


def _lire_extraction(contenu: str) -> _Extraction:
    # Lève ValueError, KeyError ou TypeError si le JSON n'a pas la forme
    # demandée. Seules les _QUESTIONS_MAX premières questions comptent.
    donnees = json.loads(contenu)
    faits = donnees["faits"]
    questions = donnees["questions_couvertes"]
    if not isinstance(faits, list) or not isinstance(questions, list):
        raise TypeError("faits ou questions_couvertes mal formés")
    lus = []
    for fait in faits:
        champs = (fait["texte"], fait["source"])
        if not all(isinstance(champ, str) for champ in champs):
            raise TypeError("fait mal formé")
        lus.append(_Fait(champs[0].strip(), champs[1].strip()))
    lues = []
    for question in questions[:_QUESTIONS_MAX]:
        champs = (question["question"], question["reponse"], question["source"])
        if not all(isinstance(champ, str) for champ in champs):
            raise TypeError("question couverte mal formée")
        lues.append(_QuestionLue(champs[0].strip(), champs[1].strip()[:_REPONSE_MAX], champs[2].strip()))
    return _Extraction(tuple(lus), tuple(lues))


def _extraire(besoin: str, lues: list[_Page], contexte: ContexteTour) -> tuple[_Extraction | None, AppelMistralOutil]:
    # Appel d'extraction (ADR-0014) : le besoin et les pages lues, rien
    # d'autre. Ses faits vont au modèle principal mais ne sont jamais
    # enregistrés comme source des garde-fous (décision n° 12) : il peut
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


def _faits_des_pages(faits: tuple[_Fait, ...], lues: list[_Page]) -> str:
    # Un fait par ligne, suivi de son URL (#160). Un fait dont la source
    # n'est pas une page lue de ce tour (URL inventée, page en échec ou
    # retirée par le plafond) est écarté, comme une question couverte.
    urls_lues = {page.url for page in lues}
    gardes = [fait for fait in faits if fait.texte and fait.source in urls_lues]
    if not gardes:
        return _AUCUN_FAIT
    lignes = "\n".join(f"- {fait.texte} (source : {fait.source})" for fait in gardes)
    return f"Ce que les pages lues disent du besoin, un fait par ligne avec sa source :\n{lignes}"


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

    pages = _lire_pages(resultats, contexte)
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
        # Les faits et la liste (titre, URL), jamais le texte des pages
        # (spec 1.4.0, étape 6).
        contenu = (
            f"{_liste_resultats(requete, resultats, avec_extraits=False)}\n\n"
            f"{_faits_des_pages(extraction.faits, lues)}"
        )
        _enregistrer_questions(extraction.questions, lignes, contexte)
    return ResultatOutil(contenu, trace=trace, appels_mistral=(appel,))


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
