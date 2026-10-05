import pytest

from vm_centrale import mistral_client as mistral_client_module
from vm_centrale.mistral_client import ErreurAppelMistral, MistralClient

_CLE_API = "cle-secrete-ne-doit-jamais-fuiter"


class _ReponseHttpFactice:
    def __init__(self, corps: dict) -> None:
        self._corps = corps

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._corps


@pytest.fixture(autouse=True)
def _cle_api(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", _CLE_API)


def test_chat_payload_envoye_et_reponse_brute_ne_contiennent_jamais_la_cle_api(monkeypatch):
    appels_post = []

    def _post_factice(url, headers, json):
        appels_post.append((url, headers, json))
        return _ReponseHttpFactice(
            {
                "choices": [{"message": {"content": "Réponse"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )

    monkeypatch.setattr(mistral_client_module._http_client, "post", _post_factice)

    reponse = MistralClient().chat("Bonjour")

    # La clé part bien dans l'en-tête Authorization, séparément du payload
    # (spec 1.3.0) : vérifié pour s'assurer que les assertions suivantes
    # testent bien la bonne distinction, pas un test qui passerait de toute
    # façon faute d'appel réel.
    _, headers, _ = appels_post[0]
    assert headers["Authorization"] == f"Bearer {_CLE_API}"

    assert "Authorization" not in reponse.payload_envoye
    assert _CLE_API not in str(reponse.payload_envoye)
    assert _CLE_API not in str(reponse.reponse_brute)


def test_ocr_payload_envoye_et_reponse_brute_ne_contiennent_jamais_la_cle_api(monkeypatch):
    appels_post = []

    def _post_factice(url, headers, json):
        appels_post.append((url, headers, json))
        return _ReponseHttpFactice(
            {"pages": [{"markdown": "Texte extrait"}], "usage_info": {"pages_processed": 1}}
        )

    monkeypatch.setattr(mistral_client_module._http_client, "post", _post_factice)

    reponse = MistralClient().ocr(b"%PDF-1.4 contenu factice", "application/pdf")

    _, headers, _ = appels_post[0]
    assert headers["Authorization"] == f"Bearer {_CLE_API}"

    assert "Authorization" not in reponse.payload_envoye
    assert _CLE_API not in str(reponse.payload_envoye)
    assert _CLE_API not in str(reponse.reponse_brute)


def test_echec_chat_leve_erreur_appel_mistral_avec_le_payload_mais_sans_la_cle(monkeypatch):
    def _post_qui_echoue(url, headers, json):
        raise RuntimeError("timeout")

    monkeypatch.setattr(mistral_client_module._http_client, "post", _post_qui_echoue)

    with pytest.raises(ErreurAppelMistral) as exc_info:
        MistralClient().chat("Bonjour")

    assert "Authorization" not in exc_info.value.payload_envoye
    assert _CLE_API not in str(exc_info.value.payload_envoye)
    assert exc_info.value.payload_envoye["messages"] == [{"role": "user", "content": "Bonjour"}]
    assert "timeout" in str(exc_info.value)


def test_echec_ocr_leve_erreur_appel_mistral_avec_le_payload_mais_sans_la_cle(monkeypatch):
    def _post_qui_echoue(url, headers, json):
        raise RuntimeError("timeout")

    monkeypatch.setattr(mistral_client_module._http_client, "post", _post_qui_echoue)

    with pytest.raises(ErreurAppelMistral) as exc_info:
        MistralClient().ocr(b"%PDF-1.4 contenu factice", "application/pdf")

    assert "Authorization" not in exc_info.value.payload_envoye
    assert _CLE_API not in str(exc_info.value.payload_envoye)
