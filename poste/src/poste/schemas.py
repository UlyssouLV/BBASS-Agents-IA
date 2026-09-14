from pydantic import BaseModel


class ConnexionRequest(BaseModel):
    identifiant: str
    mot_de_passe: str


class ConnexionResponse(BaseModel):
    identifiant: str


class CompteResponse(BaseModel):
    identifiant: str
