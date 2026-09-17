from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

import httpx

from poste.config import POSTE_HTTP_TIMEOUT, VM_CENTRALE_BASE_URL

_http_client = httpx.Client(timeout=POSTE_HTTP_TIMEOUT)


class JetonInvalideError(Exception):
    # Distingue un jeton refusé (401 de la VM, revoqué ou jamais valide) d'une
    # panne quelconque : le poste doit renvoyer le collaborateur à l'écran de
    # connexion dans le premier cas, un état d'erreur générique dans le second.
    pass


class AccesAdminRequisError(Exception):
    # 403 de la VM : jeton valide mais compte non-administrateur (ou droit
    # retiré depuis l'ouverture de la session côté poste).
    pass


class IdentifiantDejaUtiliseError(Exception):
    # 409 de la VM à la création : identifiant déjà pris par un autre compte.
    pass


class CompteInexistantError(Exception):
    # 404 de la VM à la modification : identifiant ne correspondant à aucun compte.
    pass


class CleAdminInvalideError(Exception):
    # 401 de la VM levé par exiger_cle_admin_vm (clé d'administration VM
    # absente/invalide) : distinct d'un jeton invalide (401 levé par
    # get_compte_admin), qui doit fermer la session côté poste alors que
    # celui-ci ne le doit pas (le jeton de session reste valide, seule la
    # confirmation par clé a échoué).
    pass


class ConversationIntrouvableError(Exception):
    # 404 de la VM sur /conversations* : id inexistant ou n'appartenant pas au
    # compte du jeton (la VM ne distingue jamais les deux, voir
    # vm_centrale.routers.conversations).
    pass


class PieceJointeIntrouvableError(Exception):
    # 404 de la VM sur pieces-jointes* : piece_jointe_id inexistant,
    # n'appartenant pas au compte du jeton, ou rattaché à une autre
    # conversation (la VM ne distingue jamais les cas, voir
    # vm_centrale.routers.conversations._recuperer_piece_jointe_du_compte).
    pass


class PieceJointeRefuseeError(Exception):
    # 400 de la VM sur pieces-jointes* : type de fichier non supporté,
    # fichier trop volumineux, ou pièce jointe déjà liée à un autre message.
    # Le message distingue les cas, relayé tel quel (même principe que
    # DernierAdministrateurError).
    pass


class DernierAdministrateurError(Exception):
    # 409 de la VM : la rétrogradation ou la suppression ferait passer le
    # nombre de comptes administrateur à zéro (garde-fou dernier
    # administrateur, spec V1.1). La VM distingue les deux cas par un texte
    # différent (vm_centrale.routers.comptes) : porté par le message de cette
    # exception plutôt que redupliqué ici, pour que le poste affiche le bon
    # verbe (rétrograder vs supprimer) sans connaître les deux textes.
    pass


@dataclass
class AuthentificationReussie:
    prenom: str
    nom: str
    jeton: str
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool


@dataclass
class VerificationReussie:
    identifiant: str
    est_admin: bool


@dataclass
class CompteAdmin:
    identifiant: str
    prenom: str
    nom: str
    email: str | None
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool


@dataclass
class CompteCree(CompteAdmin):
    # Le mot de passe généré n'est disponible qu'à cette occasion (voir
    # vm-centrale CompteCreeResponse) : jamais renvoyé par GET /comptes.
    mot_de_passe: str


@dataclass
class ConversationResume:
    id: int
    titre: str


@dataclass
class ConversationCree:
    conversation: ConversationResume
    reponse: str


@dataclass
class Conversation:
    id: int
    titre: str
    date_derniere_activite: datetime


@dataclass
class Message:
    id: int
    role: str
    contenu: str
    date_creation: datetime


@dataclass
class ConversationDetail:
    id: int
    titre: str
    date_creation: datetime
    date_derniere_activite: datetime
    messages: list[Message]


@dataclass
class ProfilTravail:
    contenu: str
    date_derniere_maj: datetime | None


@dataclass
class PieceJointeResume:
    id: int
    nom_fichier: str
    type_mime: str


@dataclass
class PieceJointeCreee:
    piece_jointe: PieceJointeResume
    echec_analyse: bool


