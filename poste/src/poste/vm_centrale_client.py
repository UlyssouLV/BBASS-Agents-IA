import httpx

from poste.config import POSTE_HTTP_TIMEOUT, VM_CENTRALE_BASE_URL

_http_client = httpx.Client(timeout=POSTE_HTTP_TIMEOUT)


class VmCentraleClient:
    def authentifier(self, identifiant: str, mot_de_passe: str) -> str | None:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/auth",
            json={"identifiant": identifiant, "mot_de_passe": mot_de_passe},
        )
        if reponse.status_code == 401:
            return None
        reponse.raise_for_status()
        return reponse.json()["jeton"]

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
