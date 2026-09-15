from pydantic import BaseModel, Field, field_validator

from vm_centrale.poles import POLES_VALIDES


def _valider_poles(poles: list[str]) -> list[str]:
    inconnus = [pole for pole in poles if pole not in POLES_VALIDES]
    if inconnus:
        raise ValueError(f"Pôle(s) inconnu(s) : {', '.join(inconnus)}")
    if len(set(poles)) != len(poles):
        raise ValueError("La liste des pôles ne doit pas contenir de doublon")
    return poles


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


class ChangerMotDePasseRequest(BaseModel):
    nouveau_mot_de_passe: str = Field(min_length=1)


class _ChampsCompteModifiables(BaseModel):
    prenom: str = Field(min_length=1)
    nom: str = Field(min_length=1)
    email: str | None = None
    agence: str = Field(min_length=1)
    poles: list[str] = Field(min_length=1)

    @field_validator("poles")
    @classmethod
    def _poles_valides(cls, poles: list[str]) -> list[str]:
        return _valider_poles(poles)


class CompteCreeRequest(_ChampsCompteModifiables):
    identifiant: str = Field(min_length=1)


class CompteModifieRequest(_ChampsCompteModifiables):
    pass


class CompteResponse(BaseModel):
    identifiant: str
    prenom: str
    nom: str
    email: str | None
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool


class CompteCreeResponse(CompteResponse):
    # Le mot de passe généré n'est jamais renvoyé ailleurs (ni dans
    # CompteResponse, ni stocké en clair) : c'est la seule occasion où
    # l'administrateur peut le récupérer pour le transmettre au collaborateur.
    mot_de_passe: str


class RelaisRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class RelaisResponse(BaseModel):
    reponse: str
