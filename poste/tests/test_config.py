import json
import sys
import importlib

from poste import config


def test_vm_centrale_base_url_est_lue_depuis_la_configuration(monkeypatch):
    monkeypatch.setenv("VM_CENTRALE_BASE_URL", "http://vm-centrale.interne:9000")

    importlib.reload(config)
    try:
        assert config.VM_CENTRALE_BASE_URL == "http://vm-centrale.interne:9000"
    finally:
        monkeypatch.delenv("VM_CENTRALE_BASE_URL", raising=False)
        importlib.reload(config)


def test_vm_centrale_base_url_ignore_un_slash_final(monkeypatch):
    monkeypatch.setenv("VM_CENTRALE_BASE_URL", "http://vm-centrale.interne:9000/")

    importlib.reload(config)
    try:
        assert config.VM_CENTRALE_BASE_URL == "http://vm-centrale.interne:9000"
    finally:
        monkeypatch.delenv("VM_CENTRALE_BASE_URL", raising=False)
        importlib.reload(config)


def _recharger_en_mode_paquet(monkeypatch, local_app_data):
    # Mode paquet = backend figé par PyInstaller (sys.frozen), lancé par le Lanceur.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    importlib.reload(config)


def test_en_mode_paquet_l_adresse_du_serveur_bbass_vient_du_fichier_de_configuration(monkeypatch, tmp_path):
    (tmp_path / "BBASS").mkdir()
    (tmp_path / "BBASS" / "configuration.json").write_text(
        json.dumps({"serveur_bbass": {"hote": "10.0.0.5", "port": 8000}}), encoding="utf-8"
    )
    monkeypatch.setenv("VM_CENTRALE_BASE_URL", "http://ignore-en-mode-paquet:1")

    _recharger_en_mode_paquet(monkeypatch, tmp_path)
    try:
        assert config.VM_CENTRALE_BASE_URL == "http://10.0.0.5:8000"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_en_mode_paquet_sans_fichier_de_configuration_l_adresse_par_defaut_s_applique(monkeypatch, tmp_path):
    _recharger_en_mode_paquet(monkeypatch, tmp_path)
    try:
        assert config.VM_CENTRALE_BASE_URL == "http://localhost:8000"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
