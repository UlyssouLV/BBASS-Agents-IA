import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from vm_centrale.config import MODELE_CHAT
from vm_centrale.inspecteur import payload_depuis_erreur, reponse_depuis_erreur
from vm_centrale.models import QuestionCouverte, ResultatRechercheWeb
from vm_centrale.outils.base import AppelMistralOutil, ContexteTour, Outil, ResultatOutil
from vm_centrale.questions_couvertes import REPONSE_MAX

_NOM = "lire_pages_web"
_PAGE_INTROUVABLE = "Page introuvable."
_EXTRACTION_INDISPONIBLE = "Extraction indisponible : la page n'a pas pu être relue."
_NON_TROUVE = "Non trouvé dans cette page pour ce besoin."
_BESOIN_MANQUANT = "Besoin manquant : indique ce que tu cherches dans ces pages."
# Consigne fixe de la relecture d'une page avec un besoin (spec 1.4.1) : elle
# ne reçoit que le besoin et le texte nettoyé de la page, jamais le contexte
# de la conversation (même cadre que l'appel d'extraction, ADR-0014).
CONSIGNE_LECTURE_PAGE = (
    "À partir de cette page, réponds seulement au besoin, de façon courte. "
    "N'ajoute rien qui ne soit pas écrit dans la page. Une information absente "
    "de la page est « non trouvé », jamais une estimation.\n\n"
    "Réponds en JSON : `trouvee`, vrai si la page répond au besoin ; "
    "`reponse`, la réponse (vide si non trouvé) ; `source`, l'URL de la page."
)
_SCHEMA_LECTURE_PAGE = {
    "type": "json_schema",
    "json_schema": {
        "name": "lecture_page",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "trouvee": {"type": "boolean"},
                "reponse": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["trouvee", "reponse", "source"],
            "additionalProperties": False,
        },
    },
}

logger = logging.getLogger(__name__)


def _resultats_de_la_conversation(contexte: ContexteTour) -> list[ResultatRechercheWeb]:
    # Ceux de ce tour compris (flush de rechercher_web, sans message encore).
    return (
        contexte.db.query(ResultatRechercheWeb)
        .filter(ResultatRechercheWeb.conversation_id == contexte.conversation_id)
        .order_by(ResultatRechercheWeb.id)
        .all()
    )


# Éligible dès qu'une recherche de la conversation a ramené un résultat : la
# Mémoire de la conversation liste ses URL, le modèle y pioche.
def _declarer(contexte: ContexteTour) -> dict | None:
    if (
        not contexte.db.query(ResultatRechercheWeb.id)
        .filter(ResultatRechercheWeb.conversation_id == contexte.conversation_id)
        .first()
    ):
        return None
    return {
        "type": "function",
        "function": {
            "name": _NOM,
            "description": (
                "Relit une ou plusieurs pages déjà trouvées par une recherche de "
                "cette conversation (URL listées dans la Mémoire de la "
                "conversation), pour un besoin précis, sans relancer de "
                "recherche. Renvoie, pour chaque page, ce qu'elle dit du "
                "besoin, ou « non trouvé »."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "URL des pages à relire, telles qu'écrites dans la Mémoire de la conversation.",
                    },
                    "besoin": {
                        "type": "string",
                        "description": "Ce qu'on cherche dans ces pages, en une ou deux phrases.",
                    },
                },
                "required": ["urls", "besoin"],
            },
        },
    }


@dataclass(frozen=True)
class _Lecture:
    trouvee: bool
    reponse: str


def _lire_reponse(contenu: str) -> _Lecture:
    # Lève ValueError, KeyError ou TypeError si le JSON n'a pas la forme
    # demandée. `source` n'est pas relu : une page par appel, la source est
    # l'URL lue.
    donnees = json.loads(contenu)
    trouvee, reponse = donnees["trouvee"], donnees["reponse"]
    if not isinstance(trouvee, bool) or not isinstance(reponse, str):
        raise TypeError("trouvee ou reponse mal formés")
    return _Lecture(trouvee and bool(reponse.strip()), reponse.strip())


