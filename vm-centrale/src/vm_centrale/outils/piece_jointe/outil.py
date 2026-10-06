import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from vm_centrale.config import MODELE_CHAT
from vm_centrale.inspecteur import payload_depuis_erreur, reponse_depuis_erreur
from vm_centrale.models import PieceJointe, QuestionCouverte
from vm_centrale.outils.base import AppelMistralOutil, ContexteTour, Outil, ResultatOutil
from vm_centrale.questions_couvertes import REPONSE_MAX

_NOM = "relire_pieces_jointes"
_PIECE_JOINTE_INTROUVABLE = "Pièce jointe introuvable."
_TYPE_APPEL = "extraction_piece_jointe"
_EXTRACTION_INDISPONIBLE = "Extraction indisponible : les pièces jointes n'ont pas pu être relues pour ce besoin."
_NON_TROUVE = "Non trouvé dans ces pièces jointes pour ce besoin."
# Consigne fixe de la relecture avec un besoin (spec 1.4.1, #141) : elle ne
# reçoit que le besoin et les contenus extraits, jamais le contexte de la
# conversation (même cadre que l'appel d'extraction, ADR-0014).
CONSIGNE_RELECTURE_PIECES_JOINTES = (
    "À partir de ces pièces jointes, réponds seulement au besoin, de façon "
    "courte. N'ajoute rien qui ne soit pas écrit dans les pièces jointes. Une "
    "information absente est « non trouvé », jamais une estimation.\n\n"
    "Réponds en JSON : `trouvee`, vrai si une pièce jointe répond au besoin ; "
    "`reponse`, la réponse (vide si non trouvé) ; `source`, le nom de fichier "
    "de la pièce jointe qui répond."
)
_SCHEMA_RELECTURE = {
    "type": "json_schema",
    "json_schema": {
        "name": _TYPE_APPEL,
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


def _pieces_jointes_eligibles(contexte: ContexteTour) -> list[PieceJointe]:
    # Celle du tour en cours n'est liée à son message qu'après la réponse
    # (envoyer_message) : `message_id` non nul l'exclut d'office.
    return (
        contexte.db.query(PieceJointe)
        .filter(
            PieceJointe.conversation_id == contexte.conversation_id,
            PieceJointe.message_id.isnot(None),
        )
        .order_by(PieceJointe.id)
        .all()
    )


# Éligible dès qu'une pièce jointe de la conversation n'est pas celle du tour
# en cours, que son message soit encore dans la fenêtre des derniers messages
# ou non (spec 1.4.1) : au tour suivant l'envoi, le texte du message ne
# mentionne pas la pièce jointe et son contenu n'est plus envoyé.
def _declarer(contexte: ContexteTour) -> dict | None:
    pieces_jointes = _pieces_jointes_eligibles(contexte)
    if not pieces_jointes:
        return None
    # La description est générée à chaque appel à partir des pièces jointes
    # réellement éligibles de la conversation courante (jamais une liste
    # statique figée dans le schéma) : sans le nom de fichier en face de
    # chaque id, le modèle doit deviner quel entier correspond à quel
    # document (ticket #50 — cause du mauvais choix de pièce jointe observé
    # dans l'essai du 2026-09-17).
    liste_pieces_jointes = "\n".join(
        f"- id {piece_jointe.id} : {piece_jointe.nom_fichier}" for piece_jointe in pieces_jointes
    )
    return {
        "type": "function",
        "function": {
            "name": _NOM,
            "description": (
                "Relit une ou plusieurs pièces jointes envoyées plus tôt dans "
                "cette conversation : sans `besoin`, leur contenu complet ; "
                "avec `besoin`, seulement ce qu'elles en disent, ou « non "
                "trouvé ». Pièces jointes éligibles (id — nom de fichier) :\n"
                f"{liste_pieces_jointes}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "piece_jointe_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": (
                            "Identifiants des pièces jointes à relire, parmi "
                            "ceux listés ci-dessus."
                        ),
                    },
                    "besoin": {
                        "type": "string",
                        "description": (
                            "Facultatif : ce qu'on cherche dans ces pièces "
                            "jointes, en une ou deux phrases. Sans besoin, "
                            "le contenu complet est renvoyé."
                        ),
                    },
                },
                "required": ["piece_jointe_ids"],
            },
        },
    }


def _piece_jointe_de_la_conversation(identifiant, contexte: ContexteTour) -> PieceJointe | None:
    # bool est un int en Python : jamais une pièce jointe pour `true`.
    if not isinstance(identifiant, int) or isinstance(identifiant, bool):
        return None
    piece_jointe = contexte.db.get(PieceJointe, identifiant)
    if piece_jointe is None or piece_jointe.conversation_id != contexte.conversation_id:
        # Jamais une pièce jointe rattachée à une autre conversation, même
        # confidentialité que _recuperer_piece_jointe_du_compte
        # (routers/conversations.py).
        return None
    return piece_jointe


@dataclass(frozen=True)
class _Lecture:
    trouvee: bool
    reponse: str
    source: str


def _lire_reponse(contenu: str) -> _Lecture:
    # Lève ValueError, KeyError ou TypeError si le JSON n'a pas la forme
    # demandée.
    donnees = json.loads(contenu)
    trouvee, reponse, source = donnees["trouvee"], donnees["reponse"], donnees["source"]
    if not isinstance(trouvee, bool) or not isinstance(reponse, str) or not isinstance(source, str):
        raise TypeError("trouvee, reponse ou source mal formés")
    return _Lecture(trouvee and bool(reponse.strip()), reponse.strip(), source.strip())


