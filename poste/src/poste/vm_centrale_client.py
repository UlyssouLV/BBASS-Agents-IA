from dataclasses import dataclass

import httpx

from poste.config import POSTE_HTTP_TIMEOUT, VM_CENTRALE_BASE_URL

_http_client = httpx.Client(timeout=POSTE_HTTP_TIMEOUT)


class JetonInvalideError(Exception):
    # Distingue un jeton refusé (401 de la VM, revoqué ou jamais valide) d'une
    # panne quelconque : le poste doit renvoyer le collaborateur à l'écran de
    # connexion dans le premier cas, un état d'erreur générique dans le second.
    pass


@dataclass
class AuthentificationReussie:
    prenom: str
    nom: str
    jeton: str


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
        return AuthentificationReussie(prenom=corps["prenom"], nom=corps["nom"], jeton=corps["jeton"])

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

    def verifier(self, jeton: str) -> str | None:
        reponse = _http_client.get(
            f"{VM_CENTRALE_BASE_URL}/auth/verifier",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        if reponse.status_code == 401:
            return None
        reponse.raise_for_status()
        return reponse.json()["identifiant"]

    def revoquer(self, jeton: str) -> None:
        reponse = _http_client.delete(
            f"{VM_CENTRALE_BASE_URL}/auth/jeton",
            headers={"Authorization": f"Bearer {jeton}"},
        )
        reponse.raise_for_status()


def get_vm_centrale_client() -> VmCentraleClient:
    return VmCentraleClient()
