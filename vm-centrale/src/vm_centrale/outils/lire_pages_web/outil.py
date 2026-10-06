import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from vm_centrale.config import MODELE_CHAT
from vm_centrale.garde_fous import normaliser_url, urls_ecrites
from vm_centrale.inspecteur import payload_depuis_erreur, reponse_depuis_erreur
from vm_centrale.models import Message, QuestionCouverte, ResultatRechercheWeb
from vm_centrale.outils.base import AppelMistralOutil, ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.recherche_web.outil import lire_page
from vm_centrale.questions_couvertes import REPONSE_MAX

_NOM = "lire_pages_web"
_PAGE_INTROUVABLE = "Page introuvable."
_EXTRACTION_INDISPONIBLE = "Extraction indisponible : la page n'a pas pu être relue."
_NON_TROUVE = "Non trouvé dans cette page pour ce besoin."
# Sans besoin, le texte nettoyé de chaque page part au modèle, coupé à ce
# plafond : de quoi découvrir de quoi parle une page, pas la relire entière.
_TEXTE_SANS_BESOIN_MAX = 8_000
_TEXTE_COUPE = "[… texte coupé : relis avec un besoin pour une information précise]"
_PAGE_DU_COMPTE_NON_LUE = "page non lue (PDF, page refusée ou délai dépassé)."
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


def _urls_du_compte(contexte: ContexteTour) -> dict[str, str]:
    # URL normalisée → URL telle que le compte l'a écrite la première fois,
    # message du tour compris (même règle que le garde-fou URL et la Mémoire
    # de la conversation) : jamais une URL écrite par l'assistant.
    messages = (
        contexte.db.query(Message.contenu)
        .filter(Message.conversation_id == contexte.conversation_id, Message.role == "user")
        .order_by(Message.id)
        .all()
    )
    textes = [contenu for (contenu,) in messages] + [contexte.message_du_tour]
    return {normaliser_url(url): url for _, url in urls_ecrites(textes)}