def _extraire(
    besoin: str, pieces_jointes: list[PieceJointe], contexte: ContexteTour
) -> tuple[_Lecture | None, AppelMistralOutil]:
    # Un seul appel isolé pour toutes les pièces jointes relues : consigne
    # fixe, besoin, contenus extraits déjà en base. None si l'appel échoue
    # ou sort du JSON demandé, jamais d'exception.
    contenus = "\n\n".join(
        f"--- Pièce jointe « {piece_jointe.nom_fichier} » ---\n{piece_jointe.contenu_extrait or ''}"
        for piece_jointe in pieces_jointes
    )
    messages = [
        {"role": "system", "content": CONSIGNE_RELECTURE_PIECES_JOINTES},
        {"role": "user", "content": f"Besoin : {besoin}\n\n{contenus}"},
    ]
    try:
        reponse = contexte.client_mistral.chat(messages, response_format=_SCHEMA_RELECTURE)
    except Exception as erreur:
        logger.warning("Relecture de pièces jointes en échec : %s", erreur)
        return None, AppelMistralOutil(
            type_appel=_TYPE_APPEL,
            modele=MODELE_CHAT,
            requete_payload=payload_depuis_erreur(erreur),
            reponse_payload=reponse_depuis_erreur(erreur),
            usage=None,
            erreur=str(erreur),
        )
    appel = AppelMistralOutil(
        type_appel=_TYPE_APPEL,
        modele=MODELE_CHAT,
        requete_payload=reponse.payload_envoye,
        reponse_payload=reponse.reponse_brute,
        usage=reponse.usage,
    )
    try:
        return _lire_reponse(reponse.contenu), appel
    except (ValueError, KeyError, TypeError) as erreur:
        # Appel payé et tracé tel quel : seule sa sortie est inutilisable.
        logger.warning("Relecture de pièces jointes hors du JSON attendu : %s", erreur)
        return None, appel


def _pieces_jointes_de_la_reponse(lecture: _Lecture, pieces_jointes: list[PieceJointe]) -> list[PieceJointe]:
    # Où enregistrer la question couverte. Non trouvé : chacune des pièces
    # jointes relues. Trouvé : celle que nomme `source` (une seule relue :
    # elle, sans ambiguïté) ; une source qui n'est pas une pièce jointe
    # relue n'est pas enregistrée, comme pour l'appel d'extraction web.
    if not lecture.trouvee or len(pieces_jointes) == 1:
        return pieces_jointes
    source = lecture.source.casefold()
    return next(([pj] for pj in pieces_jointes if pj.nom_fichier.casefold() == source), [])


def _relire_pour_un_besoin(
    besoin: str, blocs: list[str], pieces_jointes: list[PieceJointe], contexte: ContexteTour
) -> ResultatOutil:
    if not pieces_jointes:
        return ResultatOutil("\n\n".join(blocs))
    lecture, appel = _extraire(besoin, pieces_jointes, contexte)
    if lecture is None:
        blocs.append(_EXTRACTION_INDISPONIBLE)
        return ResultatOutil("\n\n".join(blocs), pieces_jointes[0].id, appels_mistral=(appel,))
    blocs.append(f"{lecture.reponse} ({lecture.source})" if lecture.trouvee else _NON_TROUVE)
    maintenant = datetime.now(timezone.utc)
    # Origine `besoin`, hors des 8 questions initiales. Écrite par un
    # modèle : jamais une source des garde-fous. Flush (jamais commit) : un
    # tour qui échoue plus loin l'annule.
    contexte.db.add_all(
        QuestionCouverte(
            conversation_id=contexte.conversation_id,
            piece_jointe_id=piece_jointe.id,
            question=besoin,
            reponse=lecture.reponse[:REPONSE_MAX] if lecture.trouvee else "",
            source=piece_jointe.nom_fichier,
            trouvee=lecture.trouvee,
            origine="besoin",
            date_creation=maintenant,
        )
        for piece_jointe in _pieces_jointes_de_la_reponse(lecture, pieces_jointes)
    )
    contexte.db.flush()
    return ResultatOutil("\n\n".join(blocs), pieces_jointes[0].id, appels_mistral=(appel,))


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    identifiants = arguments.get("piece_jointe_ids")
    if not isinstance(identifiants, list) or not identifiants:
        return ResultatOutil(_PIECE_JOINTE_INTROUVABLE)
    besoin = str(arguments.get("besoin") or "").strip()
    # Sans besoin, un contenu par pièce jointe, chacun précédé de son nom de
    # fichier ; avec, une seule réponse pour toutes. Un id inconnu ou d'une
    # autre conversation : « Pièce jointe introuvable. » pour lui seul,
    # jamais une erreur HTTP ; les autres sont relues.
    blocs: list[str] = []
    relues: list[PieceJointe] = []
    for identifiant in identifiants:
        piece_jointe = _piece_jointe_de_la_conversation(identifiant, contexte)
        if piece_jointe is None:
            blocs.append(f"Pièce jointe id {identifiant} : {_PIECE_JOINTE_INTROUVABLE}")
            continue
        if piece_jointe not in relues:
            relues.append(piece_jointe)
        if not besoin:
            blocs.append(
                f"Pièce jointe id {piece_jointe.id} « {piece_jointe.nom_fichier} » :\n"
                f"{piece_jointe.contenu_extrait or ''}"
            )
    if besoin:
        return _relire_pour_un_besoin(besoin, blocs, relues, contexte)
    # L'échange d'inspecteur ne référence qu'une pièce jointe (spec 1.3.0) :
    # la première relue.
    return ResultatOutil("\n\n".join(blocs), relues[0].id if relues else None)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
