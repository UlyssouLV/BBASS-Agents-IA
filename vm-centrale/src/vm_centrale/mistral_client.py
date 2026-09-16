import base64
from collections.abc import Mapping, Sequence

import httpx

from vm_centrale.config import MISTRAL_HTTP_TIMEOUT, MODELE_CHAT, MODELE_OCR, get_mistral_api_key

_API_URL_CHAT = "https://api.mistral.ai/v1/chat/completions"
_API_URL_OCR = "https://api.mistral.ai/v1/ocr"

_http_client = httpx.Client(timeout=MISTRAL_HTTP_TIMEOUT)


class MistralClient:
    def __init__(self, modele: str = MODELE_CHAT, modele_ocr: str = MODELE_OCR) -> None:
        self._modele = modele
        self._modele_ocr = modele_ocr

    def chat(
        self,
        # `content` reste une str pour un message texte, mais devient une
        # liste de parts (`text`/`image_url`) pour l'appel vision image
        # (vm_centrale.analyse_pieces_jointes.image) : ce paramètre reste
        # celui d'un simple relais vers /v1/chat/completions, sans logique
        # propre à un format, contrairement à .ocr() ci-dessous. `Sequence`/
        # `Mapping` (covariants), pas `list`/`dict`, pour accepter aussi bien
        # `list[dict[str, str]]` (messages texte usuels) que la liste de
        # parts à contenu mixte de l'appel vision.
        messages: str | Sequence[Mapping[str, object]],
        response_format: dict | None = None,
    ) -> str:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        api_key = get_mistral_api_key()
        payload: dict = {
            "model": self._modele,
            "messages": messages,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        reponse = _http_client.post(
            _API_URL_CHAT,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        reponse.raise_for_status()
        return reponse.json()["choices"][0]["message"]["content"]

    def ocr(self, document: bytes, type_mime: str) -> str:
        # Appel stateless dédié à /v1/ocr (forme de requête/réponse distincte
        # de .chat() ci-dessus) : le fichier est transmis inline en base64,
        # jamais via la Files API Mistral (ADR-0009) — aucun file_id
        # persistant n'est jamais référencé.
        api_key = get_mistral_api_key()
        document_url = f"data:{type_mime};base64,{base64.b64encode(document).decode('ascii')}"
        payload = {
            "model": self._modele_ocr,
            "document": {"type": "document_url", "document_url": document_url},
        }

        reponse = _http_client.post(
            _API_URL_OCR,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        reponse.raise_for_status()
        pages = reponse.json()["pages"]
        return "\n\n".join(page["markdown"] for page in pages)


def get_mistral_client() -> MistralClient:
    return MistralClient()
