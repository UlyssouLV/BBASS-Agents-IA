import re

import pytest

from vm_centrale.exploitation import main

# `creer-admin` (spec 1.6.1, #232) : le premier compte administrateur de la
# production, créé pendant `installer`. Interactif : identifiant, prénom,
# nom, agence ; le mot de passe est généré, affiché une fois, à changer à la
# première connexion. Refuse s'il existe déjà un administrateur : la
# production n'a jamais de compte de test au mot de passe connu.


@pytest.fixture
def base_de_la_commande(monkeypatch, db_session):
    # La commande ouvre sa propre session sur la base de la VM : ici celle
    # du test (SQLite en mémoire), tables déjà créées.
    monkeypatch.setattr("vm_centrale.database.init_db", lambda: None)
    monkeypatch.setattr("vm_centrale.database.SessionLocal", lambda: db_session)


@pytest.fixture
def saisies(monkeypatch):
    def _saisies(*reponses: str) -> None:
        restantes = iter(reponses)
        monkeypatch.setattr("builtins.input", lambda _invite="": next(restantes))

    return _saisies


def test_creer_admin_cree_un_administrateur_qui_doit_changer_son_mot_de_passe(
    base_de_la_commande, saisies, client, capsys
):
    saisies("p.durand", "Paul", "Durand", "Castries")

    main(["creer-admin"])

    sortie = capsys.readouterr().out
    affiche = re.search(r"Mot de passe\s*:\s*(\S+)", sortie)
    assert affiche is not None
    mot_de_passe = affiche.group(1)
    reponse = client.post("/auth", json={"identifiant": "p.durand", "mot_de_passe": mot_de_passe})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["est_admin"] is True
    assert corps["doit_changer_mot_de_passe"] is True
    assert corps["agence"] == "Castries"
    assert corps["poles"] == ["Administration"]


def test_creer_admin_refuse_s_il_existe_deja_un_administrateur(
    base_de_la_commande, saisies, seed_compte, client, capsys
):
    seed_compte(
        "a.martin", "correcthorsebatterystaple", agence="Castries", poles=["Administration"],
        prenom="Alice", nom="Martin", est_admin=True,
    )
    saisies("p.durand", "Paul", "Durand", "Castries")

    with pytest.raises(SystemExit) as sortie:
        main(["creer-admin"])

    assert sortie.value.code != 0
    assert "administrateur existe déjà" in capsys.readouterr().err
    reponse = client.post("/auth", json={"identifiant": "p.durand", "mot_de_passe": "x"})
    assert reponse.status_code == 401
