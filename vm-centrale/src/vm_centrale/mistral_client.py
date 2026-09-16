import httpx

from vm_centrale.config import MISTRAL_HTTP_TIMEOUT, get_mistral_api_key

_API_URL = "https://api.mistral.ai/v1/chat/completions"
_MODELE = "mistral-small-latest"

_http_client = httpx.Client(timeout=MISTRAL_HTTP_TIMEOUT)


class MistralClient:
    def __init__(self, modele: str = _MODELE) -> None:
        self._modele = modele

    def chat(self, messages: str | list[dict[str, str]]) -> str:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        api_key = get_mistral_api_key()
        reponse = _http_client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self._modele,
                "messages": messages,
            },
        )
        reponse.raise_for_status()
        return reponse.json()["choices"][0]["message"]["content"]


def get_mistral_client() -> MistralClient:
    return MistralClient()
