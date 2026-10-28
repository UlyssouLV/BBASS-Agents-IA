from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from vm_centrale.config import get_mistral_api_key, get_vm_admin_key
from vm_centrale.exploitation import main
from vm_centrale.main import app
from vm_centrale.moduleo.configuration import config_moduleo

# `installer <env>` et `configurer-secret <env> <VARIABLE>` (spec 1.6.1,
# ADR-0021, #232), lancés par `docker run … installer <env>` avec la racine
# de l'hôte montée (BBASS_RACINE_HOTE) : ici un dossier temporaire. Docker
# et systemd sont simulés : les commandes passées à l'hôte sont relevées.

CLE_MISTRAL = "cle-mistral-saisie-0123456789"
CLE_MODULEO = "cle-moduleo-saisie-abcdef"
SECURITY_CODE = "security-code-saisi-987654"


@pytest.fixture
def racine(monkeypatch, tmp_path) -> Path:
    monkeypatch.setenv("BBASS_RACINE_HOTE", str(tmp_path))
    return tmp_path


@pytest.fixture
def hote(monkeypatch) -> list[list[str]]:
    commandes: list[list[str]] = []
    monkeypatch.setattr("vm_centrale.installation.executer_sur_hote", commandes.append)
    return commandes


@pytest.fixture
def saisies_masquees(monkeypatch):
    def _saisies(*reponses: str) -> None:
        restantes = iter(reponses)
        monkeypatch.setattr("vm_centrale.installation.getpass", lambda _invite="": next(restantes))

    return _saisies


def _installer(environnement: str, saisies_masquees, *secrets: str) -> None:
    saisies_masquees(*(secrets or (CLE_MISTRAL, CLE_MODULEO, SECURITY_CODE)))
    main(["installer", environnement])


def _env(racine: Path, environnement: str) -> dict[str, str | None]:
    return dotenv_values(racine / "opt" / "bbass" / environnement / ".env")


def _charger_env(monkeypatch, racine: Path, environnement: str) -> None:
    # Ce que voit le conteneur de la VM : le .env de l'Environnement, et la
    # clé maître montée au chemin de l'hôte (ici, sous la racine).
    for nom, valeur in _env(racine, environnement).items():
        monkeypatch.setenv(nom, valeur or "")
    cle_maitre = racine / (_env(racine, environnement)["VM_CLE_MAITRE_FICHIER"] or "").lstrip("/")
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(cle_maitre))


def _fichiers(racine: Path) -> list[Path]:
    return [chemin for chemin in racine.rglob("*") if chemin.is_file()]


def test_installer_cree_l_environnement_et_la_vm_dechiffre_les_cles_saisies(
    racine, hote, saisies_masquees, monkeypatch
):
    _installer("staging", saisies_masquees)

    dossier = racine / "opt" / "bbass" / "staging"
    assert (dossier / "compose.yml").is_file()
    assert (dossier / "donnees" / "pieces_jointes").is_dir()
    assert (dossier / "sauvegardes").is_dir()
    assert (racine / "etc" / "bbass" / "staging" / "cle-maitre").is_file()
    _charger_env(monkeypatch, racine, "staging")
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
    assert get_mistral_api_key() == CLE_MISTRAL
    moduleo = config_moduleo()
    assert moduleo is not None
    assert (moduleo.api_key, moduleo.security_code) == (CLE_MODULEO, SECURITY_CODE)


def test_aucune_cle_saisie_n_est_ecrite_en_clair(racine, hote, saisies_masquees):
    _installer("staging", saisies_masquees)

    for fichier in _fichiers(racine):
        contenu = fichier.read_bytes()
        for secret in (CLE_MISTRAL, CLE_MODULEO, SECURITY_CODE):
            assert secret.encode() not in contenu, fichier


def test_moduleo_laisse_vide_la_vm_demarre_sans_moduleo(racine, hote, saisies_masquees, monkeypatch):
    _installer("staging", saisies_masquees, CLE_MISTRAL, "", "")

    _charger_env(monkeypatch, racine, "staging")
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
    assert config_moduleo() is None


def test_la_cle_mistral_vide_est_redemandee(racine, hote, saisies_masquees, monkeypatch):
    _installer("staging", saisies_masquees, "", CLE_MISTRAL, "", "")

    _charger_env(monkeypatch, racine, "staging")
    assert get_mistral_api_key() == CLE_MISTRAL


def test_staging_et_prod_sont_deux_environnements_separes(racine, hote, saisies_masquees):
    _installer("staging", saisies_masquees)
    _installer("prod", saisies_masquees)

    staging, prod = _env(racine, "staging"), _env(racine, "prod")
    assert (staging["BBASS_ENVIRONNEMENT"], staging["BBASS_ETIQUETTE"], staging["VM_PORT_HOTE"]) == (
        "staging", "staging", "8001",
    )
    assert (prod["BBASS_ENVIRONNEMENT"], prod["BBASS_ETIQUETTE"], prod["VM_PORT_HOTE"]) == ("prod", "prod", "8000")
    assert staging["VM_CLE_MAITRE_FICHIER"] == "/etc/bbass/staging/cle-maitre"
    assert prod["VM_CLE_MAITRE_FICHIER"] == "/etc/bbass/prod/cle-maitre"
    cle_staging = (racine / "etc" / "bbass" / "staging" / "cle-maitre").read_bytes()
    cle_prod = (racine / "etc" / "bbass" / "prod" / "cle-maitre").read_bytes()
    assert cle_staging != cle_prod
    for nom in ("POSTGRES_PASSWORD", "VM_ADMIN_KEY"):
        assert staging[nom] != prod[nom]


