import pytest
from fastapi.testclient import TestClient

from poste.main import app
from poste.session import SessionStore, get_session_store
from poste.vm_centrale_client import (
    AuthentificationReussie,
    CompteAdmin,
    CompteConsommation,
    CompteCree,
    Consommation,
    Conversation,
    ConversationCree,
    ConversationDetail,
    PieceJointeCreee,
    ProfilTravail,
    VerificationReussie,
    get_vm_centrale_client,
)


class VmCentraleClientFactice:
    def __init__(self) -> None:
        self.appels: list[tuple[str, str]] = []
        self.jetons_verifies: list[str] = []
        self.jetons_revoques: list[str] = []
        self._authentifie = False
        self._exception: Exception | None = None
        self._jeton = "jeton-factice"
        self._prenom = "Jean"
        self._nom = "Dupont"
        self._agence = "Castries"
        self._poles: list[str] = ["Foncier"]
        self._est_admin = False
        self._doit_changer_mot_de_passe = False
        self._identifiant_verifie: str | None = None
        self._est_admin_verifie = False
        self._exception_verification: Exception | None = None
        self._exception_revocation: Exception | None = None
        self._comptes: list[CompteAdmin] = []
        self._exception_liste_comptes: Exception | None = None
        self._jetons_liste_comptes: list[str] = []
        self._consommation_comptes: list[CompteConsommation] = []
        self._exception_consommation_comptes: Exception | None = None
        self._jetons_consommation_comptes: list[str] = []
        self._compte_cree: CompteCree | None = None
        self._exception_creation_compte: Exception | None = None
        self._requetes_creation_compte: list[dict] = []
        self._jetons_creation_compte: list[str] = []
        self._exception_changement_mot_de_passe: Exception | None = None
        self.appels_changement_mot_de_passe: list[tuple[str, str]] = []
        self._compte_modifie: CompteAdmin | None = None
        self._exception_modification_compte: Exception | None = None
        self._requetes_modification_compte: list[dict] = []
        self._jetons_modification_compte: list[str] = []
        self._mot_de_passe_reinitialise: str | None = None
        self._exception_reinitialisation_mot_de_passe: Exception | None = None
        self._jetons_reinitialisation_mot_de_passe: list[str] = []
        self._identifiants_reinitialisation_mot_de_passe: list[str] = []
        self._exception_deconnexion_forcee: Exception | None = None
        self._jetons_deconnexion_forcee: list[str] = []
        self._identifiants_deconnexion_forcee: list[str] = []
        self._compte_statut_admin_modifie: CompteAdmin | None = None
        self._exception_statut_admin: Exception | None = None
        self._jetons_statut_admin: list[str] = []
        self._requetes_statut_admin: list[dict] = []
        self._exception_suppression_compte: Exception | None = None
        self._jetons_suppression_compte: list[str] = []
        self._requetes_suppression_compte: list[dict] = []
        self._conversation_creee: ConversationCree | None = None
        self._exception_creation_conversation: Exception | None = None
        self._jetons_creation_conversation: list[str] = []
        self._messages_creation_conversation: list[str] = []
        self._cles_idempotence_creation_conversation: list[str | None] = []
        self._conversations: list[Conversation] = []
        self._exception_liste_conversations: Exception | None = None
        self._jetons_liste_conversations: list[str] = []
        self._detail_conversation: ConversationDetail | None = None
        self._exception_detail_conversation: Exception | None = None
        self._jetons_detail_conversation: list[str] = []
        self._ids_detail_conversation: list[int] = []
        self._conversation_renommee: Conversation | None = None
        self._exception_renommage_conversation: Exception | None = None
        self._jetons_renommage_conversation: list[str] = []
        self._requetes_renommage_conversation: list[dict] = []
        self._exception_suppression_conversation: Exception | None = None
        self._jetons_suppression_conversation: list[str] = []
        self._ids_suppression_conversation: list[int] = []
        self._reponse_message_conversation = ""
        self._exception_envoi_message_conversation: Exception | None = None
        self._jetons_envoi_message_conversation: list[str] = []
        self._requetes_envoi_message_conversation: list[dict] = []
        self._cles_idempotence_envoi_message_conversation: list[str | None] = []
        self._profil_travail: ProfilTravail | None = None
        self._exception_profil_travail: Exception | None = None
        self._jetons_profil_travail: list[str] = []
        self._identifiants_profil_travail: list[str] = []
        self._consommation: Consommation | None = None
        self._exception_consommation: Exception | None = None
        self._jetons_consommation: list[str] = []
        self._pieces_jointes_id_creation_conversation: list[int | None] = []
        self._pieces_jointes_id_envoi_message_conversation: list[int | None] = []
        self._piece_jointe_creee: PieceJointeCreee | None = None
        self._exception_televersement_piece_jointe: Exception | None = None
        self._jetons_televersement_piece_jointe: list[str] = []
        self._requetes_televersement_piece_jointe: list[dict] = []
        self._piece_jointe_creee_sans_conversation: PieceJointeCreee | None = None
        self._exception_televersement_piece_jointe_sans_conversation: Exception | None = None
        self._jetons_televersement_piece_jointe_sans_conversation: list[str] = []
        self._requetes_televersement_piece_jointe_sans_conversation: list[dict] = []

    def accepter(
        self,
        prenom: str = "Jean",
        nom: str = "Dupont",
        agence: str = "Castries",
        poles: list[str] | None = None,
        est_admin: bool = False,
        doit_changer_mot_de_passe: bool = False,
    ) -> None:
        self._authentifie = True
        self._exception = None
        self._prenom = prenom
        self._nom = nom
        self._agence = agence
        self._poles = poles if poles is not None else ["Foncier"]
        self._est_admin = est_admin
        self._doit_changer_mot_de_passe = doit_changer_mot_de_passe

    def rejeter(self) -> None:
        self._authentifie = False
        self._exception = None

    def echouer(self, exception: Exception) -> None:
        self._exception = exception

    def verification_reussit(self, identifiant: str, est_admin: bool = False) -> None:
        self._identifiant_verifie = identifiant
        self._est_admin_verifie = est_admin
        self._exception_verification = None

    def verification_echoue(self) -> None:
        self._identifiant_verifie = None
        self._exception_verification = None

    def verification_indisponible(self, exception: Exception) -> None:
        self._exception_verification = exception

    def revocation_echoue(self, exception: Exception) -> None:
        self._exception_revocation = exception

    def authentifier(self, identifiant: str, mot_de_passe: str) -> AuthentificationReussie | None:
        self.appels.append((identifiant, mot_de_passe))
        if self._exception is not None:
            raise self._exception
        if not self._authentifie:
            return None
        return AuthentificationReussie(
            prenom=self._prenom,
            nom=self._nom,
            jeton=self._jeton,
            agence=self._agence,
            poles=self._poles,
            est_admin=self._est_admin,
            doit_changer_mot_de_passe=self._doit_changer_mot_de_passe,
        )

    def verifier(self, jeton: str) -> VerificationReussie | None:
        self.jetons_verifies.append(jeton)
        if self._exception_verification is not None:
            raise self._exception_verification
        if self._identifiant_verifie is None:
            return None
        return VerificationReussie(identifiant=self._identifiant_verifie, est_admin=self._est_admin_verifie)

    def revoquer(self, jeton: str) -> None:
        self.jetons_revoques.append(jeton)
        if self._exception_revocation is not None:
            raise self._exception_revocation

    def liste_comptes_retourne(self, comptes: list[CompteAdmin]) -> None:
        self._comptes = comptes
        self._exception_liste_comptes = None

    def liste_comptes_echoue(self, exception: Exception) -> None:
        # Couvre aussi bien JetonInvalideError / AccesAdminRequisError
        # (erreurs métier attendues, voir vm_centrale_client) qu'une panne
        # quelconque de la VM centrale.
        self._exception_liste_comptes = exception

    def lister_comptes(self, jeton: str) -> list[CompteAdmin]:
        self._jetons_liste_comptes.append(jeton)
        if self._exception_liste_comptes is not None:
            raise self._exception_liste_comptes
        return self._comptes

    def consommation_comptes_retournee(self, comptes: list[CompteConsommation]) -> None:
        self._consommation_comptes = comptes
        self._exception_consommation_comptes = None

    def consommation_comptes_echoue(self, exception: Exception) -> None:
        self._exception_consommation_comptes = exception

    def lister_consommation_comptes(self, jeton: str) -> list[CompteConsommation]:
        self._jetons_consommation_comptes.append(jeton)
        if self._exception_consommation_comptes is not None:
            raise self._exception_consommation_comptes
        return self._consommation_comptes

    def creation_compte_reussit(self, compte: CompteCree) -> None:
        self._compte_cree = compte
        self._exception_creation_compte = None

    def creation_compte_echoue(self, exception: Exception) -> None:
        self._exception_creation_compte = exception

    def creer_compte(
        self,
        jeton: str,
        identifiant: str,
        prenom: str,
        nom: str,
        agence: str,
        poles: list[str],
        email: str | None = None,
    ) -> CompteCree:
        self._jetons_creation_compte.append(jeton)
        self._requetes_creation_compte.append(
            {
                "identifiant": identifiant,
                "prenom": prenom,
                "nom": nom,
                "email": email,
                "agence": agence,
                "poles": poles,
            }
        )
        if self._exception_creation_compte is not None:
            raise self._exception_creation_compte
        assert self._compte_cree is not None
        return self._compte_cree

    def modification_compte_reussit(self, compte: CompteAdmin) -> None:
        self._compte_modifie = compte
        self._exception_modification_compte = None

    def modification_compte_echoue(self, exception: Exception) -> None:
        self._exception_modification_compte = exception

    def modifier_compte(
        self,
        jeton: str,
        identifiant: str,
        prenom: str,
        nom: str,
        agence: str,
        poles: list[str],
        email: str | None = None,
    ) -> CompteAdmin:
        self._jetons_modification_compte.append(jeton)
        self._requetes_modification_compte.append(
            {
                "identifiant": identifiant,
                "prenom": prenom,
                "nom": nom,
                "email": email,
                "agence": agence,
                "poles": poles,
            }
        )
        if self._exception_modification_compte is not None:
            raise self._exception_modification_compte
        assert self._compte_modifie is not None
        return self._compte_modifie

    def changement_mot_de_passe_echoue(self, exception: Exception) -> None:
        self._exception_changement_mot_de_passe = exception

    def changer_mot_de_passe(self, jeton: str, nouveau_mot_de_passe: str) -> None:
        self.appels_changement_mot_de_passe.append((jeton, nouveau_mot_de_passe))
        if self._exception_changement_mot_de_passe is not None:
            raise self._exception_changement_mot_de_passe

    def reinitialisation_mot_de_passe_reussit(self, mot_de_passe: str) -> None:
        self._mot_de_passe_reinitialise = mot_de_passe
        self._exception_reinitialisation_mot_de_passe = None

    def reinitialisation_mot_de_passe_echoue(self, exception: Exception) -> None:
        self._exception_reinitialisation_mot_de_passe = exception

    def reinitialiser_mot_de_passe(self, jeton: str, identifiant: str) -> str:
        self._jetons_reinitialisation_mot_de_passe.append(jeton)
        self._identifiants_reinitialisation_mot_de_passe.append(identifiant)
        if self._exception_reinitialisation_mot_de_passe is not None:
            raise self._exception_reinitialisation_mot_de_passe
        assert self._mot_de_passe_reinitialise is not None
        return self._mot_de_passe_reinitialise

    def deconnexion_forcee_echoue(self, exception: Exception) -> None:
        self._exception_deconnexion_forcee = exception

    def deconnexion_forcee(self, jeton: str, identifiant: str) -> None:
        self._jetons_deconnexion_forcee.append(jeton)
        self._identifiants_deconnexion_forcee.append(identifiant)
        if self._exception_deconnexion_forcee is not None:
            raise self._exception_deconnexion_forcee

    def statut_admin_modifie(self, compte: CompteAdmin) -> None:
        self._compte_statut_admin_modifie = compte
        self._exception_statut_admin = None

    def statut_admin_echoue(self, exception: Exception) -> None:
        self._exception_statut_admin = exception

    def modifier_statut_admin(
        self, jeton: str, identifiant: str, est_admin: bool, cle_admin_vm: str
    ) -> CompteAdmin:
        self._jetons_statut_admin.append(jeton)
        self._requetes_statut_admin.append(
            {"identifiant": identifiant, "est_admin": est_admin, "cle_admin_vm": cle_admin_vm}
        )
        if self._exception_statut_admin is not None:
            raise self._exception_statut_admin
        assert self._compte_statut_admin_modifie is not None
        return self._compte_statut_admin_modifie

    def suppression_compte_echoue(self, exception: Exception) -> None:
        self._exception_suppression_compte = exception

    def supprimer_compte(self, jeton: str, identifiant: str, cle_admin_vm: str) -> None:
        self._jetons_suppression_compte.append(jeton)
        self._requetes_suppression_compte.append(
            {"identifiant": identifiant, "cle_admin_vm": cle_admin_vm}
        )
        if self._exception_suppression_compte is not None:
            raise self._exception_suppression_compte

    def creation_conversation_reussit(self, conversation: ConversationCree) -> None:
        self._conversation_creee = conversation
        self._exception_creation_conversation = None

    def creation_conversation_echoue(self, exception: Exception) -> None:
        self._exception_creation_conversation = exception

    def creer_conversation(
        self,
        jeton: str,
        message: str,
        cle_idempotence: str | None = None,
        piece_jointe_id: int | None = None,
    ) -> ConversationCree:
        self._jetons_creation_conversation.append(jeton)
        self._messages_creation_conversation.append(message)
        self._cles_idempotence_creation_conversation.append(cle_idempotence)
        self._pieces_jointes_id_creation_conversation.append(piece_jointe_id)
        if self._exception_creation_conversation is not None:
            raise self._exception_creation_conversation
        assert self._conversation_creee is not None
        return self._conversation_creee

    def liste_conversations_retourne(self, conversations: list[Conversation]) -> None:
        self._conversations = conversations
        self._exception_liste_conversations = None

    def liste_conversations_echoue(self, exception: Exception) -> None:
        self._exception_liste_conversations = exception

    def lister_conversations(self, jeton: str) -> list[Conversation]:
        self._jetons_liste_conversations.append(jeton)
        if self._exception_liste_conversations is not None:
            raise self._exception_liste_conversations
        return self._conversations

    def detail_conversation_retourne(self, detail: ConversationDetail) -> None:
        self._detail_conversation = detail
        self._exception_detail_conversation = None

    def detail_conversation_echoue(self, exception: Exception) -> None:
        self._exception_detail_conversation = exception

    def consulter_conversation(self, jeton: str, conversation_id: int) -> ConversationDetail:
        self._jetons_detail_conversation.append(jeton)
        self._ids_detail_conversation.append(conversation_id)
        if self._exception_detail_conversation is not None:
            raise self._exception_detail_conversation
        assert self._detail_conversation is not None
        return self._detail_conversation

    def renommage_conversation_reussit(self, conversation: Conversation) -> None:
        self._conversation_renommee = conversation
        self._exception_renommage_conversation = None

    def renommage_conversation_echoue(self, exception: Exception) -> None:
        self._exception_renommage_conversation = exception

    def renommer_conversation(self, jeton: str, conversation_id: int, titre: str) -> Conversation:
        self._jetons_renommage_conversation.append(jeton)
        self._requetes_renommage_conversation.append(
            {"conversation_id": conversation_id, "titre": titre}
        )
        if self._exception_renommage_conversation is not None:
            raise self._exception_renommage_conversation
        assert self._conversation_renommee is not None
        return self._conversation_renommee

    def suppression_conversation_echoue(self, exception: Exception) -> None:
        self._exception_suppression_conversation = exception

    def supprimer_conversation(self, jeton: str, conversation_id: int) -> None:
        self._jetons_suppression_conversation.append(jeton)
        self._ids_suppression_conversation.append(conversation_id)
        if self._exception_suppression_conversation is not None:
            raise self._exception_suppression_conversation

    def envoi_message_conversation_reussit(self, reponse: str) -> None:
        self._reponse_message_conversation = reponse
        self._exception_envoi_message_conversation = None

    def envoi_message_conversation_echoue(self, exception: Exception) -> None:
        self._exception_envoi_message_conversation = exception

    def envoyer_message(
        self,
        jeton: str,
        conversation_id: int,
        message: str,
        cle_idempotence: str | None = None,
        piece_jointe_id: int | None = None,
    ) -> str:
        self._jetons_envoi_message_conversation.append(jeton)
        self._requetes_envoi_message_conversation.append(
            {"conversation_id": conversation_id, "message": message}
        )
        self._cles_idempotence_envoi_message_conversation.append(cle_idempotence)
        self._pieces_jointes_id_envoi_message_conversation.append(piece_jointe_id)
        if self._exception_envoi_message_conversation is not None:
            raise self._exception_envoi_message_conversation
        return self._reponse_message_conversation

    def televersement_piece_jointe_reussit(self, piece_jointe: PieceJointeCreee) -> None:
        self._piece_jointe_creee = piece_jointe
        self._exception_televersement_piece_jointe = None

    def televersement_piece_jointe_echoue(self, exception: Exception) -> None:
        self._exception_televersement_piece_jointe = exception

    def televerser_piece_jointe(
        self,
        jeton: str,
        conversation_id: int,
        nom_fichier: str,
        contenu: bytes,
        type_mime: str,
    ) -> PieceJointeCreee:
        self._jetons_televersement_piece_jointe.append(jeton)
        self._requetes_televersement_piece_jointe.append(
            {
                "conversation_id": conversation_id,
                "nom_fichier": nom_fichier,
                "contenu": contenu,
                "type_mime": type_mime,
            }
        )
        if self._exception_televersement_piece_jointe is not None:
            raise self._exception_televersement_piece_jointe
        assert self._piece_jointe_creee is not None
        return self._piece_jointe_creee

    def televersement_piece_jointe_sans_conversation_reussit(self, piece_jointe: PieceJointeCreee) -> None:
        self._piece_jointe_creee_sans_conversation = piece_jointe
        self._exception_televersement_piece_jointe_sans_conversation = None

    def televersement_piece_jointe_sans_conversation_echoue(self, exception: Exception) -> None:
        self._exception_televersement_piece_jointe_sans_conversation = exception

    def televerser_piece_jointe_sans_conversation(
        self, jeton: str, nom_fichier: str, contenu: bytes, type_mime: str
    ) -> PieceJointeCreee:
        self._jetons_televersement_piece_jointe_sans_conversation.append(jeton)
        self._requetes_televersement_piece_jointe_sans_conversation.append(
            {"nom_fichier": nom_fichier, "contenu": contenu, "type_mime": type_mime}
        )
        if self._exception_televersement_piece_jointe_sans_conversation is not None:
            raise self._exception_televersement_piece_jointe_sans_conversation
        assert self._piece_jointe_creee_sans_conversation is not None
        return self._piece_jointe_creee_sans_conversation

    def profil_travail_retourne(self, profil: ProfilTravail) -> None:
        self._profil_travail = profil
        self._exception_profil_travail = None

    def profil_travail_echoue(self, exception: Exception) -> None:
        self._exception_profil_travail = exception

    def consulter_profil_travail(self, jeton: str, identifiant: str) -> ProfilTravail:
        self._jetons_profil_travail.append(jeton)
        self._identifiants_profil_travail.append(identifiant)
        if self._exception_profil_travail is not None:
            raise self._exception_profil_travail
        assert self._profil_travail is not None
        return self._profil_travail

    def consommation_retournee(self, consommation: Consommation) -> None:
        self._consommation = consommation
        self._exception_consommation = None

    def consommation_echoue(self, exception: Exception) -> None:
        self._exception_consommation = exception

    def consulter_consommation(self, jeton: str) -> Consommation:
        self._jetons_consommation.append(jeton)
        if self._exception_consommation is not None:
            raise self._exception_consommation
        assert self._consommation is not None
        return self._consommation


