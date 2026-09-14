from pydantic import BaseModel


class AuthRequest(BaseModel):
    identifiant: str
    mot_de_passe: str


class AuthResponse(BaseModel):
    agence: str
    pole: str
