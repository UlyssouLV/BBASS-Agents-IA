import logging

import pytest

from poste.journaux import configurer_journaux

MOT_DE_PASSE = "MotDePasse-Tres-Secret-42"
JETON = "jeton-factice"  # Jeton rendu par VmCentraleClientFactice.authentifier.


@pytest.fixture
def journaux(tmp_path):
    dossiers_et_handlers = []

    def configurer(**options):
        dossier = tmp_path / "journaux"
        dossiers_et_handlers.append(configurer_journaux(dossier, **options))
        return dossier

    yield configurer
    for handler in dossiers_et_handlers:
        logging.getLogger().removeHandler(handler)
        handler.close()


def _contenu(dossier):
    return "".join(f.read_text(encoding="utf-8") for f in sorted(dossier.iterdir()))


def test_les_requetes_sont_journalisees_sans_mot_de_passe_ni_jeton(client, vm_centrale_client_factice, journaux):
    dossier = journaux()
    vm_centrale_client_factice.accepter()

    client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": MOT_DE_PASSE})
    client.get("/compte")
    client.post("/deconnexion")

    contenu = _contenu(dossier)
    assert "POST /connexion 200" in contenu
    assert "GET /compte 200" in contenu
    assert "POST /deconnexion 204" in contenu
    assert MOT_DE_PASSE not in contenu
    assert JETON not in contenu


def test_le_journal_ne_reprend_pas_la_chaine_de_requete(client, journaux):
    dossier = journaux()

    client.get("/compte?jeton=secret-dans-l-url")

    contenu = _contenu(dossier)
    assert "GET /compte 401" in contenu
    assert "secret-dans-l-url" not in contenu


def test_les_journaux_tournent_sans_depasser_leur_taille(client, journaux):
    dossier = journaux(taille_max=2_000, archives=2)

    for _ in range(200):
        client.get("/compte")

    fichiers = list(dossier.iterdir())
    assert len(fichiers) == 3
    assert all(f.stat().st_size <= 2_000 for f in fichiers)
