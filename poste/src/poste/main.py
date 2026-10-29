from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from poste.config import DOSSIER_JOURNAUX, EN_MODE_PAQUET, POSTE_HOST, POSTE_PORT
from poste.journaux import configurer_journaux, journal_des_requetes
from poste.routers.comptes import router as comptes_router
from poste.routers.configuration import router as configuration_router
from poste.routers.consommation import router as consommation_router
from poste.routers.conversations import router as conversations_router
from poste.routers.inspecteur import router as inspecteur_router
from poste.routers.mise_a_jour import router as mise_a_jour_router
from poste.routers.moduleo import router as moduleo_router
from poste.routers.profil_travail import router as profil_travail_router
from poste.routers.session import router as session_router
from poste.session import get_session_store, verifier_session_au_demarrage
from poste.vm_centrale_client import get_vm_centrale_client

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Résout les dependency_overrides éventuels (tests) plutôt que les
    # factories réelles directement, pour rester testable comme le reste de
    # l'app malgré l'absence de contexte de requête au démarrage.
    session = app.dependency_overrides.get(get_session_store, get_session_store)()
    client = app.dependency_overrides.get(get_vm_centrale_client, get_vm_centrale_client)()
    verifier_session_au_demarrage(session, client)
    yield


app = FastAPI(title="Poste", lifespan=lifespan)
app.include_router(session_router)
app.include_router(conversations_router)
app.include_router(profil_travail_router)
app.include_router(consommation_router)
app.include_router(comptes_router)
app.include_router(inspecteur_router)
app.include_router(moduleo_router)
app.include_router(mise_a_jour_router)
app.include_router(configuration_router)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


_METHODES_SURES = {"GET", "HEAD", "OPTIONS"}
_HOTES_LOCAUX = {"127.0.0.1", "localhost"}


def _venue_d_un_autre_site(request: Request) -> bool:
    # Une page d'un autre site peut envoyer un POST sans corps sans demande CORS
    # préalable (« Vérifier les mises à jour », « Ouvrir le dossier ») : le
    # navigateur le signale par Sec-Fetch-Site, ou à défaut par Origin. Sans ces
    # en-têtes (outil en ligne de commande, tests), la requête n'est pas d'une page.
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site not in {"same-origin", "none"}
    origine = request.headers.get("origin")
    return origine is not None and urlsplit(origine).hostname not in _HOTES_LOCAUX


# Avant journaliser_la_requete, qui l'enveloppe : un refus est journalisé.
@app.middleware("http")
async def refuser_les_autres_sites(request: Request, call_next):
    if request.method not in _METHODES_SURES and _venue_d_un_autre_site(request):
        return JSONResponse(status_code=403, content={"detail": "Requête refusée : elle ne vient pas de BBASS."})
    return await call_next(request)


@app.middleware("http")
async def journaliser_la_requete(request: Request, call_next):
    # Méthode, chemin et statut seulement : ni chaîne de requête, ni en-tête,
    # ni corps (mot de passe, jeton).
    reponse = await call_next(request)
    journal_des_requetes.info("%s %s %d", request.method, request.url.path, reponse.status_code)
    return reponse


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


# Mode développeur (spec 1.3.0) : point d'entrée séparé ouvert dans un nouvel
# onglet par Ctrl+Maj+D, servi par le même build que la racine — main.tsx
# choisit l'écran selon le chemin. Route exacte, distincte des routes API
# /inspecteur/* (routers/inspecteur.py).
@app.get("/inspecteur")
def inspecteur() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


def run() -> None:
    import uvicorn

    if EN_MODE_PAQUET:
        # Sortie standard nulle sous le Lanceur : uvicorn passe par nos
        # journaux rotatifs ; son access log doublerait journaliser_la_requete.
        configurer_journaux(DOSSIER_JOURNAUX)
        uvicorn.run(app, host=POSTE_HOST, port=POSTE_PORT, log_config=None, access_log=False)
    else:
        uvicorn.run(app, host=POSTE_HOST, port=POSTE_PORT)


if __name__ == "__main__":
    run()
