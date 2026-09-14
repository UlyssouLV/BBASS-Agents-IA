import os

from dotenv import load_dotenv

load_dotenv()

POSTE_HOST = os.environ.get("POSTE_HOST", "127.0.0.1")
POSTE_PORT = int(os.environ.get("POSTE_PORT", "8100"))
VM_CENTRALE_BASE_URL = os.environ.get("VM_CENTRALE_BASE_URL", "http://localhost:8000").rstrip("/")
# Doit rester >= au timeout Mistral de la VM centrale (MISTRAL_HTTP_TIMEOUT,
# 30s par défaut) : sinon le poste abandonne avant que la VM n'ait fini
# d'attendre Mistral et affiche une erreur alors qu'une réponse allait arriver.
POSTE_HTTP_TIMEOUT = float(os.environ.get("POSTE_HTTP_TIMEOUT", "35"))
