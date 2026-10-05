import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

from vm_centrale.config import MISTRAL_HTTP_TIMEOUT, MODELE_CHAT, MODELE_OCR, get_mistral_api_key

_API_URL_CHAT = "https://api.mistral.ai/v1/chat/completions"
_API_URL_OCR = "https://api.mistral.ai/v1/ocr"

_http_client = httpx.Client(timeout=MISTRAL_HTTP_TIMEOUT)


@dataclass(frozen=True)
class AppelOutil:
    id: str
    nom: str
    arguments: dict


@dataclass(frozen=True)
class Usage:
    # Tokens de l'appel qui vient d'être fait (spec 1.1.3) — jamais un
    # cumul : chaque appel Mistral porte le sien, à tracer un par un par le
    # ticket suivant (table Consommation).
    tokens_entree: int
    tokens_sortie: int
    tokens_total: int


@dataclass(frozen=True)
class ReponseChat:
    contenu: str
    usage: Usage
    # Payload exact envoyé et réponse brute reçue (spec 1.3.0, inspecteur des
    # échanges) : capturés ici plutôt que reconstruits par l'appelant, seul
    # ce module connaît la forme exacte du payload réellement posté.
    payload_envoye: dict
    reponse_brute: dict


@dataclass(frozen=True)
class ReponseOcr:
    contenu: str
    pages_processed: int
    payload_envoye: dict
    reponse_brute: dict


class ErreurAppelMistral(Exception):
    # Lève à la place de l'exception brute (httpx, JSON malformé...) sur tout
    # échec de .chat()/.ocr() : porte le payload exact qui allait être
    # envoyé, pour que l'appelant puisse quand même tracer l'échange dans
    # l'inspecteur (spec 1.3.0) même quand aucune réponse n'a jamais été
    # obtenue. Capturé après construction du payload mais avant l'ajout de
    # l'en-tête Authorization ci-dessous : ne porte jamais la clé API.
    # `reponse_brute` : renseignée seulement quand une réponse a bien été
    # reçue mais n'a pas pu être exploitée par l'appelant (ex. sortie
    # structurée illisible de l'analyse d'image).
    def __init__(self, message: str, payload_envoye: dict, reponse_brute: dict | None = None) -> None:
        super().__init__(message)
        self.payload_envoye = payload_envoye
        self.reponse_brute = reponse_brute


class AppelOutilDemande(Exception):
    # Mistral répond par un appel d'outil plutôt qu'un contenu texte final
    # (spec 1.1.2, tool calling) : le message assistant brut est conservé
    # tel quel pour être réinjecté par l'appelant dans le second appel, comme
    # l'exige le protocole (l'API attend ce message avant le rôle `tool` qui
    # porte le résultat).
    def __init__(
        self,
        appels: list[AppelOutil],
        message_assistant: dict,
        usage: Usage,
        payload_envoye: dict,
        reponse_brute: dict,
    ) -> None:
        super().__init__("Mistral a demandé un appel d'outil")
        self.appels = appels
        self.message_assistant = message_assistant
        # L'appel qui décide d'invoquer l'outil a déjà consommé des tokens
        # (spec 1.1.3) même sans contenu texte final : à tracer au même titre
        # qu'un appel de chat normal par le ticket suivant.
        self.usage = usage
        # Spec 1.3.0 : cette demande d'outil est elle-même un échange à part
        # entière dans l'inspecteur (statut succès, Mistral a bien répondu),
        # distinct du second appel une fois le résultat de l'outil réinjecté.
        self.payload_envoye = payload_envoye
        self.reponse_brute = reponse_brute


def _usage_depuis_reponse(usage_brut: Mapping[str, int]) -> Usage:
    return Usage(
        tokens_entree=usage_brut["prompt_tokens"],
        tokens_sortie=usage_brut["completion_tokens"],
        tokens_total=usage_brut["total_tokens"],
    )


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
        tools: Sequence[Mapping[str, object]] | None = None,
    ) -> ReponseChat:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        api_key = get_mistral_api_key()
        payload: dict = {
            "model": self._modele,
            "messages": messages,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools

        try:
            reponse = _http_client.post(
                _API_URL_CHAT,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            reponse.raise_for_status()
            corps = reponse.json()
            message = corps["choices"][0]["message"]
            usage = _usage_depuis_reponse(corps["usage"])
        except Exception as erreur:
            raise ErreurAppelMistral(str(erreur), payload_envoye=payload) from erreur

        tool_calls = message.get("tool_calls")
        if tool_calls:
            appels = [
                AppelOutil(
                    id=appel["id"],
                    nom=appel["function"]["name"],
                    arguments=json.loads(appel["function"]["arguments"]),
                )
                for appel in tool_calls
            ]
            raise AppelOutilDemande(
                appels, message, usage, payload_envoye=payload, reponse_brute=corps
            )

        return ReponseChat(
            contenu=message["content"], usage=usage, payload_envoye=payload, reponse_brute=corps
        )

    def ocr(self, document: bytes, type_mime: str) -> ReponseOcr:
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

        try:
            reponse = _http_client.post(
                _API_URL_OCR,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            reponse.raise_for_status()
            corps = reponse.json()
            contenu = "\n\n".join(page["markdown"] for page in corps["pages"])
        except Exception as erreur:
            raise ErreurAppelMistral(str(erreur), payload_envoye=payload) from erreur

        return ReponseOcr(
            contenu=contenu,
            pages_processed=corps["usage_info"]["pages_processed"],
            payload_envoye=payload,
            reponse_brute=corps,
        )


def get_mistral_client() -> MistralClient:
    return MistralClient()
