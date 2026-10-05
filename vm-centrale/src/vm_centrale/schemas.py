from datetime import datetime
from decimal import Decimal

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
    # CompteResponse, ni stocké en clair) : à la création, c'est la seule
    # occasion où l'administrateur peut le récupérer pour le transmettre au
    # collaborateur (l'autre occasion étant une réinitialisation, voir
    # MotDePasseReinitialiseResponse).
    mot_de_passe: str


class MotDePasseReinitialiseResponse(BaseModel):
    mot_de_passe: str


class StatutAdminRequest(BaseModel):
    est_admin: bool


class ConversationCreeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    # Optionnelle (compatibilité avec un appelant qui n'en fournit pas) :
    # si fournie, une requête rejouée avec la même clé pour le même compte
    # reçoit la réponse déjà produite au lieu de créer une seconde
    # conversation (cf. vm_centrale.concurrence.CacheIdempotence).
    cle_idempotence: str | None = None
    # Optionnelle : id d'une pièce jointe déjà téléversée (POST
    # /pieces-jointes, sans conversation au moment de l'upload — voir
    # vm_centrale.models.PieceJointe.conversation_id) à rattacher à ce
    # premier message (spec 1.1.2).
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
    # Pagination par curseur (issue #103) : indique s'il reste des messages
    # plus anciens que `messages` à charger (un nouvel appel avec avant_id =
    # id du plus ancien message ci-dessus). Jamais de pagination par numéro
    # de page ni par décalage global, voir vm_centrale.routers.conversations.
    a_des_messages_plus_anciens: bool


class ConversationRenommeeRequest(BaseModel):
    titre: str = Field(min_length=1)


class MessageEnvoyeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    # Voir ConversationCreeRequest.cle_idempotence.
    cle_idempotence: str | None = None
    # Voir ConversationCreeRequest.piece_jointe_id.
    piece_jointe_id: int | None = None


class MessageEnvoyeResponse(BaseModel):
    reponse: str


class PieceJointeResume(BaseModel):
    id: int
    nom_fichier: str
    type_mime: str


class PieceJointeCreeeResponse(BaseModel):
    piece_jointe: PieceJointeResume
    echec_analyse: bool


class ProfilTravailResponse(BaseModel):
    contenu: str
    date_derniere_maj: datetime | None


class DetailConsommationCategorie(BaseModel):
    # tokens_total et pages_traitees toujours présents (0 si non applicable) :
    # Pièce jointe mélange des lignes "ocr" (page-based) et "vision"
    # (token-based), Chat n'est jamais page-based (spec 1.1.3).
    tokens_total: int
    pages_traitees: int
    cout_usd: Decimal
    nombre_requetes: int


class ConversationConsommationResponse(BaseModel):
    id: int
    titre: str
    cout_usd: Decimal
    chat: DetailConsommationCategorie
    piece_jointe: DetailConsommationCategorie


class ConsommationResponse(BaseModel):
    chat: DetailConsommationCategorie
    piece_jointe: DetailConsommationCategorie
    # Triée par cout_usd décroissant ; ne contient que les conversations
    # encore existantes ayant au moins une ligne Consommation rattachée
    # (spec 1.1.3).
    conversations: list[ConversationConsommationResponse]


class CompteConsommationResponse(BaseModel):
    identifiant: str
    prenom: str
    nom: str
    cout_usd: Decimal
    chat: DetailConsommationCategorie
    piece_jointe: DetailConsommationCategorie


class InspecteurCompteResponse(BaseModel):
    # Pas de jointure vers Compte (Conversation n'a pas de ForeignKey vers
    # comptes.identifiant, même convention qu'ailleurs) : seul l'identifiant,
    # distinct des champs prenom/nom/etc. d'un CompteResponse classique.
    identifiant_compte: str


class InspecteurConversationResponse(BaseModel):
    id: int
    titre: str
    date_creation: datetime
    date_derniere_activite: datetime


class InspecteurEchangeResumeResponse(BaseModel):
    # Fil chronologique d'une conversation (spec 1.3.0) : juste assez pour la
    # navigation et l'affichage replié d'une carte d'échange, le détail
    # complet (payload/réponse) n'étant chargé qu'au dépliage (GET
    # /inspecteur/echanges/{id}).
    id: int
    type_appel: str
    statut: str
    date_creation: datetime


class InspecteurEchangeDetailResponse(BaseModel):
    id: int
    identifiant_compte: str
    conversation_id: int | None
    piece_jointe_id: int | None
    type_appel: str
    modele: str
    requete_payload: dict
    reponse_payload: dict | None
    statut: str
    erreur: str | None
    date_creation: datetime
