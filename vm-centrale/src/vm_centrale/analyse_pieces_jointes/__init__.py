from vm_centrale.analyse_pieces_jointes import excel, image, pdf, word
from vm_centrale.analyse_pieces_jointes.resultat import ResultatAnalyse
from vm_centrale.mistral_client import MistralClient

_TYPE_MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_TYPE_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Formats raster standards (spec 1.1.2 ne les énumère pas explicitement) :
# les quatre types les plus courants côté vision Mistral, pas de format CAO
# ni d'animation multi-frame à interpréter (hors périmètre de ce ticket).
_TYPE_MIME_JPEG = "image/jpeg"
_TYPE_MIME_PNG = "image/png"
_TYPE_MIME_WEBP = "image/webp"
_TYPE_MIME_GIF = "image/gif"

# Un sous-module par format (spec 1.1.2). Point d'entrée unique pensé comme
# premier utilitaire réutilisable par les futurs Agents IA par pôle
# (1.3.0+), pas comme logique interne au routeur conversations.py.
_EXTRACTEURS_PAR_TYPE = {
    "application/pdf": pdf.analyser,
    _TYPE_MIME_DOCX: word.analyser,
    _TYPE_MIME_XLSX: excel.analyser,
    _TYPE_MIME_JPEG: image.analyser,
    _TYPE_MIME_PNG: image.analyser,
    _TYPE_MIME_WEBP: image.analyser,
    _TYPE_MIME_GIF: image.analyser,
}

TYPES_SUPPORTES = frozenset(_EXTRACTEURS_PAR_TYPE)


def analyser(fichier: bytes, type_mime: str, client: MistralClient) -> ResultatAnalyse:
    extracteur = _EXTRACTEURS_PAR_TYPE[type_mime]
    return extracteur(fichier, type_mime, client)
