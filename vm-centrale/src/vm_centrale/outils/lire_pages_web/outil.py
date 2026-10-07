import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from vm_centrale.compte_tokens import compter_tokens
from vm_centrale.config import MODELE_CHAT
from vm_centrale.garde_fous import normaliser_url, urls_ecrites
from vm_centrale.inspecteur import payload_depuis_erreur, reponse_depuis_erreur
from vm_centrale.models import Message, QuestionCouverte, ResultatRechercheWeb
from vm_centrale.outils.base import AppelMistralOutil, ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.recherche_web.outil import PLAFOND_TOKENS_PAGES, lire_pages
from vm_centrale.questions_couvertes import REPONSE_MAX

_NOM = "lire_pages_web"
_PAGE_INTROUVABLE = "Page introuvable."
_EXTRACTION_INDISPONIBLE = "Extraction indisponible : la page n'a pas pu être relue."
_NON_TROUVE = "Non trouvé dans cette page pour ce besoin."
# Avec un besoin, une page au-delà du plafond de rechercher_web (spec 1.4.2)
# n'est ni coupée ni relue : un « non trouvé » sur une page coupée passerait
# pour un « non trouvé » sur la page entière. Consigne de réponse honnête
# (#151) : le modèle a résumé de mémoire une page qu'il n'avait pas lue.
# Durcie en #152 : sans rien de la page, il en devinait le sujet.
_PAGE_TROP_LONGUE = (
    "Page trop longue pour être lue : son contenu ne t'a pas été transmis. "
    "Dis au collaborateur que la page était trop longue pour être lue. Tu ne "
    "connais de cette page que son URL et, s'il est donné, son titre : "
    "n'affirme rien d'autre sur ce qu'elle contient. Réponds sur le sujet "
    "seulement s'il est connu (titre de la page ou message du collaborateur), "
    "en précisant que cela vient de tes connaissances et non de la page."
)
# Sans besoin, le texte nettoyé de chaque page part au modèle, coupé à ce
# plafond : de quoi découvrir de quoi parle une page, pas la relire entière.
_TEXTE_SANS_BESOIN_MAX = 8_000
_TEXTE_COUPE = "[… texte coupé : relis avec un besoin pour une information précise]"
_PAGE_DU_COMPTE_NON_LUE = "page non lue (PDF, page refusée ou délai dépassé)."
# Relecture forcée en échec (#157) : seul cas où le modèle reçoit l'âge de
# la copie de la conversation (spec 1.4.3, « Visibilité »). Suivie du
# contenu habituel de cette copie.
_RELECTURE_EN_ECHEC = (
    "la page n'a pas pu être relue (nouveau téléchargement en échec). Dis au "
    "collaborateur que tu n'as pas réussi à relire la page, puis réponds "
    "d'après la version lue le {date}, en le précisant."
)
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
                    "retelecharger": {
                        "type": "boolean",
                        "description": (
                            "Facultatif : vrai seulement si l'utilisateur dit "
                            "que la page a changé ou demande de la relire à "
                            "jour. La page est alors téléchargée de nouveau au "
                            "lieu d'être relue depuis la conversation."
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
    # le dernier résultat (son extrait de moteur). Comparaison normalisée,
    # comme pour une URL du compte (le modèle redonne parfois l'URL sans
    # « www. » ou avec un « / » final).
    if url is None:
        return None
    cle = normaliser_url(url)
    candidats = [resultat for resultat in resultats if normaliser_url(resultat.url) == cle]
    lus = [resultat for resultat in candidats if resultat.texte_nettoye]
    return (lus or candidats or [None])[-1]


def _url_de_la_conversation(url, resultats: list[ResultatRechercheWeb], urls_du_compte: dict[str, str]) -> str | None:
    # L'URL d'un résultat, sinon l'URL écrite par le compte sous sa forme
    # d'origine (le modèle la redonne parfois sans « www. » ou avec un « / »
    # final). None : « Page introuvable. ».
    if not isinstance(url, str):
        return None
    url = url.strip()
    if _page_de_la_conversation(url, resultats) is not None:
        return url
    return urls_du_compte.get(normaliser_url(url))


def _avec_schema(url: str) -> str:
    # « www.bbass.fr » écrite par le compte : sans schéma, le téléchargeur la
    # refuse, et la page resterait non lue toute la conversation.
    return url if re.match(r"https?://", url, re.IGNORECASE) else f"https://{url}"


def _a_retenter(page: ResultatRechercheWeb | None, contexte: ContexteTour) -> bool:
    # Page sans texte (échec, non téléchargée ou retirée par le plafond)
    # enregistrée à un tour antérieur (#156) : `message_id` n'est rattaché
    # qu'à la fin de son tour. Au même tour, ou déjà retentée dans ce tour,
    # pas de nouvel essai en boucle.
    return (
        page is not None
        and not page.texte_nettoye
        and page.message_id is not None
        and page.id not in contexte.pages_retentees
    )


@dataclass(frozen=True)
class _RelectureForcee:
    reussie: bool
    questions_supprimees: int
    # Date de la copie de la conversation, pour la consigne d'échec.
    date_copie: datetime

    def trace(self, url: str) -> dict:
        return {"url": url, "reussie": self.reussie, "questions_supprimees": self.questions_supprimees}


def _relire_de_force(
    urls: list[str], resultats: list[ResultatRechercheWeb], contexte: ContexteTour
) -> tuple[list[tuple[ResultatRechercheWeb, dict]], dict[int, _RelectureForcee]]:
    # `retelecharger` (#157) : chaque page déjà en base est téléchargée sans
    # passer par le cache, une fois par URL et par tour au plus (un appel
    # suivant du tour sert la copie actuelle). Succès : cache mis à jour par
    # lire_pages, copie de la conversation remplacée sur toutes les lignes
    # de l'URL (sources du garde-fou chiffres), questions couvertes de la
    # page supprimées (jamais une réponse lue sur l'ancienne version).
    # Échec : rien ne change.
    a_relire: dict[str, ResultatRechercheWeb] = {}
    for url in urls:
        page = _page_de_la_conversation(url, resultats)
        if page is None:
            continue
        cle = normaliser_url(page.url)
        if cle not in contexte.pages_relues_de_force:
            contexte.pages_relues_de_force.add(cle)
            a_relire[cle] = page
    if not a_relire:
        return [], {}
    pages = lire_pages([_avec_schema(page.url) for page in a_relire.values()], contexte, sans_cache=True)
    maintenant = datetime.now(timezone.utc)
    relectures: dict[int, _RelectureForcee] = {}
    for (cle, ligne), page in zip(a_relire.items(), pages):
        # Pas de nouvel essai #156 en plus dans ce tour.
        contexte.pages_retentees.add(ligne.id)
        if not page.texte:
            relectures[ligne.id] = _RelectureForcee(False, 0, ligne.date_creation)
            continue
        copies = [resultat for resultat in resultats if normaliser_url(resultat.url) == cle]
        for copie in copies:
            copie.texte_nettoye = page.texte
            copie.titre = page.titre or copie.titre
            copie.date_creation = maintenant
        supprimees = (
            contexte.db.query(QuestionCouverte)
            .filter(QuestionCouverte.resultat_recherche_web_id.in_([copie.id for copie in copies]))
            .delete(synchronize_session=False)
        )
        relectures[ligne.id] = _RelectureForcee(True, supprimees, maintenant)
    contexte.db.flush()
    return [(ligne, page.trace()) for ligne, page in zip(a_relire.values(), pages)], relectures


def _consigne_relecture_en_echec(page: ResultatRechercheWeb, relecture: _RelectureForcee) -> str:
    # Date seule : `date_creation` est enregistrée sans fuseau.
    return f"Page {page.url} : " + _RELECTURE_EN_ECHEC.format(date=f"{relecture.date_copie:%d/%m/%Y}")


def _lire_pages_sans_texte(
    urls: list[str], resultats: list[ResultatRechercheWeb], contexte: ContexteTour, sans_cache: bool = False
) -> list[tuple[ResultatRechercheWeb, dict]]:
    # Même chaîne que rechercher_web (cache commun, téléchargement, statut,
    # HTML, nettoyage) pour une URL du compte pas encore en base (#140) et
    # pour une page sans texte d'un tour antérieur (#156). Une URL du compte
    # en échec (PDF, refus, délai) est enregistrée sans texte ; une page
    # retentée en échec ne change pas.
    nouvelles = list(dict.fromkeys(url for url in urls if _page_de_la_conversation(url, resultats) is None))
    retentees = list(
        {
            page.id: page
            for page in (_page_de_la_conversation(url, resultats) for url in urls)
            if _a_retenter(page, contexte)
        }.values()
    )
    if not nouvelles and not retentees:
        return []
    pages = lire_pages(
        [_avec_schema(url) for url in [*nouvelles, *(page.url for page in retentees)]], contexte, sans_cache
    )
    pages_nouvelles, pages_retentees = pages[: len(nouvelles)], pages[len(nouvelles) :]
    for ligne, page in zip(retentees, pages_retentees):
        contexte.pages_retentees.add(ligne.id)
        if page.texte:
            # Source du garde-fou chiffres dès ce tour. Le titre du moteur
            # reste si la page n'en donne pas.
            ligne.texte_nettoye = page.texte
            ligne.titre = page.titre or ligne.titre
            # Date de la copie de la conversation (consigne d'une relecture
            # forcée en échec, #157).
            ligne.date_creation = datetime.now(timezone.utc)
    maintenant = datetime.now(timezone.utc)
    lignes = [
        ResultatRechercheWeb(
            conversation_id=contexte.conversation_id,
            requete="",
            # Telle qu'écrite par le compte, sans le schéma ajouté.
            url=url,
            # `<title>` de la page : seul indice donné au modèle sur une
            # page trop longue (#152).
            titre=page.titre,
            extrait_moteur="",
            # Source du garde-fou chiffres, comme une page trouvée.
            texte_nettoye=page.texte,
            provenance="utilisateur",
            date_creation=maintenant,
        )
        for url, page in zip(nouvelles, pages_nouvelles)
    ]
    contexte.db.add_all(lignes)
    # Flush (jamais commit), comme rechercher_web : rattachée au message à
    # la fin du tour, annulée si le tour échoue.
    contexte.db.flush()
    resultats.extend(lignes)
    # Ligne enregistrée et trace de son téléchargement : la page n'est
    # comptée en tokens qu'avec un besoin (voir _trace_telechargee).
    return [(ligne, page.trace()) for ligne, page in zip([*lignes, *retentees], [*pages_nouvelles, *pages_retentees])]


def _trace_telechargee(ligne: ResultatRechercheWeb, trace: dict, tokens: dict[int, tuple[str, int]]) -> dict:
    # Jamais un « tokens: 0 » trompeur dans l'inspecteur (#151) : le vrai
    # compte de la page s'il a été fait, sinon pas de champ.
    trace = {cle: valeur for cle, valeur in trace.items() if cle != "tokens"}
    if ligne.id in tokens:
        trace["tokens"] = tokens[ligne.id][1]
    return trace


def _refus_page_trop_longue(page: ResultatRechercheWeb) -> str:
    # Le titre (du moteur, ou `<title>` d'une page du compte), jamais une
    # ligne du texte : sans lui, le modèle devinait le sujet de la page à
    # partir de son URL (#152, Les Trois Mousquetaires pour Les Misérables).
    bloc = f"Page {page.url} : {_PAGE_TROP_LONGUE}"
    return f"{bloc}\nTitre de la page : {page.titre.strip()}" if page.titre.strip() else bloc


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
    connues = [url for url in cibles if url is not None]
    retelecharger = arguments.get("retelecharger") is True
    relues, relectures = _relire_de_force(connues, resultats, contexte) if retelecharger else ([], {})
    if retelecharger:
        # Une URL du compte pas encore en base est téléchargée sans passer
        # par le cache : c'est la relecture forcée de ce tour.
        contexte.pages_relues_de_force.update(normaliser_url(url) for url in connues)
    telechargees = [*relues, *_lire_pages_sans_texte(connues, resultats, contexte, sans_cache=retelecharger)]
    pages = [_page_de_la_conversation(url, resultats) if url is not None else None for url in cibles]
    # Une page jugée trop longue plus tôt dans ce tour (#151) est refusée,
    # avec ou sans besoin, sans être recomptée : sans besoin, son aperçu
    # passerait pour la page lue.
    refusees = {
        page.id for page in pages if page is not None and normaliser_url(page.url) in contexte.pages_trop_longues
    }
    # Seules les pages lues (texte nettoyé en base, page retentée comprise)
    # passent à l'appel d'extraction, une fois chacune, en parallèle. Sans
    # besoin, aucun appel : le texte part tel quel. Avec un besoin, une page
    # au-delà du plafond n'est pas relue.
    tokens = {
        page.id: (page.url, compter_tokens(page.texte_nettoye, MODELE_CHAT))
        for page in pages
        if besoin and page is not None and page.texte_nettoye and page.id not in refusees
    }
    for url, nombre in tokens.values():
        if nombre > PLAFOND_TOKENS_PAGES:
            contexte.pages_trop_longues.setdefault(normaliser_url(url), url)
    a_lire = {
        page.id: (page.url, page.texte_nettoye)
        for page in pages
        if page is not None and page.id in tokens and tokens[page.id][1] <= PLAFOND_TOKENS_PAGES
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
        relecture = relectures.get(page.id)
        if relecture is not None and not relecture.reussie and page.texte_nettoye:
            # Suivie, bloc suivant, du contenu habituel de l'ancienne copie.
            blocs.append(_consigne_relecture_en_echec(page, relecture))
        if not page.texte_nettoye and page.provenance == "utilisateur":
            blocs.append(f"Page {page.url} : {_PAGE_DU_COMPTE_NON_LUE}")
            continue
        if not page.texte_nettoye:
            # Page non lue à la recherche (PDF, refus, délai), au même tour
            # ou en échec au nouvel essai : le modèle garde l'extrait du
            # moteur.
            blocs.append(f"Page {page.url} : non lue, seul l'extrait du moteur est disponible.\n{page.extrait_moteur}")
            continue
        if page.id in refusees:
            blocs.append(_refus_page_trop_longue(page))
            continue
        if not besoin:
            blocs.append(f"Page {page.url} :\n{_texte_sans_besoin(page.texte_nettoye)}")
            continue
        if page.id not in extractions:
            blocs.append(_refus_page_trop_longue(page))
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
    trace: dict = (
        {"pages_telechargees": [_trace_telechargee(ligne, trace, tokens) for ligne, trace in telechargees]}
        if telechargees
        else {}
    )
    if relectures:
        trace["relectures_forcees"] = [
            relecture.trace(page.url) for page in resultats if (relecture := relectures.get(page.id)) is not None
        ]
    if tokens:
        trace["plafond_tokens"] = PLAFOND_TOKENS_PAGES
        trace["pages_relues"] = [
            {"url": url, "tokens": nombre, "trop_longue": nombre > PLAFOND_TOKENS_PAGES}
            for url, nombre in tokens.values()
        ]
    return ResultatOutil("\n\n".join(blocs), trace=trace, appels_mistral=appels)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
