import importlib.util
import logging
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from vm_centrale.main import app
from vm_centrale.moduleo.configuration import ConfigModuleo, config_moduleo
from vm_centrale.secrets_chiffres import SecretIndechiffrable, dechiffrer, lire_cle_maitre

# Config Moduléo chiffrée (spec 1.5.0, ADR-0017, #173) : la clé d'API et le
# SecurityCode sont chiffrés (Fernet) dans .env, la clé maître est un fichier
# hors du dépôt. Toutes les clés maîtres des tests sont générées dans tmp_path.

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "chiffrer_secret.py"
_URL = "https://moduleo.exemple.fr/api"
_API_KEY = "cle-api-bbass-0123456789"
_SECURITY_CODE = "code-utilisateur-test-9876"


def _charger_script():
    spec = importlib.util.spec_from_file_location("chiffrer_secret", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cle_maitre(tmp_path) -> Path:
    return tmp_path / "cle_maitre_moduleo.key"


@pytest.fixture
def env_moduleo(monkeypatch, cle_maitre):
    # Toutes les variables sont posées ou retirées explicitement : le .env de
    # vm-centrale/ (load_dotenv dans config.py) ne doit pas fuiter ici.
    script = _charger_script()
    monkeypatch.setenv("MODULEO_URL", _URL)
    monkeypatch.setenv("MODULEO_API_KEY_CHIFFREE", script.chiffrer(_API_KEY, cle_maitre))
    monkeypatch.setenv("MODULEO_SECURITY_CODE_CHIFFRE", script.chiffrer(_SECURITY_CODE, cle_maitre))
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(cle_maitre))
    # Même clé maître que Moduléo (spec 1.5.1) : sans elle, la VM ne démarre pas.
    monkeypatch.setenv("MISTRAL_API_KEY_CHIFFREE", script.chiffrer("cle-api-mistral", cle_maitre))
    return monkeypatch


def test_un_secret_chiffre_par_le_script_se_dechiffre(cle_maitre):
    valeur_chiffree = _charger_script().chiffrer(_API_KEY, cle_maitre)

    assert _API_KEY not in valeur_chiffree
    assert dechiffrer(valeur_chiffree, lire_cle_maitre(str(cle_maitre))) == _API_KEY


def test_le_script_cree_la_cle_maitre_une_seule_fois(cle_maitre):
    script = _charger_script()

    assert script.creer_cle_maitre_si_absente(cle_maitre) is True
    contenu = cle_maitre.read_bytes()
    assert script.creer_cle_maitre_si_absente(cle_maitre) is False
    assert cle_maitre.read_bytes() == contenu


def test_un_secret_chiffre_avec_une_autre_cle_maitre_est_refuse(cle_maitre):
    valeur_chiffree = _charger_script().chiffrer(_API_KEY, cle_maitre)

    with pytest.raises(SecretIndechiffrable):
        dechiffrer(valeur_chiffree, Fernet.generate_key())


def test_le_script_affiche_la_valeur_a_coller_dans_env(cle_maitre, monkeypatch, capsys):
    script = _charger_script()
    monkeypatch.setattr(script, "getpass", lambda invite: _SECURITY_CODE)
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(cle_maitre))

    script.main(["MODULEO_SECURITY_CODE_CHIFFRE"])

    sortie = capsys.readouterr().out
    ligne = next(ligne for ligne in sortie.splitlines() if ligne.startswith("MODULEO_SECURITY_CODE_CHIFFRE="))
    valeur_chiffree = ligne.split("=", 1)[1]
    assert dechiffrer(valeur_chiffree, lire_cle_maitre(str(cle_maitre))) == _SECURITY_CODE
    assert _SECURITY_CODE not in sortie


def test_config_complete_renvoie_les_secrets_en_clair(env_moduleo):
    assert config_moduleo() == ConfigModuleo(url=_URL, api_key=_API_KEY, security_code=_SECURITY_CODE)


def test_la_config_ne_montre_pas_les_secrets_dans_son_repr(env_moduleo):
    texte = repr(config_moduleo())

    assert _API_KEY not in texte
    assert _SECURITY_CODE not in texte


@pytest.mark.parametrize(
    "variable",
    ["MODULEO_URL", "MODULEO_API_KEY_CHIFFREE", "MODULEO_SECURITY_CODE_CHIFFRE", "VM_CLE_MAITRE_FICHIER"],
)
def test_une_variable_manquante_rend_moduleo_non_configure(env_moduleo, variable):
    env_moduleo.setenv(variable, "")

    assert config_moduleo() is None


def test_une_variable_absente_rend_moduleo_non_configure(env_moduleo):
    env_moduleo.delenv("MODULEO_API_KEY_CHIFFREE")

    assert config_moduleo() is None


def test_cle_maitre_absente_rend_moduleo_non_configure(env_moduleo, tmp_path):
    env_moduleo.setenv("VM_CLE_MAITRE_FICHIER", str(tmp_path / "absente.key"))

    assert config_moduleo() is None


def test_cle_maitre_illisible_rend_moduleo_non_configure(env_moduleo, cle_maitre):
    cle_maitre.write_text("pas une clé Fernet")

    assert config_moduleo() is None


def test_cle_maitre_fausse_rend_moduleo_non_configure(env_moduleo, cle_maitre):
    cle_maitre.write_bytes(Fernet.generate_key())

    assert config_moduleo() is None


def test_secret_chiffre_corrompu_rend_moduleo_non_configure(env_moduleo):
    env_moduleo.setenv("MODULEO_SECURITY_CODE_CHIFFRE", "pas-un-jeton-fernet")

    assert config_moduleo() is None


def test_ni_la_cle_ni_le_code_ne_vont_dans_les_logs(env_moduleo, cle_maitre, caplog):
    caplog.set_level(logging.DEBUG)

    config_moduleo()
    env_moduleo.setenv("MODULEO_SECURITY_CODE_CHIFFRE", "pas-un-jeton-fernet")
    config_moduleo()
    cle_maitre.write_bytes(Fernet.generate_key())
    config_moduleo()

    assert caplog.records
    assert _API_KEY not in caplog.text
    assert _SECURITY_CODE not in caplog.text
    assert cle_maitre.read_text() not in caplog.text


def test_la_vm_demarre_avec_un_secret_moduleo_indechiffrable(env_moduleo, caplog):
    # Une clé maître fausse empêche désormais le démarrage (clé Mistral, spec
    # 1.5.1) ; un secret Moduléo seul indéchiffrable ne l'empêche pas.
    env_moduleo.setenv("MODULEO_SECURITY_CODE_CHIFFRE", "pas-un-jeton-fernet")
    caplog.set_level(logging.INFO)

    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200

    assert "Moduléo non configuré" in caplog.text
