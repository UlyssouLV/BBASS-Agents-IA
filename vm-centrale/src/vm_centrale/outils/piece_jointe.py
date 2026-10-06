from vm_centrale.models import PieceJointe
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil

_NOM = "obtenir_contenu_piece_jointe"
_PIECE_JOINTE_INTROUVABLE = "Pièce jointe introuvable."


def _pieces_jointes_hors_fenetre(contexte: ContexteTour) -> list[PieceJointe]:
    requete = contexte.db.query(PieceJointe).filter(
        PieceJointe.conversation_id == contexte.conversation_id,
        PieceJointe.message_id.isnot(None),
    )
    if contexte.ids_fenetre:
        requete = requete.filter(~PieceJointe.message_id.in_(contexte.ids_fenetre))
    return requete.all()


# Éligible seulement si la conversation a une pièce jointe déjà liée à un
# message sorti de la fenêtre des derniers messages (spec 1.1.2) : l'IA peut
# alors la redemander explicitement plutôt que de répondre sans son contenu
# complet.
def _declarer(contexte: ContexteTour) -> dict | None:
    pieces_jointes_hors_fenetre = _pieces_jointes_hors_fenetre(contexte)
    if not pieces_jointes_hors_fenetre:
        return None
    # La description est générée à chaque appel à partir des pièces jointes
    # réellement éligibles de la conversation courante (jamais une liste
    # statique figée dans le schéma) : sans le nom de fichier en face de
    # chaque id, le modèle doit deviner quel entier correspond à quel
    # document (ticket #50 — cause du mauvais choix de pièce jointe observé
    # dans l'essai du 2026-09-17).
    liste_pieces_jointes = "\n".join(
        f"- id {piece_jointe.id} : {piece_jointe.nom_fichier}"
        for piece_jointe in pieces_jointes_hors_fenetre
    )
    return {
        "type": "function",
        "function": {
            "name": _NOM,
            "description": (
                "Récupère le contenu complet d'une pièce jointe de cette "
                "conversation dont le message n'est plus dans les derniers "
                "messages. Pièces jointes éligibles (id — nom de fichier) "
                f":\n{liste_pieces_jointes}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "piece_jointe_id": {
                        "type": "integer",
                        "description": (
                            "Identifiant de la pièce jointe à récupérer, "
                            "parmi ceux listés ci-dessus."
                        ),
                    }
                },
                "required": ["piece_jointe_id"],
            },
        },
    }


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    piece_jointe = contexte.db.get(PieceJointe, arguments.get("piece_jointe_id"))
    if piece_jointe is None or piece_jointe.conversation_id != contexte.conversation_id:
        # Ne devrait pas arriver (l'IA ne voit que des piece_jointe_id réels
        # dans son propre contexte), mais jamais de 500 sur une divergence :
        # un contenu explicatif pour l'outil plutôt qu'une pièce jointe
        # rattachée à une autre conversation, même confidentialité que
        # _recuperer_piece_jointe_du_compte (routers/conversations.py).
        return ResultatOutil(_PIECE_JOINTE_INTROUVABLE)
    return ResultatOutil(piece_jointe.contenu_extrait or "", piece_jointe.id)


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
