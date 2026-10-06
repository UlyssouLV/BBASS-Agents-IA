import os

from dotenv import load_dotenv

load_dotenv()

POSTE_HOST = os.environ.get("POSTE_HOST", "127.0.0.1")
POSTE_PORT = int(os.environ.get("POSTE_PORT", "8100"))
VM_CENTRALE_BASE_URL = os.environ.get("VM_CENTRALE_BASE_URL", "http://localhost:8000").rstrip("/")
# Doit couvrir le pire tour de la VM centrale : sinon le poste abandonne,
# affiche une erreur, et la VM enregistre quand même le tour (un nouvel essai
# le doublerait, coût compté deux fois). Depuis la 1.4.0 (recherche web), un
# message enchaîne jusqu'à deux tours avec outil, chacun chat (30 s,
# MISTRAL_HTTP_TIMEOUT) + SearXNG (10 s) + pages (10 s) + extraction (30 s),
# puis une réponse finale (30 s) : 190 s, d'où 200 s.
POSTE_HTTP_TIMEOUT = float(os.environ.get("POSTE_HTTP_TIMEOUT", "200"))
