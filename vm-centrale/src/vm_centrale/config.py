import os
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from dotenv import load_dotenv

from vm_centrale.secrets_chiffres import SecretIndechiffrable, dechiffrer, lire_cle_maitre

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
# API Moduléo du cabinet (spec 1.5.0, ADR-0017) : changer de serveur est une
# ligne de .env. Les routes de vm_centrale/moduleo/routes.py s'ajoutent à
# cette base ; la doc du serveur est sous <MODULEO_URL>/documentation.
MODULEO_URL = os.environ.get("MODULEO_URL", "https://mwa-bbass.kipaware.fr/api")
# Délai d'une lecture Moduléo : au-delà, Moduléo est tenu pour indisponible
# (panne), sans nouvelle tentative.
MODULEO_HTTP_TIMEOUT = 10.0
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


class CleMistralInutilisable(RuntimeError):
    # Le message nomme la variable en cause, jamais une valeur (spec 1.5.1).
    pass


def get_mistral_api_key() -> str:
    # Chiffrée (Fernet, spec 1.5.1, ADR-0018) avec la même clé maître que
    # les secrets Moduléo ; MISTRAL_API_KEY en clair n'est plus lue. Le
    # démarrage de la VM l'appelle une fois (main.py) : sans clé
    # utilisable, la VM refuse de démarrer. Lu à l'appel ensuite, comme
    # get_config_moduleo_chiffree.
    valeur_chiffree = os.environ.get("MISTRAL_API_KEY_CHIFFREE") or None
    fichier_cle_maitre = os.environ.get("VM_CLE_MAITRE_FICHIER") or None
    if valeur_chiffree is None:
        raise CleMistralInutilisable("MISTRAL_API_KEY_CHIFFREE manquant dans .env.")
    if fichier_cle_maitre is None:
        raise CleMistralInutilisable("VM_CLE_MAITRE_FICHIER manquant dans .env.")
    try:
        cle_maitre = lire_cle_maitre(fichier_cle_maitre)
    except OSError as erreur:
        raise CleMistralInutilisable(
            f"Clé maître de VM_CLE_MAITRE_FICHIER illisible ({type(erreur).__name__})."
        ) from None
    try:
        return dechiffrer(valeur_chiffree, cle_maitre)
    except SecretIndechiffrable:
        raise CleMistralInutilisable(
            "MISTRAL_API_KEY_CHIFFREE ne se déchiffre pas avec la clé maître de VM_CLE_MAITRE_FICHIER."
        ) from None


def get_vm_admin_key() -> str | None:
    # None (jamais une levée d'exception) quand la clé n'est pas configurée :
    # l'endpoint de révocation forcée doit alors refuser toute requête (401),
    # jamais planter. Une valeur vide (VM_ADMIN_KEY= dans .env) compte comme
    # non configurée, sinon une clé vide fournie par l'appelant la validerait.
    return os.environ.get("VM_ADMIN_KEY") or None


@dataclass(frozen=True)
class ConfigModuleoChiffree:
    # None quand la variable est absente ou vide.
    url: str | None
    api_key_chiffree: str | None
    security_code_chiffre: str | None
    fichier_cle_maitre: str | None


def get_config_moduleo_chiffree() -> ConfigModuleoChiffree:
    # Lu à l'appel : la clé d'API et le
    # SecurityCode sont chiffrés (Fernet, spec 1.5.0, ADR-0017) avec la clé
    # maître du fichier VM_CLE_MAITRE_FICHIER, hors du dépôt. Le
    # déchiffrement est dans vm_centrale/moduleo/configuration.py ;
    # scripts/chiffrer_secret.py produit les valeurs chiffrées.
    return ConfigModuleoChiffree(
        url=os.environ.get("MODULEO_URL", MODULEO_URL) or None,
        api_key_chiffree=os.environ.get("MODULEO_API_KEY_CHIFFREE") or None,
        security_code_chiffre=os.environ.get("MODULEO_SECURITY_CODE_CHIFFRE") or None,
        fichier_cle_maitre=os.environ.get("VM_CLE_MAITRE_FICHIER") or None,
    )
