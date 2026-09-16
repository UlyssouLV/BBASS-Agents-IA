from datetime import datetime

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


class ConversationCreationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class ConversationResume(BaseModel):
    id: int
    titre: str


class ConversationCreeResponse(BaseModel):
    conversation: ConversationResume
    reponse: str


class ConversationResponse(BaseModel):
    id: int
    titre: str
    date_derniere_activite: datetime


class MessageResponse(BaseModel):
    id: int
    role: str
    contenu: str
    date_creation: datetime


class ConversationDetailResponse(BaseModel):
    id: int
    titre: str
    date_creation: datetime
    date_derniere_activite: datetime
    messages: list[MessageResponse]


class ConversationRenommeeRequest(BaseModel):
    titre: str = Field(min_length=1)


class MessageEnvoyeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class MessageEnvoyeResponse(BaseModel):
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


class CompteModificationRequest(BaseModel):
    prenom: str = Field(min_length=1)
    nom: str = Field(min_length=1)
    email: str | None = None
    agence: str = Field(min_length=1)
    poles: list[str] = Field(min_length=1)


class MotDePasseReinitialiseResponse(BaseModel):
    mot_de_passe: str


class StatutAdminRequest(BaseModel):
    est_admin: bool
    cle_admin_vm: str = Field(min_length=1)


class SuppressionCompteRequest(BaseModel):
    cle_admin_vm: str = Field(min_length=1)