@dataclass
class DetailConsommationCategorie:
    tokens_total: int
    pages_traitees: int
    cout_usd: Decimal
    nombre_requetes: int


@dataclass
class ConversationConsommation:
    id: int
    titre: str
    cout_usd: Decimal
    chat: DetailConsommationCategorie
    piece_jointe: DetailConsommationCategorie


@dataclass
class Consommation:
    chat: DetailConsommationCategorie
    piece_jointe: DetailConsommationCategorie
    conversations: list[ConversationConsommation]


def _champs_compte_admin(corps: dict) -> dict:
    # Extraction partagée par lister_comptes/creer_compte/modifier_compte :
    # les trois construisent un CompteAdmin (ou un CompteCree, qui y ajoute
    # juste mot_de_passe) à partir des mêmes champs de réponse VM.
    return {
        "identifiant": corps["identifiant"],
        "prenom": corps["prenom"],
        "nom": corps["nom"],
        "email": corps["email"],
        "agence": corps["agence"],
        "poles": corps["poles"],
        "est_admin": corps["est_admin"],
        "doit_changer_mot_de_passe": corps["doit_changer_mot_de_passe"],
    }


def _lever_si_jeton_ou_droits_refuses(reponse: httpx.Response) -> None:
    # Partagé par lister_comptes/creer_compte/modifier_compte : mêmes codes
    # d'erreur, même correspondance vers les exceptions métier du client.
    if reponse.status_code == 401:
        raise JetonInvalideError()
    if reponse.status_code == 403:
        raise AccesAdminRequisError()


# Doit rester identique à vm_centrale.autorisation._CLE_ADMIN_INVALIDE : c'est
# le seul moyen pour ce client de distinguer, parmi les deux causes possibles
# d'un 401 sur les endpoints exigeant la clé d'administration VM (suppression,
# PATCH .../est-admin), celle qui ne doit pas fermer la session de
# l'administrateur (voir CleAdminInvalideError).
_CLE_ADMIN_INVALIDE_DETAIL = "Clé d'administration manquante ou invalide"


def _lever_si_jeton_invalide(reponse: httpx.Response) -> None:
    # Partagée par les cinq endpoints /conversations* : un seul code d'erreur
    # possible en dehors de 404 (pas de notion de droits admin ici, contrairement
    # à _lever_si_jeton_ou_droits_refuses).
    if reponse.status_code == 401:
        raise JetonInvalideError()


def _lever_si_conversation_introuvable(reponse: httpx.Response) -> None:
    if reponse.status_code == 404:
        raise ConversationIntrouvableError()


# Doit rester identique à vm_centrale.routers.conversations._PIECE_JOINTE_INTROUVABLE :
# seul moyen de distinguer, parmi les deux 404 possibles sur creer_conversation/
# envoyer_message avec piece_jointe_id (conversation introuvable vs pièce jointe
# introuvable), lequel des deux est survenu — la VM renvoie le même code pour les
# deux (voir _recuperer_piece_jointe_du_compte).
_PIECE_JOINTE_INTROUVABLE_DETAIL = "Pièce jointe introuvable"


def _lever_si_erreur_piece_jointe(reponse: httpx.Response) -> None:
    # Partagée par creer_conversation/envoyer_message (piece_jointe_id) : un
    # 400 n'y est possible que pour une pièce jointe déjà liée à un autre
    # message ; un 404 peut venir soit de la conversation, soit de la pièce
    # jointe elle-même (voir _PIECE_JOINTE_INTROUVABLE_DETAIL ci-dessus).
    if reponse.status_code == 400:
        raise PieceJointeRefuseeError(reponse.json()["detail"])
    if reponse.status_code == 404:
        if reponse.json().get("detail") == _PIECE_JOINTE_INTROUVABLE_DETAIL:
            raise PieceJointeIntrouvableError(_PIECE_JOINTE_INTROUVABLE_DETAIL)
        raise ConversationIntrouvableError()


def _lever_si_upload_piece_jointe_refuse(reponse: httpx.Response) -> None:
    # Partagée par televerser_piece_jointe/televerser_piece_jointe_sans_conversation :
    # type non supporté ou fichier trop volumineux (spec 1.1.2), jamais de
    # confusion possible avec une conversation ici (pas de piece_jointe_id en
    # entrée sur ces deux endpoints).
    if reponse.status_code == 400:
        raise PieceJointeRefuseeError(reponse.json()["detail"])


