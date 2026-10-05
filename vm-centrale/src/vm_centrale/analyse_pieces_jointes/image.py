import base64
import json

from vm_centrale.analyse_pieces_jointes.resultat import InfoConsommationAnalyse, ResultatAnalyse
from vm_centrale.config import MODELE_CHAT
from vm_centrale.mistral_client import ErreurAppelMistral, MistralClient

# Seul format sans alternative locale (spec 1.1.2, ADR-0009) : le fichier est
# transmis à l'appel vision Mistral (chat completions, MODELE_CHAT — pas de
# modèle dédié comme pour l'OCR), structurellement hors Zero Data Retention.
_PROMPT = (
    "Cette image a été jointe par un collaborateur à une conversation de "
    "travail. Transcris tout le texte visible et décris tout contenu "
    "exploitable (tableau, schéma, graphique, photo de terrain...), en "
    "français, dans contenu_extrait. Si rien d'exploitable n'apparaît "
    "(image illisible, vide, corrompue ou sans rapport), renvoie "
    "echec_analyse à true et explique brièvement pourquoi dans "
    "contenu_extrait plutôt que de le laisser vide."
)

# Sortie structurée (comme le résumé glissant, voir
# vm_centrale.routers.conversations) plutôt qu'un heuristique sur une chaîne
# vide (contrairement à pdf.py/word.py/excel.py) : seul le modèle peut juger
# si l'image contient quelque chose d'exploitable, et l'échec doit rester une
# analyse réussie (jamais une erreur HTTP, spec 1.1.2).
_SCHEMA_ANALYSE_IMAGE = {
    "type": "json_schema",
    "json_schema": {
        "name": "analyse_image",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "contenu_extrait": {"type": "string"},
                "echec_analyse": {"type": "boolean"},
            },
            "required": ["contenu_extrait", "echec_analyse"],
            "additionalProperties": False,
        },
    },
}


def analyser(fichier: bytes, type_mime: str, client: MistralClient) -> ResultatAnalyse:
    image_url = f"data:{type_mime};base64,{base64.b64encode(fichier).decode('ascii')}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url", "image_url": image_url},
            ],
        }
    ]
    reponse = client.chat(messages, response_format=_SCHEMA_ANALYSE_IMAGE)
    try:
        donnees = json.loads(reponse.contenu)
        contenu_extrait = donnees["contenu_extrait"]
        echec_analyse = donnees["echec_analyse"]
    except (json.JSONDecodeError, KeyError, TypeError) as erreur:
        # Réponse reçue mais inexploitable : remontée comme un échec d'appel
        # portant le payload envoyé et la réponse brute, pour que l'échange
        # en échec reste débogable dans l'inspecteur (spec 1.3.0).
        raise ErreurAppelMistral(
            f"Réponse vision de Mistral invalide : {erreur}",
            payload_envoye=reponse.payload_envoye,
            reponse_brute=reponse.reponse_brute,
        ) from erreur
    return ResultatAnalyse(
        contenu_extrait=contenu_extrait,
        echec_analyse=echec_analyse,
        consommation=InfoConsommationAnalyse(
            type_appel="vision",
            modele=MODELE_CHAT,
            usage=reponse.usage,
            payload_envoye=reponse.payload_envoye,
            reponse_brute=reponse.reponse_brute,
        ),
    )
