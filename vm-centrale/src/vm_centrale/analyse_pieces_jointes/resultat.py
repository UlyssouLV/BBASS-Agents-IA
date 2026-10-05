from dataclasses import dataclass, field

from vm_centrale.mistral_client import Usage


@dataclass(frozen=True)
class InfoConsommationAnalyse:
    # "ocr" ou "vision" (spec V1.1.3) — les deux seuls types d'appel Mistral
    # de ce module (word/excel n'en produisent jamais, extraction locale).
    type_appel: str
    modele: str
    usage: Usage | None = None
    pages_traitees: int | None = None
    # Payload exact envoyé et réponse brute reçue par ce même appel Mistral
    # (spec 1.3.0, inspecteur des échanges) — repris tel quel de
    # ReponseOcr/ReponseChat, jamais reconstruit.
    payload_envoye: dict = field(default_factory=dict)
    reponse_brute: dict = field(default_factory=dict)


@dataclass
class ResultatAnalyse:
    contenu_extrait: str
    # Distinct d'une panne de l'appel Mistral (qui remonte comme une
    # exception, traitée en 502 par l'appelant) : signale une analyse qui a
    # eu lieu mais n'a rien produit d'exploitable (spec 1.1.2).
    echec_analyse: bool
    # None pour word/excel (extraction locale, aucun appel Mistral) —
    # renseigné pour pdf (ocr) et image (vision), spec V1.1.3.
    consommation: InfoConsommationAnalyse | None = None