def test_installer_cree_l_admin_puis_pose_et_demarre_le_service(racine, hote, saisies_masquees):
    _installer("prod", saisies_masquees)

    unite = racine / "etc" / "systemd" / "system" / "bbass-vm-prod.service"
    assert "WorkingDirectory=/opt/bbass/prod" in unite.read_text()
    creer_admin = ["docker", "compose", "--project-directory", "/opt/bbass/prod", "run", "--rm", "vm-centrale",
                   "creer-admin"]
    demarrage = ["systemctl", "enable", "--now", "bbass-vm-prod.service"]
    assert creer_admin in hote and demarrage in hote
    assert hote.index(creer_admin) < hote.index(demarrage)


def test_les_valeurs_generees_sont_affichees_meme_si_le_premier_demarrage_echoue(
    racine, saisies_masquees, monkeypatch, capsys
):
    def hote(commande: list[str]) -> None:
        if commande[:3] == ["systemctl", "enable", "--now"]:
            raise SystemExit(1)

    monkeypatch.setattr("vm_centrale.installation.executer_sur_hote", hote)

    with pytest.raises(SystemExit):
        _installer("staging", saisies_masquees)

    sortie = capsys.readouterr().out
    env = _env(racine, "staging")
    cle_maitre = (racine / "etc" / "bbass" / "staging" / "cle-maitre").read_text().strip()
    for valeur in (env["POSTGRES_PASSWORD"], env["VM_ADMIN_KEY"], cle_maitre):
        assert valeur and sortie.count(valeur) == 1
    _charger_env(monkeypatch, racine, "staging")
    assert get_vm_admin_key() == env["VM_ADMIN_KEY"]


def test_installer_refuse_un_environnement_deja_installe(racine, hote, saisies_masquees):
    _installer("staging", saisies_masquees)
    avant = {fichier: fichier.read_bytes() for fichier in _fichiers(racine)}
    hote.clear()

    with pytest.raises(SystemExit) as sortie:
        _installer("staging", saisies_masquees)

    assert sortie.value.code != 0
    assert {fichier: fichier.read_bytes() for fichier in _fichiers(racine)} == avant
    assert hote == []


def test_configurer_secret_remplace_une_cle_relue_par_la_vm(racine, hote, saisies_masquees, monkeypatch):
    _installer("staging", saisies_masquees)
    saisies_masquees("nouvelle-cle-mistral-42")

    main(["configurer-secret", "staging", "MISTRAL_API_KEY_CHIFFREE"])

    assert b"nouvelle-cle-mistral-42" not in (racine / "opt" / "bbass" / "staging" / ".env").read_bytes()
    _charger_env(monkeypatch, racine, "staging")
    assert get_mistral_api_key() == "nouvelle-cle-mistral-42"
    # La VM seule, sur ses images en service : jamais `mettre-a-jour`.
    assert ["docker", "compose", "--project-directory", "/opt/bbass/staging", "up", "-d", "vm-centrale"] in hote
    assert not any("restart" in commande for commande in hote)


def test_configurer_secret_garde_les_autres_valeurs(racine, hote, saisies_masquees):
    _installer("staging", saisies_masquees)
    avant = _env(racine, "staging")
    saisies_masquees("nouveau-security-code")

    main(["configurer-secret", "staging", "MODULEO_SECURITY_CODE_CHIFFRE"])

    apres = _env(racine, "staging")
    assert apres.pop("MODULEO_SECURITY_CODE_CHIFFRE") != avant.pop("MODULEO_SECURITY_CODE_CHIFFRE")
    assert apres == avant


def test_configurer_secret_refuse_un_environnement_non_installe(racine, hote, saisies_masquees):
    saisies_masquees("cle")

    with pytest.raises(SystemExit) as sortie:
        main(["configurer-secret", "prod", "MISTRAL_API_KEY_CHIFFREE"])

    assert sortie.value.code != 0
    assert _fichiers(racine) == []


def test_installer_laisse_les_taches_planifiees_au_premier_demarrage(racine, hote, saisies_masquees):
    # Posées par le `mettre-a-jour` du service, depuis l'image déployée
    # (test_mettre_a_jour) : jamais deux fois, ni depuis une autre image.
    _installer("staging", saisies_masquees)

    assert not list((racine / "etc" / "systemd" / "system").glob("bbass-staging-*"))
    assert not any(commande[-1].endswith(".timer") for commande in hote)
