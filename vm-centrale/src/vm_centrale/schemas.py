from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    identifiant: str
    mot_de_passe: str


class AuthResponse(BaseModel):
    prenom: str
    nom: str
    agence: str
    pole: str
    jeton: str


class VerifierResponse(BaseModel):
    identifiant: str


class RelaisRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class RelaisResponse(BaseModel):
    reponse: str
