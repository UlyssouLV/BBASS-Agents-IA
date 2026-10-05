from vm_centrale.analyse_pieces_jointes.resultat import InfoConsommationAnalyse, ResultatAnalyse
from vm_centrale.config import MODELE_OCR
from vm_centrale.mistral_client import MistralClient


def analyser(fichier: bytes, type_mime: str, client: MistralClient) -> ResultatAnalyse:
    reponse = client.ocr(fichier, type_mime=type_mime)
    return ResultatAnalyse(
        contenu_extrait=reponse.contenu,
        echec_analyse=not reponse.contenu.strip(),
        consommation=InfoConsommationAnalyse(
            type_appel="ocr",
            modele=MODELE_OCR,
            pages_traitees=reponse.pages_processed,
            payload_envoye=reponse.payload_envoye,
            reponse_brute=reponse.reponse_brute,
        ),
    )
