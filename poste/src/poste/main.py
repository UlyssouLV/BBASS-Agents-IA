from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from poste.config import POSTE_HOST, POSTE_PORT
from poste.routers.session import router as session_router

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Poste")
app.include_router(session_router)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=POSTE_HOST, port=POSTE_PORT)


if __name__ == "__main__":
    run()
