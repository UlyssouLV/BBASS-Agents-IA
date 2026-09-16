from vm_centrale.analyse_pieces_jointes import excel, pdf, word
from vm_centrale.analyse_pieces_jointes.resultat import ResultatAnalyse
from vm_centrale.mistral_client import MistralClient

_TYPE_MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_TYPE_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Un sous-module par format (spec 1.1.2) : image, ticket suivant. Point
# d'entrée unique pensé comme premier utilitaire réutilisable par les futurs
# Agents IA par pôle (1.3.0+), pas comme logique interne au routeur
# conversations.py.
_EXTRACTEURS_PAR_TYPE = {
    "application/pdf": pdf.analyser,
    _TYPE_MIME_DOCX: word.analyser,
    _TYPE_MIME_XLSX: excel.analyser,
}

TYPES_SUPPORTES = frozenset(_EXTRACTEURS_PAR_TYPE)


def analyser(fichier: bytes, type_mime: str, client: MistralClient) -> ResultatAnalyse:
    extracteur = _EXTRACTEURS_PAR_TYPE[type_mime]
    return extracteur(fichier, client)
