from vm_centrale.models import PieceJointe
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil

_NOM = "relire_pieces_jointes"
_PIECE_JOINTE_INTROUVABLE = "Pièce jointe introuvable."


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
                "Relit le contenu complet d'une ou plusieurs pièces jointes "
                "envoyées plus tôt dans cette conversation. Pièces jointes "
                f"éligibles (id — nom de fichier) :\n{liste_pieces_jointes}"
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
                    }
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


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    identifiants = arguments.get("piece_jointe_ids")
    if not isinstance(identifiants, list) or not identifiants:
        return ResultatOutil(_PIECE_JOINTE_INTROUVABLE)
    # Un contenu par pièce jointe, chacun précédé de son nom de fichier. Un id
    # inconnu ou d'une autre conversation : « Pièce jointe introuvable. » pour
    # lui seul, jamais une erreur HTTP ; les autres sont relues.
    blocs: list[str] = []
    piece_jointe_relue: int | None = None
    for identifiant in identifiants:
        piece_jointe = _piece_jointe_de_la_conversation(identifiant, contexte)
        if piece_jointe is None:
            blocs.append(f"Pièce jointe id {identifiant} : {_PIECE_JOINTE_INTROUVABLE}")
            continue
        blocs.append(
            f"Pièce jointe id {piece_jointe.id} « {piece_jointe.nom_fichier} » :\n"
            f"{piece_jointe.contenu_extrait or ''}"
        )
        piece_jointe_relue = piece_jointe_relue or piece_jointe.id
    # L'échange d'inspecteur ne référence qu'une pièce jointe (spec 1.3.0) :
    # la première relue.
    return ResultatOutil("\n\n".join(blocs), piece_jointe_relue)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
