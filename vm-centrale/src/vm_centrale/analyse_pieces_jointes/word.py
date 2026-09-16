from io import BytesIO

from docx import Document

from vm_centrale.analyse_pieces_jointes.resultat import ResultatAnalyse
from vm_centrale.mistral_client import MistralClient


def analyser(fichier: bytes, client: MistralClient) -> ResultatAnalyse:
    # Extraction locale (python-docx), pas d'appel Mistral : ni le fichier ni
    # son contenu brut ne quittent la VM centrale avant l'appel de chat, qui
    # ne reçoit que le texte déjà extrait (spec 1.1.2). `client` non utilisé
    # ici, gardé pour la signature uniforme des sous-modules (voir
    # analyse_pieces_jointes.analyser).
    document = Document(BytesIO(fichier))
    contenu_extrait = "\n".join(paragraphe.text for paragraphe in document.paragraphs)
    return ResultatAnalyse(
        contenu_extrait=contenu_extrait, echec_analyse=not contenu_extrait.strip()
    )