def _vers_conversation(corps: dict) -> Conversation:
    return Conversation(
        id=corps["id"],
        titre=corps["titre"],
        date_derniere_activite=datetime.fromisoformat(corps["date_derniere_activite"]),
    )


def _vers_message(corps: dict) -> Message:
    return Message(
        id=corps["id"],
        role=corps["role"],
        contenu=corps["contenu"],
        date_creation=datetime.fromisoformat(corps["date_creation"]),
    )


def _vers_piece_jointe_creee(corps: dict) -> PieceJointeCreee:
    return PieceJointeCreee(
        piece_jointe=PieceJointeResume(**corps["piece_jointe"]),
        echec_analyse=corps["echec_analyse"],
    )


def _vers_profil_travail(corps: dict) -> ProfilTravail:
    return ProfilTravail(
        contenu=corps["contenu"],
        date_derniere_maj=(
            datetime.fromisoformat(corps["date_derniere_maj"])
            if corps["date_derniere_maj"] is not None
            else None
        ),
    )


def _vers_detail_consommation(corps: dict) -> DetailConsommationCategorie:
    return DetailConsommationCategorie(
        tokens_total=corps["tokens_total"],
        pages_traitees=corps["pages_traitees"],
        cout_usd=Decimal(corps["cout_usd"]),
        nombre_requetes=corps["nombre_requetes"],
    )


def _vers_conversation_consommation(corps: dict) -> ConversationConsommation:
    return ConversationConsommation(
        id=corps["id"],
        titre=corps["titre"],
        cout_usd=Decimal(corps["cout_usd"]),
        chat=_vers_detail_consommation(corps["chat"]),
        piece_jointe=_vers_detail_consommation(corps["piece_jointe"]),
    )


def _vers_consommation(corps: dict) -> Consommation:
    return Consommation(
        chat=_vers_detail_consommation(corps["chat"]),
        piece_jointe=_vers_detail_consommation(corps["piece_jointe"]),
        conversations=[_vers_conversation_consommation(c) for c in corps["conversations"]],
    )


def _lever_si_action_avec_cle_admin_refusee(reponse: httpx.Response) -> None:
    # Partagée par supprimer_compte/modifier_statut_admin : mêmes codes
    # d'erreur, même correspondance vers les exceptions métier du client
    # (les deux seuls endpoints exigeant X-Admin-Key en plus du jeton).
    if reponse.status_code == 401:
        if reponse.json().get("detail") == _CLE_ADMIN_INVALIDE_DETAIL:
            raise CleAdminInvalideError()
        raise JetonInvalideError()
    if reponse.status_code == 403:
        raise AccesAdminRequisError()
    if reponse.status_code == 409:
        raise DernierAdministrateurError(reponse.json()["detail"])


