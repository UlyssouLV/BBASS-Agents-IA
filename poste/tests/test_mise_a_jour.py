import json

import pytest

from poste import config

# Écrit par le Lanceur à chaque lancement (lanceur/coeur/src/mise_a_jour.rs).
_ECHEC = {
    "date": "2026-10-28T09:00:00+01:00",
    "version_poste": "1.6.2",
    "version_serveur": "1.6.3",
    "resultat": "echec",
    "detail": "Paquet poste v1.6.3 refusé : signature invalide.",
    "bandeau": "Mise à jour vers v1.6.3 impossible : certaines fonctionnalités peuvent ne pas fonctionner "
    "tant qu'elle n'a pas réussi. Nouvel essai au prochain lancement.",
}


@pytest.fixture
def fichier_etat(monkeypatch, tmp_path):
    chemin = tmp_path / "BBASS" / "mise-a-jour.json"
    monkeypatch.setattr(config, "FICHIER_ETAT_MISE_A_JOUR", chemin)
    monkeypatch.setattr(config, "EN_MODE_PAQUET", True)
    return chemin


def _ecrire(chemin, contenu):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")


def test_la_derniere_verification_du_lanceur_est_servie_avec_son_bandeau(client, fichier_etat):
    _ecrire(fichier_etat, json.dumps(_ECHEC))

    reponse = client.get("/mise-a-jour")

    assert reponse.status_code == 200
    assert reponse.json() == _ECHEC


def test_un_poste_a_jour_n_a_pas_de_bandeau(client, fichier_etat):
    _ecrire(fichier_etat, json.dumps({**_ECHEC, "version_serveur": "1.6.2", "resultat": "a_jour", "bandeau": None}))

    reponse = client.get("/mise-a-jour")

    assert reponse.status_code == 200
    assert reponse.json()["resultat"] == "a_jour"
    assert reponse.json()["bandeau"] is None


def test_sans_verification_du_lanceur_la_reponse_est_vide(client, fichier_etat):
    reponse = client.get("/mise-a-jour")

    assert reponse.status_code == 200
    assert reponse.json() is None


def test_un_fichier_d_etat_illisible_ne_casse_pas_l_application(client, fichier_etat):
    _ecrire(fichier_etat, "{pas du json")

    reponse = client.get("/mise-a-jour")

    assert reponse.status_code == 200
    assert reponse.json() is None


def test_en_dev_le_fichier_d_un_poste_installe_est_ignore(client, fichier_etat, monkeypatch):
    # lancer-logiciel.* : aucun Lanceur, le bandeau d'un BBASS installé sur la même machine ne concerne pas ce poste.
    _ecrire(fichier_etat, json.dumps(_ECHEC))
    monkeypatch.setattr(config, "EN_MODE_PAQUET", False)

    reponse = client.get("/mise-a-jour")

    assert reponse.status_code == 200
    assert reponse.json() is None
