from datetime import datetime
from decimal import Decimal

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
    # Optionnelle : voir vm_centrale.schemas.ConversationCreeRequest.cle_idempotence.
    cle_idempotence: str | None = None
    # Optionnelle : id d'une pièce jointe déjà téléversée (POST
    # /pieces-jointes, avant que cette conversation n'existe) à rattacher à
    # ce premier message. Voir vm_centrale.schemas.ConversationCreeRequest.piece_jointe_id.
    piece_jointe_id: int | None = None


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
    # Relayé tel quel depuis vm_centrale.schemas.ConversationDetailResponse,
    # voir poste.vm_centrale_client.ConversationDetail (issue #103).
    a_des_messages_plus_anciens: bool


class ConversationRenommeeRequest(BaseModel):
    titre: str = Field(min_length=1)


class MessageEnvoyeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    # Voir ConversationCreationRequest.cle_idempotence.
    cle_idempotence: str | None = None
    # Voir ConversationCreationRequest.piece_jointe_id.
    piece_jointe_id: int | None = None


class MessageEnvoyeResponse(BaseModel):
    reponse: str


class PieceJointeResumeResponse(BaseModel):
    id: int
    nom_fichier: str
    type_mime: str


class PieceJointeCreeeResponse(BaseModel):
    piece_jointe: PieceJointeResumeResponse
    echec_analyse: bool


class ProfilTravailResponse(BaseModel):
    contenu: str
    date_derniere_maj: datetime | None


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


class DetailConsommationCategorieResponse(BaseModel):
    tokens_total: int
    pages_traitees: int
    cout_usd: Decimal
    nombre_requetes: int


class ConversationConsommationResponse(BaseModel):
    id: int
    titre: str
    cout_usd: Decimal
    chat: DetailConsommationCategorieResponse
    piece_jointe: DetailConsommationCategorieResponse


class ConsommationResponse(BaseModel):
    chat: DetailConsommationCategorieResponse
    piece_jointe: DetailConsommationCategorieResponse
    conversations: list[ConversationConsommationResponse]


class CompteConsommationResponse(BaseModel):
    identifiant: str
    prenom: str
    nom: str
    cout_usd: Decimal
    chat: DetailConsommationCategorieResponse
    piece_jointe: DetailConsommationCategorieResponse


class InspecteurCompteResponse(BaseModel):
    identifiant_compte: str


class InspecteurConversationResponse(BaseModel):
    id: int
    titre: str
    date_creation: datetime
    date_derniere_activite: datetime


class InspecteurEchangeResumeResponse(BaseModel):
    id: int
    origine: str
    type_appel: str
    statut: str
    date_creation: datetime


class InspecteurEchangeDetailResponse(BaseModel):
    id: int
    identifiant_compte: str
    conversation_id: int | None
    piece_jointe_id: int | None
    origine: str
    type_appel: str
    modele: str
    requete_payload: dict
    reponse_payload: dict | None
    statut: str
    erreur: str | None
    date_creation: datetime