@pytest.fixture(autouse=True)
def keyring_factice(monkeypatch):
    # Aucun test ne doit jamais toucher le vrai gestionnaire d'identifiants
    # Windows : cette fixture le remplace par un stockage en mémoire pour
    # toute la suite.
    stockage: dict[tuple[str, str], str] = {}

    def fake_get_password(service_name: str, username: str) -> str | None:
        return stockage.get((service_name, username))

    def fake_set_password(service_name: str, username: str, password: str) -> None:
        stockage[(service_name, username)] = password

    def fake_delete_password(service_name: str, username: str) -> None:
        if (service_name, username) not in stockage:
            raise RuntimeError("Aucun mot de passe à supprimer pour ce service/utilisateur")
        del stockage[(service_name, username)]

    monkeypatch.setattr("poste.session.keyring.get_password", fake_get_password)
    monkeypatch.setattr("poste.session.keyring.set_password", fake_set_password)
    monkeypatch.setattr("poste.session.keyring.delete_password", fake_delete_password)
    return stockage


@pytest.fixture()
def vm_centrale_client_factice():
    return VmCentraleClientFactice()


@pytest.fixture()
def session_store():
    return SessionStore()


@pytest.fixture()
def client(vm_centrale_client_factice, session_store):
    app.dependency_overrides[get_vm_centrale_client] = lambda: vm_centrale_client_factice
    app.dependency_overrides[get_session_store] = lambda: session_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
