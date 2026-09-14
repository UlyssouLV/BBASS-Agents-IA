import httpx

from poste.config import VM_CENTRALE_BASE_URL

_http_client = httpx.Client(timeout=10.0)


class VmCentraleClient:
    def authentifier(self, identifiant: str, mot_de_passe: str) -> bool:
        reponse = _http_client.post(
            f"{VM_CENTRALE_BASE_URL}/auth",
            json={"identifiant": identifiant, "mot_de_passe": mot_de_passe},
        )
        if reponse.status_code == 401:
            return False
        reponse.raise_for_status()
        return True


def get_vm_centrale_client() -> VmCentraleClient:
    return VmCentraleClient()
