from vm_centrale.analyse_pieces_jointes import pdf
from vm_centrale.analyse_pieces_jointes.resultat import ResultatAnalyse
from vm_centrale.mistral_client import MistralClient

# Un sous-module par format (spec 1.1.2) : seul le PDF est routé pour ce
# ticket (Word/Excel/image, tickets suivants). Point d'entrée unique pensé
# comme premier utilitaire réutilisable par les futurs Agents IA par pôle
# (1.3.0+), pas comme logique interne au routeur conversations.py.
_EXTRACTEURS_PAR_TYPE = {
    "application/pdf": pdf.analyser,
}

TYPES_SUPPORTES = frozenset(_EXTRACTEURS_PAR_TYPE)


def analyser(fichier: bytes, type_mime: str, client: MistralClient) -> ResultatAnalyse:
    extracteur = _EXTRACTEURS_PAR_TYPE[type_mime]
    return extracteur(fichier, client)
