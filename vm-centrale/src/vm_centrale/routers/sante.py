from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from vm_centrale.config import get_version
from vm_centrale.database import get_db

# Santé de la VM (spec 1.6.1, ADR-0021), sans authentification : lue par la
# CI (build-image-vm) et par la mise à jour, qui remet les images précédentes
# si elle ne répond pas 200. Seule la base est vérifiée : Mistral, Moduléo et
# SearXNG en panne laissent la VM utile.
router = APIRouter()


@router.get("/sante")
def sante(db: Session = Depends(get_db)) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"statut": "base injoignable", "version": get_version()})
    return JSONResponse(content={"statut": "ok", "version": get_version()})
