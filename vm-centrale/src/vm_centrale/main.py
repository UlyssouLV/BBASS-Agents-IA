from contextlib import asynccontextmanager

from fastapi import FastAPI

from vm_centrale.compte_tokens import charger_tokenizers
from vm_centrale.config import VM_CENTRALE_HOST, VM_CENTRALE_PORT, get_mistral_api_key
from vm_centrale.database import init_db
from vm_centrale.moduleo.configuration import config_moduleo
from vm_centrale.routers.auth import router as auth_router
from vm_centrale.routers.comptes import router as comptes_router
from vm_centrale.routers.consommation import router as consommation_router
from vm_centrale.routers.conversations import router as conversations_router
from vm_centrale.routers.inspecteur import router as inspecteur_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    charger_tokenizers()
    # Sans clé Mistral chiffrée utilisable, la VM refuse de démarrer (spec
    # 1.5.1) : lève CleMistralInutilisable, qui nomme la variable en cause.
    get_mistral_api_key()
    init_db()
    # Journalise au démarrage si Moduléo est configuré ; sans config
    # complète et déchiffrable, la VM démarre quand même (ADR-0017).
    config_moduleo()
    yield


app = FastAPI(title="VM centrale", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(comptes_router)
app.include_router(consommation_router)
app.include_router(conversations_router)
app.include_router(inspecteur_router)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=VM_CENTRALE_HOST, port=VM_CENTRALE_PORT)


if __name__ == "__main__":
    run()
