# Cibles de dev (troisième passage de #206) : un seul .env ne pouvait pas
# tenir à la fois le serveur Moduléo du cabinet et celui de test, et passer
# de l'un à l'autre écrasait les clés. .env garde le commun ; .env.test et
# .env.cabinet, chacun son Moduléo, sa base et son port, lus par-dessus.

import importlib.util
import os
from pathlib import Path

import pytest

from vm_centrale.cibles_dev import (
    URL_CABINET,
    URL_TEST,
    charger_cible_dev,
    separer_env,
)

_ENV = (
    "VM_CENTRALE_PORT=8000\n"
    "VM_CENTRALE_DATABASE_URL=postgresql+psycopg://vm_centrale:vm_centrale@localhost:5432/vm_centrale\n"
    "MISTRAL_API_KEY_CHIFFREE=mistral-chiffree\n"
    "VM_CLE_MAITRE_FICHIER=C:/cles/cle-maitre\n"
    f"MODULEO_URL={URL_TEST}\n"
    "MODULEO_API_KEY_CHIFFREE=cle-test-chiffree\n"
    "MODULEO_SECURITY_CODE_CHIFFRE=code-test-chiffre\n"
    "MODULEO_ECRITURE=1\n"
)


def _lire(chemin) -> dict[str, str]:
    lignes = [ligne for ligne in chemin.read_text(encoding="utf-8").splitlines() if "=" in ligne and not ligne.startswith("#")]
    return dict(ligne.split("=", 1) for ligne in lignes)


@pytest.fixture
def env_sans_cible(monkeypatch):
    # Les variables lues par-dessus ne fuient pas d'un test à l'autre.
    for nom in ("BBASS_CIBLE_DEV", "MODULEO_URL", "MODULEO_ECRITURE", "VM_CENTRALE_PORT"):
        monkeypatch.delenv(nom, raising=False)
    yield
    for nom in ("MODULEO_URL", "MODULEO_ECRITURE", "VM_CENTRALE_PORT"):
        os.environ.pop(nom, None)


def test_separer_range_le_moduleo_actuel_dans_sa_cible_sans_perdre_de_cle(tmp_path):
    (tmp_path / ".env").write_text(_ENV, encoding="utf-8")

    separer_env(tmp_path)

    commun, test, cabinet = (_lire(tmp_path / nom) for nom in (".env", ".env.test", ".env.cabinet"))
    assert not any(nom.startswith("MODULEO_") for nom in commun)
    assert commun["MISTRAL_API_KEY_CHIFFREE"] == "mistral-chiffree"
    assert test["MODULEO_URL"] == URL_TEST
    assert test["MODULEO_API_KEY_CHIFFREE"] == "cle-test-chiffree"
    assert test["MODULEO_SECURITY_CODE_CHIFFRE"] == "code-test-chiffre"
    assert test["MODULEO_ECRITURE"] == "1"
    assert test["VM_CENTRALE_PORT"] == "8001"
    # La base actuelle reste au test, qui la remplit déjà.
    assert test["VM_CENTRALE_DATABASE_URL"].endswith("/vm_centrale")
    assert cabinet["MODULEO_URL"] == URL_CABINET
    assert cabinet["MODULEO_API_KEY_CHIFFREE"] == ""
    assert cabinet["MODULEO_ECRITURE"] == "0"
    assert cabinet["VM_CENTRALE_PORT"] == "8000"
    assert cabinet["VM_CENTRALE_DATABASE_URL"].endswith("/vm_centrale_cabinet")
    # Rien n'est perdu : l'ancien .env est gardé tel quel.
    assert (tmp_path / ".env.avant-cibles").read_text(encoding="utf-8") == _ENV


def test_separer_un_env_du_cabinet_le_range_au_cabinet(tmp_path):
    (tmp_path / ".env").write_text(_ENV.replace(URL_TEST, URL_CABINET).replace("MODULEO_ECRITURE=1\n", ""), encoding="utf-8")

    separer_env(tmp_path)

    test, cabinet = (_lire(tmp_path / nom) for nom in (".env.test", ".env.cabinet"))
    assert cabinet["MODULEO_API_KEY_CHIFFREE"] == "cle-test-chiffree"
    assert cabinet["VM_CENTRALE_DATABASE_URL"].endswith("/vm_centrale")
    assert test["MODULEO_API_KEY_CHIFFREE"] == ""
    assert test["VM_CENTRALE_DATABASE_URL"].endswith("/vm_centrale_test")


def test_separer_sans_base_dans_le_env_n_en_invente_pas(tmp_path):
    # Pas d'URL de base par défaut dans le code (mot de passe en clair, Sonar
    # S6698) : la VM garde sa base par défaut, la même pour les deux cibles.
    (tmp_path / ".env").write_text(_ENV.split("\n", 2)[0] + "\n" + _ENV.split("\n", 2)[2], encoding="utf-8")

    assert separer_env(tmp_path) is True

    for nom in (".env.test", ".env.cabinet"):
        assert "VM_CENTRALE_DATABASE_URL" not in _lire(tmp_path / nom)


def test_separer_une_seconde_fois_ne_touche_a_rien(tmp_path):
    (tmp_path / ".env").write_text(_ENV, encoding="utf-8")
    separer_env(tmp_path)
    (tmp_path / ".env.test").write_text("MODULEO_API_KEY_CHIFFREE=cle-rechiffree\n", encoding="utf-8")

    separer_env(tmp_path)

    assert _lire(tmp_path / ".env.test") == {"MODULEO_API_KEY_CHIFFREE": "cle-rechiffree"}


def test_la_cible_est_lue_par_dessus_le_env_commun(tmp_path, monkeypatch, env_sans_cible):
    (tmp_path / ".env.test").write_text(f"MODULEO_URL={URL_TEST}\nMODULEO_ECRITURE=1\nVM_CENTRALE_PORT=8001\n", encoding="utf-8")
    monkeypatch.setenv("MODULEO_URL", URL_CABINET)
    monkeypatch.setenv("BBASS_CIBLE_DEV", "test")

    assert charger_cible_dev(tmp_path) == "test"

    assert os.environ["MODULEO_URL"] == URL_TEST
    assert os.environ["VM_CENTRALE_PORT"] == "8001"


def test_sans_cible_rien_n_est_lu(tmp_path, env_sans_cible):
    # Staging et prod (Docker), tests : pas de BBASS_CIBLE_DEV.
    (tmp_path / ".env.test").write_text(f"MODULEO_URL={URL_TEST}\n", encoding="utf-8")

    assert charger_cible_dev(tmp_path) is None

    assert "MODULEO_URL" not in os.environ


@pytest.mark.parametrize(("cible", "attendu"), [("prod", "Cible de dev inconnue"), ("cabinet", "preparer_cible_dev.py cabinet")])
def test_cible_inconnue_ou_fichier_absent_la_vm_ne_demarre_pas(tmp_path, monkeypatch, env_sans_cible, cible, attendu):
    monkeypatch.setenv("BBASS_CIBLE_DEV", cible)

    with pytest.raises(RuntimeError, match=attendu):
        charger_cible_dev(tmp_path)


def test_preparer_une_cible_sans_url_de_base_ne_cree_rien():
    # separer_env n'écrit pas de ligne de base sans VM_CENTRALE_DATABASE_URL :
    # la VM garde sa base par défaut, le lanceur ne doit pas s'arrêter.
    chemin = Path(__file__).resolve().parents[1] / "scripts" / "preparer_cible_dev.py"
    spec = importlib.util.spec_from_file_location("preparer_cible_dev", chemin)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    assert script.creer_base("") is None
