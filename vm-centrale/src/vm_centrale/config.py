import os
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

VM_CENTRALE_HOST = os.environ.get("VM_CENTRALE_HOST", "0.0.0.0")
VM_CENTRALE_PORT = int(os.environ.get("VM_CENTRALE_PORT", "8000"))
DATABASE_URL = os.environ.get("VM_CENTRALE_DATABASE_URL", "sqlite:///./vm_centrale.db")
# Racine du stockage fichier des pièces jointes (spec V1.1.2), même
# convention que DATABASE_URL ci-dessus.
PIECES_JOINTES_DIR = os.environ.get("VM_CENTRALE_PIECES_JOINTES_DIR", "./pieces_jointes")
# Le timeout HTTP du poste (POSTE_HTTP_TIMEOUT, 200 s par défaut) couvre
# le pire tour qui en découle, recherche web comprise : voir
# poste/src/poste/config.py.
MISTRAL_HTTP_TIMEOUT = float(os.environ.get("MISTRAL_HTTP_TIMEOUT", "30"))
# SearXNG auto-hébergé du docker-compose.yml (spec 1.4.0, ADR-0013), publié
# sur localhost seulement.
SEARXNG_URL = os.environ.get("VM_CENTRALE_SEARXNG_URL", "http://localhost:8888")
SEARXNG_HTTP_TIMEOUT = float(os.environ.get("SEARXNG_HTTP_TIMEOUT", "10"))
# Délai par page trouvée par le moteur (spec 1.4.0, étape 2) : au-delà, la
# page est ignorée et son extrait de moteur reste.
PAGES_HTTP_TIMEOUT = float(os.environ.get("PAGES_HTTP_TIMEOUT", "10"))
# Validité d'une copie du cache commun des pages web (spec 1.4.3,
# ADR-0015) : au-delà, la copie est ignorée et la page retéléchargée.
VALIDITE_CACHE_PAGES = timedelta(hours=24)
# Longueur au-delà de laquelle la requête d'une recherche web ou le nom de
# fichier d'une pièce jointe relue est tronqué dans le statut du tour (spec
# 1.4.4, #165) : le statut tient sur une ligne du fil.
LONGUEUR_MAX_DETAIL_STATUT = 60
# Un tour qui attend le verrou de son compte republie son statut à cet
# intervalle : le poste borne le silence entre deux lectures du flux
# (POSTE_HTTP_TIMEOUT), et l'attente peut durer tout un autre tour.
INTERVALLE_STATUT_ATTENTE_SECONDES = 15.0

# Tags de modèle centralisés par fonction (spec V1.1.2), pas par valeur : tout
# code appelant Mistral référence l'une de ces constantes plutôt qu'une
# chaîne en dur, pour qu'un changement de modèle futur se fasse à un seul
# endroit. Forme de requête/réponse différente entre les deux (chat
# completions vs. OCR), pas un simple changement de paramètre.
# MODELE_CHAT est figé (spec 1.4.2) : l'alias `mistral-small-latest` pointait
# vers `mistral-small-2603` (Mistral Small 4) le 2026-10-06. Changer de
# modèle change aussi sa fiche ci-dessous, dans le même commit.
MODELE_CHAT = "mistral-small-2603"
MODELE_OCR = "mistral-ocr-latest"


@dataclass(frozen=True)
class FicheModele:
    # None quand le modèle n'a pas de fenêtre de chat (OCR).
    fenetre_tokens: int | None
    # Relatif à vm_centrale/tokenizers/ (voir son README) ; None quand rien
    # ne compte les tokens de ce modèle sur la VM.
    fichier_tokenizer: str | None
    prix_usd_par_token_entree: Decimal
    prix_usd_par_token_sortie: Decimal
    prix_usd_par_page: Decimal


# Une fiche par modèle (spec 1.4.2), liée au code et non au .env. Tarifs en
# dur et datés (Mistral n'expose aucune API de tarification programmable —
# voir docs/dev/recherches/recherche-v1.1.3-usage-tarification-mistral.md).
# - Chat : fenêtre de 262 144 tokens relevée sur GET /v1/models le
#   2026-10-06. Mistral Small 4 : 0,15 $/M tokens entrée, 0,60 $/M tokens
#   sortie, revérifié le 2026-10-06 (inchangé depuis le relevé du
#   2026-09-17 sur mistral.ai/pricing/api).
# - OCR : 4 $/1000 pages, relevé le 2026-09-17 sur mistral.ai/pricing/api.
FICHES_MODELES = {
    MODELE_CHAT: FicheModele(
        fenetre_tokens=262_144,
        fichier_tokenizer="mistral-small-2603/tekken.json",
        prix_usd_par_token_entree=Decimal("0.15") / Decimal(1_000_000),
        prix_usd_par_token_sortie=Decimal("0.60") / Decimal(1_000_000),
        prix_usd_par_page=Decimal(0),
    ),
    MODELE_OCR: FicheModele(
        fenetre_tokens=None,
        fichier_tokenizer=None,
        prix_usd_par_token_entree=Decimal(0),
        prix_usd_par_token_sortie=Decimal(0),
        prix_usd_par_page=Decimal(4) / Decimal(1000),
    ),
}

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
    fiche = FICHES_MODELES[modele]
    if type_appel in _TYPES_APPEL_PAGE_BASED:
        return fiche.prix_usd_par_page * Decimal(pages_traitees or 0)
    return (
        fiche.prix_usd_par_token_entree * Decimal(tokens_entree or 0)
        + fiche.prix_usd_par_token_sortie * Decimal(tokens_sortie or 0)
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
