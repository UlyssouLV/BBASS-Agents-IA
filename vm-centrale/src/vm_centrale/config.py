import os
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

VM_CENTRALE_HOST = os.environ.get("VM_CENTRALE_HOST", "0.0.0.0")
VM_CENTRALE_PORT = int(os.environ.get("VM_CENTRALE_PORT", "8000"))
DATABASE_URL = os.environ.get("VM_CENTRALE_DATABASE_URL", "sqlite:///./vm_centrale.db")
# Racine du stockage fichier des pièces jointes (spec V1.1.2), même
# convention que DATABASE_URL ci-dessus.
PIECES_JOINTES_DIR = os.environ.get("VM_CENTRALE_PIECES_JOINTES_DIR", "./pieces_jointes")
# Doit rester <= au timeout HTTP du poste (POSTE_HTTP_TIMEOUT, 35s par
# défaut) : voir poste/src/poste/config.py.
MISTRAL_HTTP_TIMEOUT = float(os.environ.get("MISTRAL_HTTP_TIMEOUT", "30"))
# SearXNG auto-hébergé du docker-compose.yml (spec 1.4.0, ADR-0013), publié
# sur localhost seulement.
SEARXNG_URL = os.environ.get("VM_CENTRALE_SEARXNG_URL", "http://localhost:8888")
SEARXNG_HTTP_TIMEOUT = float(os.environ.get("SEARXNG_HTTP_TIMEOUT", "10"))

# Tags de modèle centralisés par fonction (spec V1.1.2), pas par valeur : tout
# code appelant Mistral référence l'une de ces constantes plutôt qu'une
# chaîne en dur, pour qu'un changement de modèle futur se fasse à un seul
# endroit. Forme de requête/réponse différente entre les deux (chat
# completions vs. OCR), pas un simple changement de paramètre.
MODELE_CHAT = "mistral-small-latest"
MODELE_OCR = "mistral-ocr-latest"

# Tarifs par modèle (spec V1.1.3), en dur et datés par commentaire (Mistral
# n'expose aucune API de tarification programmable — voir
# docs/suivi-avancement/recherche-v1.1.3-usage-tarification-mistral.md).
# Relevés le 2026-09-17 sur mistral.ai/pricing/api (à revérifier avant
# intégration, correspondance alias MODELE_CHAT/MODELE_OCR avec les noms
# commerciaux non confirmée par une citation primaire verbatim) : Mistral
# Small ≈ 0,15 $/M tokens entrée, 0,60 $/M tokens sortie ; OCR ≈ 4 $/1000
# pages.
_PRIX_USD_PAR_TOKEN_ENTREE = {MODELE_CHAT: Decimal("0.15") / Decimal(1_000_000)}
_PRIX_USD_PAR_TOKEN_SORTIE = {MODELE_CHAT: Decimal("0.60") / Decimal(1_000_000)}
_PRIX_USD_PAR_PAGE = {MODELE_OCR: Decimal(4) / Decimal(1000)}

# Seul "ocr" est facturé à la page (pages_traitees, pas de tokens) ; tout le
# reste (chat/titrage/resume_et_profil/vision) est facturé au token (spec
# V1.1.3) — une ligne Consommation ne porte jamais les deux jeux de champs.
_TYPES_APPEL_PAGE_BASED = frozenset({"ocr"})


def calculer_cout(
    type_appel: str,
    modele: str,
    tokens_entree: int | None,
    tokens_sortie: int | None,
    pages_traitees: int | None,
) -> Decimal:
    if type_appel in _TYPES_APPEL_PAGE_BASED:
        return _PRIX_USD_PAR_PAGE[modele] * Decimal(pages_traitees or 0)
    return (
        _PRIX_USD_PAR_TOKEN_ENTREE[modele] * Decimal(tokens_entree or 0)
        + _PRIX_USD_PAR_TOKEN_SORTIE[modele] * Decimal(tokens_sortie or 0)
    )


def get_mistral_api_key() -> str:
    # Lu à l'appel (pas mis en cache dans une constante de module) : une clé
    # manquante doit lever au moment de l'appel Mistral, dans le try/except
    # du endpoint de relais, jamais avant.
    return os.environ["MISTRAL_API_KEY"]


def get_vm_admin_key() -> str | None:
    # None (jamais une levée d'exception) quand la clé n'est pas configurée :
    # l'endpoint de révocation forcée doit alors refuser toute requête (401),
    # jamais planter. Une valeur vide (VM_ADMIN_KEY= dans .env) compte comme
    # non configurée, sinon une clé vide fournie par l'appelant la validerait.
    return os.environ.get("VM_ADMIN_KEY") or None
