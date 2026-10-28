import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Mode paquet (ADR-0022) : backend figé par PyInstaller et démarré par le
# Lanceur. L'adresse du Serveur BBASS vient alors du fichier de configuration
# de l'utilisateur, partagé avec le Lanceur ; en dev, du `.env` du clone.
EN_MODE_PAQUET = bool(getattr(sys, "frozen", False))

# Format du fichier de configuration (lu aussi par le Lanceur) :
# {"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}}
FICHIER_CONFIGURATION = Path(os.environ.get("LOCALAPPDATA", "")) / "BBASS" / "configuration.json"


def _adresse_du_fichier_de_configuration() -> str | None:
    try:
        serveur = json.loads(FICHIER_CONFIGURATION.read_text(encoding="utf-8"))["serveur_bbass"]
        hote, port = str(serveur["hote"]).strip(), int(serveur["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return f"http://{hote}:{port}" if hote else None


if not EN_MODE_PAQUET:
    load_dotenv()

POSTE_HOST = os.environ.get("POSTE_HOST", "127.0.0.1")
POSTE_PORT = int(os.environ.get("POSTE_PORT", "8100"))
if EN_MODE_PAQUET:
    VM_CENTRALE_BASE_URL = _adresse_du_fichier_de_configuration() or "http://localhost:8000"
else:
    VM_CENTRALE_BASE_URL = os.environ.get("VM_CENTRALE_BASE_URL", "http://localhost:8000").rstrip("/")
# Doit couvrir le pire tour de la VM centrale : sinon le poste abandonne,
# affiche une erreur, et la VM enregistre quand même le tour (un nouvel essai
# le doublerait, coût compté deux fois). Depuis la 1.4.0 (recherche web), un
# message enchaîne jusqu'à deux tours avec outil, chacun chat (30 s,
# MISTRAL_HTTP_TIMEOUT) + SearXNG (10 s) + pages (10 s) + extraction (30 s),
# puis une réponse finale (30 s) : 190 s, d'où 200 s.
POSTE_HTTP_TIMEOUT = float(os.environ.get("POSTE_HTTP_TIMEOUT", "200"))
