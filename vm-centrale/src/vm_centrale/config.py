import os

from dotenv import load_dotenv

load_dotenv()

VM_CENTRALE_HOST = os.environ.get("VM_CENTRALE_HOST", "0.0.0.0")
VM_CENTRALE_PORT = int(os.environ.get("VM_CENTRALE_PORT", "8000"))
DATABASE_URL = os.environ.get("VM_CENTRALE_DATABASE_URL", "sqlite:///./vm_centrale.db")


def get_mistral_api_key() -> str:
    # Lu à l'appel (pas mis en cache dans une constante de module) : une clé
    # manquante doit lever au moment de l'appel Mistral, dans le try/except
    # du endpoint de relais, jamais avant.
    return os.environ["MISTRAL_API_KEY"]
