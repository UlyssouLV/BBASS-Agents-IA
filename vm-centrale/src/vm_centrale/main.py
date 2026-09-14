import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vm_centrale.database import init_db
from vm_centrale.routers.auth import router as auth_router
from vm_centrale.routers.relais import router as relais_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="VM centrale", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(relais_router)


def run() -> None:
    import uvicorn

    host = os.environ.get("VM_CENTRALE_HOST", "0.0.0.0")
    port = int(os.environ.get("VM_CENTRALE_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
