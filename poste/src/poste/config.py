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
# Résultat de la dernière vérification de mise à jour, écrit par le Lanceur à
# chaque lancement (ADR-0022) : bandeau de l'application, « À propos ».
FICHIER_ETAT_MISE_A_JOUR = FICHIER_CONFIGURATION.parent / "mise-a-jour.json"
# Journaux du Lanceur et du backend, en mode paquet seulement.
DOSSIER_JOURNAUX = FICHIER_CONFIGURATION.parent / "journaux"
# Donnés par le Lanceur à son backend (lanceur/src/sidecar.rs) : version du
# poste et exe à relancer pour « Vérifier les mises à jour maintenant ».
VERSION_POSTE = os.environ.get("BBASS_VERSION") or None
LANCEUR = os.environ.get("BBASS_LANCEUR") or None


# Adresse prod par défaut du Serveur BBASS (spec 1.6.2, point 10), même
# constante que le Lanceur (lanceur/coeur/src/configuration.rs). Vide tant
# qu'elle n'est pas connue : le premier lancement ouvre alors la Configuration.
ADRESSE_PROD = ""
PORT_PAR_DEFAUT = 8000


def lire_serveur_bbass() -> tuple[str, int] | None:
    """Hôte et port du fichier de configuration, `None` s'il est absent, illisible ou sans hôte."""
    try:
        serveur = json.loads(FICHIER_CONFIGURATION.read_text(encoding="utf-8"))["serveur_bbass"]
        hote, port = str(serveur["hote"]).strip(), int(serveur["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (hote, port) if hote else None


def adresse_serveur_bbass() -> str:
    """Adresse du Serveur BBASS, relue à chaque appel en mode paquet : la
    Configuration (menu « … ») vaut sans redémarrer ni réinstaller."""
    if not EN_MODE_PAQUET:
        return VM_CENTRALE_BASE_URL
    serveur = lire_serveur_bbass()
    return f"http://{serveur[0]}:{serveur[1]}" if serveur else ADRESSE_PROD


if not EN_MODE_PAQUET:
    load_dotenv()

POSTE_HOST = os.environ.get("POSTE_HOST", "127.0.0.1")
POSTE_PORT = int(os.environ.get("POSTE_PORT", "8100"))
# Dev seulement (`.env` du clone) ; en mode paquet, adresse_serveur_bbass().
VM_CENTRALE_BASE_URL = os.environ.get("VM_CENTRALE_BASE_URL", "http://localhost:8000").rstrip("/")
# Doit couvrir le pire tour de la VM centrale : sinon le poste abandonne,
# affiche une erreur, et la VM enregistre quand même le tour (un nouvel essai
# le doublerait, coût compté deux fois). Depuis la 1.4.0 (recherche web), un
# message enchaîne jusqu'à deux tours avec outil, chacun chat (30 s,
# MISTRAL_HTTP_TIMEOUT) + SearXNG (10 s) + pages (10 s) + extraction (30 s),
# puis une réponse finale (30 s) : 190 s, d'où 200 s.
POSTE_HTTP_TIMEOUT = float(os.environ.get("POSTE_HTTP_TIMEOUT", "200"))
