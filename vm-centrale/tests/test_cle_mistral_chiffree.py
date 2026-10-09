import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from conftest import CLE_API_MISTRAL_DE_TEST

from vm_centrale.config import CleMistralInutilisable
from vm_centrale.main import app

# Clé Mistral chiffrée (spec 1.5.1, ADR-0018, #186) : MISTRAL_API_KEY_CHIFFREE,
# Fernet, même clé maître que Moduléo (VM_CLE_MAITRE_FICHIER). Sans clé
# utilisable, la VM refuse de démarrer, avec un message qui nomme la variable
# en cause et jamais une valeur. La fixture `_cle_mistral_chiffree` du
# conftest pose une clé valide avant chaque test.


def _demarrage_refuse() -> str:
    with pytest.raises(CleMistralInutilisable) as erreur:
        with TestClient(app):
            pass
    return str(erreur.value)


def test_la_vm_demarre_avec_la_cle_mistral_chiffree():
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("variable", ["MISTRAL_API_KEY_CHIFFREE", "VM_CLE_MAITRE_FICHIER"])
def test_la_vm_refuse_de_demarrer_si_une_variable_manque(monkeypatch, variable):
    monkeypatch.setenv(variable, "")

    assert variable in _demarrage_refuse()


def test_la_vm_refuse_de_demarrer_si_la_cle_mistral_est_absente(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY_CHIFFREE")

    assert "MISTRAL_API_KEY_CHIFFREE" in _demarrage_refuse()


def test_la_vm_refuse_de_demarrer_si_le_fichier_de_cle_maitre_est_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(tmp_path / "absente.key"))

    assert "VM_CLE_MAITRE_FICHIER" in _demarrage_refuse()


def test_la_vm_refuse_de_demarrer_si_la_cle_maitre_est_fausse(monkeypatch, tmp_path):
    fausse = tmp_path / "fausse.key"
    fausse.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(fausse))

    message = _demarrage_refuse()

    assert "MISTRAL_API_KEY_CHIFFREE" in message
    assert fausse.read_text() not in message


def test_la_vm_refuse_de_demarrer_si_la_cle_maitre_nest_pas_une_cle_fernet(monkeypatch, tmp_path):
    illisible = tmp_path / "illisible.key"
    illisible.write_text("pas une clé Fernet")
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(illisible))

    assert "MISTRAL_API_KEY_CHIFFREE" in _demarrage_refuse()


def test_la_vm_refuse_de_demarrer_si_la_cle_mistral_est_corrompue(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY_CHIFFREE", "pas-un-jeton-fernet")

    message = _demarrage_refuse()

    assert "MISTRAL_API_KEY_CHIFFREE" in message
    assert "pas-un-jeton-fernet" not in message


def test_mistral_api_key_en_clair_est_ignoree(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY_CHIFFREE")
    monkeypatch.setenv("MISTRAL_API_KEY", "cle-en-clair-ignoree")

    message = _demarrage_refuse()

    assert "MISTRAL_API_KEY_CHIFFREE" in message
    assert "cle-en-clair-ignoree" not in message
    assert CLE_API_MISTRAL_DE_TEST not in message
