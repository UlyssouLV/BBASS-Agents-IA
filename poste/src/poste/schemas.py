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


class ChangerMotDePasseRequest(BaseModel):
    nouveau_mot_de_passe: str = Field(min_length=1)


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    reponse: str


class CompteAdminResponse(BaseModel):
    identifiant: str
    prenom: str
    nom: str
    email: str | None
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool


class CompteCreationRequest(BaseModel):
    identifiant: str = Field(min_length=1)
    prenom: str = Field(min_length=1)
    nom: str = Field(min_length=1)
    email: str | None = None
    agence: str = Field(min_length=1)
    poles: list[str] = Field(min_length=1)


class CompteCreeResponse(CompteAdminResponse):
    # Le mot de passe généré n'est renvoyé qu'à la création, jamais ailleurs
    # (voir CompteAdminResponse, utilisé par la liste).
    mot_de_passe: str
