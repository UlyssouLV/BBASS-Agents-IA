from dataclasses import dataclass
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

    def envoyer_message(self, message: str, jeton: str) -> str:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/relais",
            json={"message": message},
            headers={"Authorization": f"Bearer {jeton}"},
        )
        if reponse.status_code == 401:
            raise JetonInvalideError()
        reponse.raise_for_status()
        return reponse.json()["reponse"]

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
