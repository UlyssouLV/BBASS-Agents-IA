from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from poste.config import POSTE_HOST, POSTE_PORT
from poste.routers.chat import router as chat_router
from poste.routers.comptes import router as comptes_router
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
app.include_router(chat_router)
app.include_router(comptes_router)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=POSTE_HOST, port=POSTE_PORT)


if __name__ == "__main__":
    run()
