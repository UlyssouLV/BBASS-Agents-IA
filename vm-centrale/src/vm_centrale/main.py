from contextlib import asynccontextmanager

from fastapi import FastAPI

from vm_centrale.config import VM_CENTRALE_HOST, VM_CENTRALE_PORT
from vm_centrale.database import init_db
from vm_centrale.routers.auth import router as auth_router
from vm_centrale.routers.comptes import router as comptes_router
from vm_centrale.routers.consommation import router as consommation_router
from vm_centrale.routers.conversations import router as conversations_router
from vm_centrale.routers.inspecteur import router as inspecteur_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