def _extraire(besoin: str, url: str, texte: str, contexte: ContexteTour) -> tuple[_Lecture | None, AppelMistralOutil]:
    # Appel isolé : consigne fixe, besoin, texte nettoyé déjà en base. None
    # si l'appel échoue ou sort du JSON demandé, jamais d'exception. Lancé
    # dans un thread : ne touche pas à la session.
    messages = [
        {"role": "system", "content": CONSIGNE_LECTURE_PAGE},
        {"role": "user", "content": f"Besoin : {besoin}\n\n--- Page : {url} ---\n{texte}"},
    ]
    try:
        reponse = contexte.client_mistral.chat(messages, response_format=_SCHEMA_LECTURE_PAGE)
    except Exception as erreur:
        logger.warning("Relecture de page en échec : %s", erreur)
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
        return _lire_reponse(reponse.contenu), appel
    except (ValueError, KeyError, TypeError) as erreur:
        # Appel payé et tracé tel quel : seule sa sortie est inutilisable.
        logger.warning("Relecture de page hors du JSON attendu : %s", erreur)
        return None, appel


def _page_de_la_conversation(url, resultats: list[ResultatRechercheWeb]) -> ResultatRechercheWeb | None:
    # Une URL ramenée par plusieurs recherches : la dernière page lue, sinon
    # le dernier résultat (son extrait de moteur).
    if not isinstance(url, str):
        return None
    candidats = [resultat for resultat in resultats if resultat.url == url.strip()]
    lus = [resultat for resultat in candidats if resultat.texte_nettoye]
    return (lus or candidats or [None])[-1]


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    urls = arguments.get("urls")
    if not isinstance(urls, list) or not urls:
        return ResultatOutil(_PAGE_INTROUVABLE)
    besoin = str(arguments.get("besoin") or "").strip()
    if not besoin:
        return ResultatOutil(_BESOIN_MANQUANT)
    resultats = _resultats_de_la_conversation(contexte)
    pages = [_page_de_la_conversation(url, resultats) for url in urls]
    # Jamais de retéléchargement : seules les pages déjà lues (texte nettoyé
    # en base) passent à l'appel d'extraction, une fois chacune, en
    # parallèle.
    a_lire = {page.id: (page.url, page.texte_nettoye) for page in pages if page is not None and page.texte_nettoye}
    with ThreadPoolExecutor(max_workers=max(len(a_lire), 1)) as executeur:
        extractions = dict(
            zip(a_lire, executeur.map(lambda page: _extraire(besoin, *page, contexte), a_lire.values()))
        )

    blocs: list[str] = []
    enregistrees: set[int] = set()
    maintenant = datetime.now(timezone.utc)
    for url, page in zip(urls, pages):
        if page is None:
            blocs.append(f"Page {url} : {_PAGE_INTROUVABLE}")
            continue
        if not page.texte_nettoye:
            # Page non lue à la recherche (PDF, refus, délai) : jamais
            # retéléchargée, le modèle garde l'extrait du moteur.
            blocs.append(f"Page {page.url} : non lue, seul l'extrait du moteur est disponible.\n{page.extrait_moteur}")
            continue
        lecture, _ = extractions[page.id]
        if lecture is None:
            blocs.append(f"Page {page.url} : {_EXTRACTION_INDISPONIBLE}")
            continue
        blocs.append(f"Page {page.url} :\n{lecture.reponse if lecture.trouvee else _NON_TROUVE}")
        if page.id in enregistrees:
            continue
        enregistrees.add(page.id)
        # Origine `besoin`, hors des 8 questions initiales. Écrite par un
        # modèle : jamais une source des garde-fous.
        contexte.db.add(
            QuestionCouverte(
                conversation_id=contexte.conversation_id,
                resultat_recherche_web_id=page.id,
                question=besoin,
                reponse=lecture.reponse[:REPONSE_MAX] if lecture.trouvee else "",
                source=page.url,
                trouvee=lecture.trouvee,
                origine="besoin",
                date_creation=maintenant,
            )
        )
    # Flush (jamais commit) : un tour qui échoue plus loin les annule.
    contexte.db.flush()
    appels = tuple(appel for _, appel in extractions.values())
    return ResultatOutil("\n\n".join(blocs), appels_mistral=appels)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
