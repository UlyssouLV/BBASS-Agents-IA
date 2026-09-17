from vm_centrale.analyse_pieces_jointes.resultat import ResultatAnalyse
from vm_centrale.mistral_client import MistralClient


def analyser(fichier: bytes, type_mime: str, client: MistralClient) -> ResultatAnalyse:
    contenu_extrait = client.ocr(fichier, type_mime=type_mime)
    return ResultatAnalyse(
        contenu_extrait=contenu_extrait, echec_analyse=not contenu_extrait.strip()
    )