# Éligible dès qu'une recherche de la conversation a ramené un résultat, ou
# que le compte a écrit une URL (#140) : la Mémoire de la conversation liste
# ces URL, le modèle y pioche.
def _declarer(contexte: ContexteTour) -> dict | None:
    if (
        not contexte.db.query(ResultatRechercheWeb.id)
        .filter(ResultatRechercheWeb.conversation_id == contexte.conversation_id)
        .first()
        and not _urls_du_compte(contexte)
    ):
        return None
    return {
        "type": "function",
        "function": {
            "name": _NOM,
            "description": (
                "Lit une ou plusieurs pages de cette conversation (URL listées "
                "dans la Mémoire de la conversation : trouvées par une "
                "recherche, ou envoyées par l'utilisateur), sans relancer de "
                "recherche. Sans `besoin` : le texte de chaque page (coupé "
                "s'il est long), pour découvrir de quoi elle parle, par "
                "exemple une URL envoyée seule. Avec `besoin` : pour chaque "
                "page, ce qu'elle dit du besoin, ou « non trouvé »."
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
                        "description": (
                            "Facultatif : ce qu'on cherche dans ces pages, en "
                            "une ou deux phrases. À omettre si on ne sait pas "
                            "encore de quoi parle la page : ne jamais deviner."
                        ),
                    },
                },
                "required": ["urls"],
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


def _page_de_la_conversation(url: str | None, resultats: list[ResultatRechercheWeb]) -> ResultatRechercheWeb | None:
    # Une URL ramenée par plusieurs recherches : la dernière page lue, sinon
    # le dernier résultat (son extrait de moteur).
    candidats = [resultat for resultat in resultats if resultat.url == url]
    lus = [resultat for resultat in candidats if resultat.texte_nettoye]
    return (lus or candidats or [None])[-1]


def _url_de_la_conversation(url, resultats: list[ResultatRechercheWeb], urls_du_compte: dict[str, str]) -> str | None:
    # L'URL d'un résultat telle quelle, sinon l'URL écrite par le compte
    # sous sa forme d'origine (le modèle la redonne parfois sans « www. »
    # ou avec un « / » final). None : « Page introuvable. ».
    if not isinstance(url, str):
        return None
    url = url.strip()
    if any(resultat.url == url for resultat in resultats):
        return url
    return urls_du_compte.get(normaliser_url(url))


def _telecharger_pages_du_compte(
    urls: list[str], resultats: list[ResultatRechercheWeb], contexte: ContexteTour
) -> list[dict]:
    # Au premier appel seulement (#140) : une URL déjà en base n'est jamais
    # retéléchargée dans la conversation, lue ou non. Même chaîne que
    # rechercher_web (téléchargement, statut, HTML, nettoyage) ; en échec
    # (PDF, refus, délai), la ligne est enregistrée sans texte.
    a_telecharger = list(dict.fromkeys(url for url in urls if _page_de_la_conversation(url, resultats) is None))
    if not a_telecharger:
        return []
    with ThreadPoolExecutor(max_workers=len(a_telecharger)) as executeur:
        pages = list(executeur.map(lambda url: lire_page(url, contexte.telechargeur_pages), a_telecharger))
    maintenant = datetime.now(timezone.utc)
    lignes = [
        ResultatRechercheWeb(
            conversation_id=contexte.conversation_id,
            requete="",
            url=page.url,
            titre="",
            extrait_moteur="",
            # Source du garde-fou chiffres, comme une page trouvée.
            texte_nettoye=page.texte,
            provenance="utilisateur",
            date_creation=maintenant,
        )
        for page in pages
    ]
    contexte.db.add_all(lignes)
    # Flush (jamais commit), comme rechercher_web : rattachée au message à
    # la fin du tour, annulée si le tour échoue.
    contexte.db.flush()
    resultats.extend(lignes)
    return [page.trace() for page in pages]


def _texte_sans_besoin(texte: str) -> str:
    if len(texte) <= _TEXTE_SANS_BESOIN_MAX:
        return texte
    return f"{texte[:_TEXTE_SANS_BESOIN_MAX]}\n{_TEXTE_COUPE}"


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    urls = arguments.get("urls")
    if not isinstance(urls, list) or not urls:
        return ResultatOutil(_PAGE_INTROUVABLE)
    besoin = str(arguments.get("besoin") or "").strip()
    resultats = _resultats_de_la_conversation(contexte)
    urls_du_compte = _urls_du_compte(contexte)
    cibles = [_url_de_la_conversation(url, resultats, urls_du_compte) for url in urls]
    telechargees = _telecharger_pages_du_compte([url for url in cibles if url is not None], resultats, contexte)
    pages = [_page_de_la_conversation(url, resultats) if url is not None else None for url in cibles]
    # Jamais de retéléchargement : seules les pages déjà lues (texte nettoyé
    # en base) passent à l'appel d'extraction, une fois chacune, en
    # parallèle. Sans besoin, aucun appel : le texte part tel quel.
    a_lire = {
        page.id: (page.url, page.texte_nettoye)
        for page in pages
        if besoin and page is not None and page.texte_nettoye
    }
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
        if not page.texte_nettoye and page.provenance == "utilisateur":
            blocs.append(f"Page {page.url} : {_PAGE_DU_COMPTE_NON_LUE}")
            continue
        if not page.texte_nettoye:
            # Page non lue à la recherche (PDF, refus, délai) : jamais
            # retéléchargée, le modèle garde l'extrait du moteur.
            blocs.append(f"Page {page.url} : non lue, seul l'extrait du moteur est disponible.\n{page.extrait_moteur}")
            continue
        if not besoin:
            blocs.append(f"Page {page.url} :\n{_texte_sans_besoin(page.texte_nettoye)}")
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
    trace = {"pages_telechargees": telechargees} if telechargees else {}
    return ResultatOutil("\n\n".join(blocs), trace=trace, appels_mistral=appels)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
