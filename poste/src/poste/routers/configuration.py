import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

from poste import config
from poste.schemas import ConfigurationResponse, EtatServeurBbassResponse, ServeurBbassRequest

# Configuration du Serveur BBASS (spec 1.6.2, point 9) : menu « … » de l'écran
# de connexion et du profil, donc sans session. L'adresse est écrite dans le
# fichier de configuration partagé avec le Lanceur ; le chat la relit à chaque
# appel (config.adresse_serveur_bbass).
router = APIRouter()
journal = logging.getLogger("poste.configuration")

# Pastille d'état : un Serveur BBASS qui ne répond pas vite est dit injoignable.
_client_sante = httpx.Client(timeout=httpx.Timeout(5, connect=3))


def get_client_sante() -> httpx.Client:
    return _client_sante


def _ouvrir_dans_l_explorateur(dossier: Path) -> None:
    os.startfile(dossier)  # type: ignore[attr-defined]  # Windows seulement, comme le paquet.


def get_ouvreur_de_dossier() -> Callable[[Path], None]:
    return _ouvrir_dans_l_explorateur


def etat_a_l_adresse(client: httpx.Client, adresse: str) -> EtatServeurBbassResponse:
    # Vert seulement sur 200 : un 503 « base injoignable » ne permet pas de chatter.
    try:
        reponse = client.get(f"{adresse}/sante")
        version = reponse.json().get("version") if reponse.status_code == 200 else None
    except (httpx.HTTPError, ValueError, AttributeError):
        version = None
    if not isinstance(version, str):
        return EtatServeurBbassResponse(joignable=False, version=None)
    return EtatServeurBbassResponse(joignable=True, version=version)


def _configuration() -> ConfigurationResponse:
    if not config.EN_MODE_PAQUET:
        adresse = urlsplit(config.VM_CENTRALE_BASE_URL)
        return ConfigurationResponse(
            hote=adresse.hostname or "", port=adresse.port or config.PORT_PAR_DEFAUT, modifiable=False
        )
    serveur = config.lire_serveur_bbass()
    if serveur is None:
        adresse = urlsplit(config.ADRESSE_PROD)
        serveur = (adresse.hostname or "", adresse.port or config.PORT_PAR_DEFAUT)
    return ConfigurationResponse(hote=serveur[0], port=serveur[1], modifiable=True)


@router.get("/serveur-bbass/etat")
def etat_du_serveur_bbass(client: httpx.Client = Depends(get_client_sante)) -> EtatServeurBbassResponse:
    adresse = config.adresse_serveur_bbass()
    if not adresse:
        return EtatServeurBbassResponse(joignable=False, version=None)
    return etat_a_l_adresse(client, adresse)


@router.get("/configuration")
def lire_configuration() -> ConfigurationResponse:
    return _configuration()


@router.post("/configuration/test")
def tester_la_connexion(
    requete: ServeurBbassRequest, client: httpx.Client = Depends(get_client_sante)
) -> EtatServeurBbassResponse:
    return etat_a_l_adresse(client, config.adresse_http(requete.hote.strip(), requete.port))


@router.put("/configuration")
def enregistrer_la_configuration(requete: ServeurBbassRequest) -> ConfigurationResponse:
    if not config.EN_MODE_PAQUET:
        raise HTTPException(
            status_code=409,
            detail="En développement, l'adresse du Serveur BBASS se règle dans le fichier .env (VM_CENTRALE_BASE_URL).",
        )
    fichier = config.FICHIER_CONFIGURATION
    # Le choix « démarrer avec Windows » du Setup est gardé ; seuls les
    # réglages connus sont réécrits, pas le contenu lu tel quel.
    contenu: dict[str, object] = {"serveur_bbass": {"hote": requete.hote.strip(), "port": requete.port}}
    try:
        existant = json.loads(fichier.read_text(encoding="utf-8"))
        if isinstance(existant, dict) and isinstance(existant.get("demarrage_windows"), bool):
            contenu["demarrage_windows"] = existant["demarrage_windows"] is True
    except (OSError, ValueError):
        pass
    try:
        fichier.parent.mkdir(parents=True, exist_ok=True)
        provisoire = fichier.with_suffix(".json.tmp")
        provisoire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
        provisoire.replace(fichier)
        config.oublier_la_configuration_lue()
    except OSError as erreur:
        journal.warning("Configuration non enregistrée : %s", erreur)
        raise HTTPException(status_code=500, detail="La configuration n'a pas pu être enregistrée.") from erreur
    journal.info("Adresse du Serveur BBASS enregistrée : http://%s:%d", requete.hote.strip(), requete.port)
    return _configuration()


@router.post("/configuration/ouvrir-dossier", status_code=204)
def ouvrir_le_dossier_de_configuration(
    ouvrir: Callable[[Path], None] = Depends(get_ouvreur_de_dossier),
) -> Response:
    # Configuration et journaux : %LOCALAPPDATA%\BBASS.
    dossier = config.FICHIER_CONFIGURATION.parent
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        ouvrir(dossier)
    except OSError as erreur:
        journal.warning("Dossier de configuration non ouvert : %s", erreur)
        raise HTTPException(status_code=500, detail="Le dossier de configuration n'a pas pu être ouvert.") from erreur
    return Response(status_code=204)
