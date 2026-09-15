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


def get_vm_centrale_client() -> VmCentraleClient:
    return VmCentraleClient()
