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

# Tags de modèle centralisés par fonction (spec V1.1.2), pas par valeur : tout
# code appelant Mistral référence l'une de ces constantes plutôt qu'une
# chaîne en dur, pour qu'un changement de modèle futur se fasse à un seul
# endroit. Forme de requête/réponse différente entre les deux (chat
# completions vs. OCR), pas un simple changement de paramètre.
MODELE_CHAT = "mistral-small-latest"
MODELE_OCR = "mistral-ocr-latest"


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
