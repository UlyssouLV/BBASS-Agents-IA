from pydantic import BaseModel, Field


class ConnexionRequest(BaseModel):
    identifiant: str
    mot_de_passe: str


class ConnexionResponse(BaseModel):
    identifiant: str
    prenom: str
    nom: str
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool
    avertissement: str | None = None


class CompteResponse(BaseModel):
    identifiant: str
    prenom: str
    nom: str
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    reponse: str
