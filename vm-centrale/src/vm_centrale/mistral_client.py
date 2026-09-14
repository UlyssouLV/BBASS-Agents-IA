import os

import httpx

_API_URL = "https://api.mistral.ai/v1/chat/completions"
_MODELE = "mistral-small-latest"

_http_client = httpx.Client(timeout=30.0)


class MistralClient:
    def __init__(self, modele: str = _MODELE) -> None:
        self._modele = modele

    def chat(self, message: str) -> str:
        # Lu ici plutôt qu'à la construction : une clé manquante doit lever
        # pendant l'appel, dans le try/except du endpoint de relais, jamais
        # pendant la résolution de la dépendance FastAPI (avant ce try/except).
        api_key = os.environ["MISTRAL_API_KEY"]
        reponse = _http_client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self._modele,
                "messages": [{"role": "user", "content": message}],
            },
        )
        reponse.raise_for_status()
        return reponse.json()["choices"][0]["message"]["content"]


def get_mistral_client() -> MistralClient:
    return MistralClient()