class VmCentraleClient:
    def authentifier(self, identifiant: str, mot_de_passe: str) -> AuthentificationReussie | None:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/auth",
            json={"identifiant": identifiant, "mot_de_passe": mot_de_passe},
        )
        if reponse.status_code == 401:
            return None
        reponse.raise_for_status()
        corps = reponse.json()
        return AuthentificationReussie(
            prenom=corps["prenom"],
            nom=corps["nom"],
            jeton=corps["jeton"],
            agence=corps["agence"],
            poles=corps["poles"],
            est_admin=corps["est_admin"],
            doit_changer_mot_de_passe=corps["doit_changer_mot_de_passe"],
        )

    def creer_conversation(
        self,
        jeton: str,
        message: str,
        cle_idempotence: str | None = None,
        piece_jointe_id: int | None = None,
    ) -> ConversationCree:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/conversations",
            json={
                "message": message,
                "cle_idempotence": cle_idempotence,
                "piece_jointe_id": piece_jointe_id,
            },
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        _lever_si_erreur_piece_jointe(reponse)
        reponse.raise_for_status()
        corps = reponse.json()
        return ConversationCree(
            conversation=ConversationResume(**corps["conversation"]),
            reponse=corps["reponse"],
        )

    def lister_conversations(self, jeton: str) -> list[Conversation]:
        reponse = _http_client.get(
            f"{VM_CENTRALE_BASE_URL}/conversations",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        reponse.raise_for_status()
        return [_vers_conversation(conversation) for conversation in reponse.json()]

    def consulter_conversation(self, jeton: str, conversation_id: int) -> ConversationDetail:
        reponse = _http_client.get(
            f"{VM_CENTRALE_BASE_URL}/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        _lever_si_conversation_introuvable(reponse)
        reponse.raise_for_status()
        corps = reponse.json()
        return ConversationDetail(
            id=corps["id"],
            titre=corps["titre"],
            date_creation=datetime.fromisoformat(corps["date_creation"]),
            date_derniere_activite=datetime.fromisoformat(corps["date_derniere_activite"]),
            messages=[_vers_message(message) for message in corps["messages"]],
        )

    def renommer_conversation(self, jeton: str, conversation_id: int, titre: str) -> Conversation:
        reponse = _http_client.patch(
            f"{VM_CENTRALE_BASE_URL}/conversations/{conversation_id}",
            json={"titre": titre},
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        _lever_si_conversation_introuvable(reponse)
        reponse.raise_for_status()
        return _vers_conversation(reponse.json())

    def supprimer_conversation(self, jeton: str, conversation_id: int) -> None:
        reponse = _http_client.delete(
            f"{VM_CENTRALE_BASE_URL}/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        _lever_si_conversation_introuvable(reponse)
        reponse.raise_for_status()

    def envoyer_message(
        self,
        jeton: str,
        conversation_id: int,
        message: str,
        cle_idempotence: str | None = None,
        piece_jointe_id: int | None = None,
    ) -> str:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/conversations/{conversation_id}/messages",
            json={
                "message": message,
                "cle_idempotence": cle_idempotence,
                "piece_jointe_id": piece_jointe_id,
            },
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        _lever_si_erreur_piece_jointe(reponse)
        reponse.raise_for_status()
        return reponse.json()["reponse"]

    def televerser_piece_jointe(
        self,
        jeton: str,
        conversation_id: int,
        nom_fichier: str,
        contenu: bytes,
        type_mime: str,
    ) -> PieceJointeCreee:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/conversations/{conversation_id}/pieces-jointes",
            files={"fichier": (nom_fichier, contenu, type_mime)},
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        _lever_si_conversation_introuvable(reponse)
        _lever_si_upload_piece_jointe_refuse(reponse)
        reponse.raise_for_status()
        return _vers_piece_jointe_creee(reponse.json())

    def televerser_piece_jointe_sans_conversation(
        self, jeton: str, nom_fichier: str, contenu: bytes, type_mime: str
    ) -> PieceJointeCreee:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/pieces-jointes",
            files={"fichier": (nom_fichier, contenu, type_mime)},
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        _lever_si_upload_piece_jointe_refuse(reponse)
        reponse.raise_for_status()
        return _vers_piece_jointe_creee(reponse.json())

    def consulter_profil_travail(self, jeton: str, identifiant: str) -> ProfilTravail:
        # Le poste ne demande jamais que le profil du compte propriétaire du
        # jeton (voir routers/profil_travail.py) : le 403 que la VM renvoie
        # pour un identifiant différent (spec V1.1.1) n'est donc jamais
        # attendu ici, et retombe sur l'erreur générique via raise_for_status.
        reponse = _http_client.get(
            f"{VM_CENTRALE_BASE_URL}/comptes/{quote(identifiant, safe='')}/profil-travail",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        reponse.raise_for_status()
        return _vers_profil_travail(reponse.json())

    def consulter_consommation(self, jeton: str) -> Consommation:
        # Toujours celle du compte propriétaire du jeton (identifiant extrait
        # côté VM à partir du jeton, voir vm_centrale.routers.consommation) :
        # pas de paramètre identifiant ici, contrairement à
        # consulter_profil_travail.
        reponse = _http_client.get(
            f"{VM_CENTRALE_BASE_URL}/consommation",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_invalide(reponse)
        reponse.raise_for_status()
        return _vers_consommation(reponse.json())

    def changer_mot_de_passe(self, jeton: str, nouveau_mot_de_passe: str) -> None:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/auth/mot-de-passe",
            json={"nouveau_mot_de_passe": nouveau_mot_de_passe},
            headers={"Authorization": f"Bearer {jeton}"},
        )
        if reponse.status_code == 401:
            raise JetonInvalideError()
        reponse.raise_for_status()

    def verifier(self, jeton: str) -> VerificationReussie | None:
        reponse = _http_client.get(
            f"{VM_CENTRALE_BASE_URL}/auth/verifier",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        if reponse.status_code == 401:
            return None
        reponse.raise_for_status()
        corps = reponse.json()
        return VerificationReussie(identifiant=corps["identifiant"], est_admin=corps["est_admin"])

    def revoquer(self, jeton: str) -> None:
        reponse = _http_client.delete(
            f"{VM_CENTRALE_BASE_URL}/auth/jeton",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        reponse.raise_for_status()

    def lister_comptes(self, jeton: str) -> list[CompteAdmin]:
        reponse = _http_client.get(
            f"{VM_CENTRALE_BASE_URL}/comptes",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_ou_droits_refuses(reponse)
        reponse.raise_for_status()
        return [CompteAdmin(**_champs_compte_admin(compte)) for compte in reponse.json()]

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
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/comptes",
            json={
                "identifiant": identifiant,
                "prenom": prenom,
                "nom": nom,
                "email": email,
                "agence": agence,
                "poles": poles,
            },
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_ou_droits_refuses(reponse)
        if reponse.status_code == 409:
            raise IdentifiantDejaUtiliseError()
        reponse.raise_for_status()
        corps = reponse.json()
        return CompteCree(**_champs_compte_admin(corps), mot_de_passe=corps["mot_de_passe"])

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
        reponse = _http_client.patch(
            f"{VM_CENTRALE_BASE_URL}/comptes/{quote(identifiant, safe='')}",
            json={
                "prenom": prenom,
                "nom": nom,
                "email": email,
                "agence": agence,
                "poles": poles,
            },
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_ou_droits_refuses(reponse)
        if reponse.status_code == 404:
            raise CompteInexistantError()
        reponse.raise_for_status()
        return CompteAdmin(**_champs_compte_admin(reponse.json()))

    def reinitialiser_mot_de_passe(self, jeton: str, identifiant: str) -> str:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/comptes/{quote(identifiant, safe='')}/reinitialiser-mot-de-passe",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_ou_droits_refuses(reponse)
        if reponse.status_code == 404:
            raise CompteInexistantError()
        reponse.raise_for_status()
        return reponse.json()["mot_de_passe"]

    def deconnexion_forcee(self, jeton: str, identifiant: str) -> None:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/comptes/{quote(identifiant, safe='')}/deconnexion-forcee",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        _lever_si_jeton_ou_droits_refuses(reponse)
        if reponse.status_code == 404:
            raise CompteInexistantError()
        reponse.raise_for_status()

    def modifier_statut_admin(
        self, jeton: str, identifiant: str, est_admin: bool, cle_admin_vm: str
    ) -> CompteAdmin:
        reponse = _http_client.patch(
            f"{VM_CENTRALE_BASE_URL}/comptes/{quote(identifiant, safe='')}/est-admin",
            json={"est_admin": est_admin},
            headers={"Authorization": f"Bearer {jeton}", "X-Admin-Key": cle_admin_vm},
        )
        _lever_si_action_avec_cle_admin_refusee(reponse)
        if reponse.status_code == 404:
            raise CompteInexistantError()
        reponse.raise_for_status()
        return CompteAdmin(**_champs_compte_admin(reponse.json()))

    def supprimer_compte(self, jeton: str, identifiant: str, cle_admin_vm: str) -> None:
        reponse = _http_client.delete(
            f"{VM_CENTRALE_BASE_URL}/comptes/{quote(identifiant, safe='')}",
            headers={"Authorization": f"Bearer {jeton}", "X-Admin-Key": cle_admin_vm},
        )
        _lever_si_action_avec_cle_admin_refusee(reponse)
        if reponse.status_code == 404:
            raise CompteInexistantError()
        reponse.raise_for_status()


def get_vm_centrale_client() -> VmCentraleClient:
    return VmCentraleClient()
