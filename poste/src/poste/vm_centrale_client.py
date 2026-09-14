from dataclasses import dataclass

import httpx

from poste.config import POSTE_HTTP_TIMEOUT, VM_CENTRALE_BASE_URL

_http_client = httpx.Client(timeout=POSTE_HTTP_TIMEOUT)


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
        reponse.raise_for_status()
        return reponse.json()["reponse"]


def get_vm_centrale_client() -> VmCentraleClient:
    return VmCentraleClient()
