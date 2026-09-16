from dataclasses import dataclass


@dataclass
class ResultatAnalyse:
    contenu_extrait: str
    # Distinct d'une panne de l'appel Mistral (qui remonte comme une
    # exception, traitée en 502 par l'appelant) : signale une analyse qui a
    # eu lieu mais n'a rien produit d'exploitable (spec 1.1.2).
    echec_analyse: bool
