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
