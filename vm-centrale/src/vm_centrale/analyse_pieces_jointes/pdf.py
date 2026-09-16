from vm_centrale.analyse_pieces_jointes.resultat import ResultatAnalyse
from vm_centrale.mistral_client import MistralClient

_TYPE_MIME = "application/pdf"


def analyser(fichier: bytes, client: MistralClient) -> ResultatAnalyse:
    contenu_extrait = client.ocr(fichier, type_mime=_TYPE_MIME)
    return ResultatAnalyse(
        contenu_extrait=contenu_extrait, echec_analyse=not contenu_extrait.strip()
    )
