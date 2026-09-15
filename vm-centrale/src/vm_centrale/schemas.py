from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    identifiant: str
    mot_de_passe: str


class AuthResponse(BaseModel):
    prenom: str
    nom: str
    email: str | None
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool
    jeton: str


class VerifierResponse(BaseModel):
    identifiant: str
    est_admin: bool


class RelaisRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class RelaisResponse(BaseModel):
    reponse: str
