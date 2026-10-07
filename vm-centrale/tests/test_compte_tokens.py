from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from vm_centrale.config import FICHES_MODELES, MODELE_CHAT
from vm_centrale.main import app

# Tokenizer local (spec 1.4.2) : chargé au démarrage pour chaque fiche de
# modèle qui en déclare un.


def test_la_vm_demarre_avec_le_tokenizer_de_la_fiche_chat():
    assert FICHES_MODELES[MODELE_CHAT].fichier_tokenizer is not None
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200


def test_la_vm_refuse_de_demarrer_si_le_tokenizer_dune_fiche_manque(monkeypatch):
    fiche = replace(FICHES_MODELES[MODELE_CHAT], fichier_tokenizer="absent/tekken.json")
    monkeypatch.setitem(FICHES_MODELES, MODELE_CHAT, fiche)

    with pytest.raises(Exception):
        with TestClient(app):
            pass
