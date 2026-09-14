from pydantic import BaseModel, Field


class ConnexionRequest(BaseModel):
    identifiant: str
    mot_de_passe: str


class ConnexionResponse(BaseModel):
    identifiant: str


class CompteResponse(BaseModel):
    identifiant: str


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    reponse: str
