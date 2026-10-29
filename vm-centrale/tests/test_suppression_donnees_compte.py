from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from flux_sse import fin

from vm_centrale.database import init_db
from vm_centrale.models import (
    Compte,
    Consommation,
    Conversation,
    EchangeInspecteur,
    EvenementJournalModuleo,
    Message,
    PieceJointe,
    ProfilTravail,
    RattachementModuleo,
)
from vm_centrale.moduleo.droits import charger_catalogue

# Supprimer un compte supprime ses données (spec 1.6.3, #161) : un compte
# recréé avec le même identifiant repart de zéro. La consommation reste,
# sous « Compte supprimé » ; le journal Moduléo n'est pas touché.

_CLE_ADMIN = "cle-admin-de-test"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


@pytest.fixture
def repertoire_pieces_jointes(tmp_path, monkeypatch):
    monkeypatch.setattr("vm_centrale.routers.conversations.PIECES_JOINTES_DIR", str(tmp_path))
    monkeypatch.setattr("vm_centrale.routers.comptes.PIECES_JOINTES_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def admin(client, seed_compte, jeton_store, db_session, monkeypatch):
    monkeypatch.setenv("VM_ADMIN_KEY", _CLE_ADMIN)
    charger_catalogue(db_session)
    db_session.commit()
    seed_compte("a.martin", "secret", "Castries", ["Foncier"], "Alice", "Martin", est_admin=True)
    return {**_autorisation(jeton_store.emettre("a.martin")), "X-Admin-Key": _CLE_ADMIN}


def _remplir_compte(client, mistral_client_factice, jeton_store, db_session, admin, identifiant: str) -> dict:
    """Donne au compte une conversation avec pièce jointe, une pièce jointe
    hors conversation, un profil, un rattachement Moduléo ; renvoie les
    chemins des fichiers de pièces jointes."""
    jeton = _autorisation(jeton_store.emettre(identifiant))

    mistral_client_factice.repondre("Réponse assistant", "Titre")
    conversation_id = fin(client.post("/conversations", json={"message": "Bonjour"}, headers=jeton))[
        "conversation"
    ]["id"]
    mistral_client_factice.repondre_ocr("Texte extrait du PDF")
    dans_conversation = client.post(
        f"/conversations/{conversation_id}/pieces-jointes",
        files={"fichier": ("plan.pdf", b"%PDF-1.4 plan", "application/pdf")},
        headers=jeton,
    ).json()["piece_jointe"]["id"]
    mistral_client_factice.repondre_ocr("Texte extrait du PDF")
    hors_conversation = client.post(
        "/pieces-jointes",
        files={"fichier": ("devis.pdf", b"%PDF-1.4 devis", "application/pdf")},
        headers=jeton,
    ).json()["piece_jointe"]["id"]

    db_session.merge(
        ProfilTravail(identifiant_compte=identifiant, contenu="Géomètre", date_derniere_maj=datetime.now(timezone.utc))
    )
    db_session.commit()
    (cogeo,) = [
        g["id"]
        for g in client.get("/moduleo/groupes", headers=admin).json()
        if (g["application"], g["nom"]) == ("cogeo", "Admin")
    ]
    client.patch(f"/moduleo/rattachements/{identifiant}", json={"groupe_cogeo_id": cogeo}, headers=admin)

    return {
        identifiant_pj: db_session.get(PieceJointe, identifiant_pj).chemin_fichier
        for identifiant_pj in (dans_conversation, hors_conversation)
    }


def _compter(db_session, modele, identifiant: str) -> int:
    return db_session.query(modele).filter(modele.identifiant_compte == identifiant).count()


def _cout(db_session, identifiant: str) -> Decimal:
    return db_session.scalar(
        select(func.coalesce(func.sum(Consommation.cout_usd), 0)).where(Consommation.identifiant_compte == identifiant)
    )


def test_un_compte_supprime_puis_recree_ne_retrouve_aucune_donnee(
    client, mistral_client_factice, jeton_store, seed_compte, db_session, admin, repertoire_pieces_jointes
):
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")
    fichiers = _remplir_compte(client, mistral_client_factice, jeton_store, db_session, admin, "n.durand")
    assert all((repertoire_pieces_jointes / chemin).exists() for chemin in fichiers.values())
    assert _compter(db_session, EchangeInspecteur, "n.durand") > 0
    journal_avant = db_session.query(EvenementJournalModuleo).count()

    assert client.delete("/comptes/n.durand", headers=admin).status_code == 204
    recree = client.post(
        "/comptes",
        json={"identifiant": "n.durand", "prenom": "Nadia", "nom": "Durand", "agence": "Castries", "poles": ["Foncier"]},
        headers=admin,
    )
    assert recree.status_code == 201

    jeton = _autorisation(jeton_store.emettre("n.durand"))
    assert client.get("/conversations", headers=jeton).json() == []
    assert client.get("/comptes/n.durand/profil-travail", headers=jeton).json()["contenu"] == ""
    (rattachement,) = [r for r in client.get("/moduleo/rattachements", headers=admin).json() if r["identifiant"] == "n.durand"]
    assert rattachement["groupe_cogeo_id"] is None
    for identifiant_pj, chemin in fichiers.items():
        assert db_session.get(PieceJointe, identifiant_pj) is None
        assert not (repertoire_pieces_jointes / chemin).exists()
    for modele in (Conversation, PieceJointe, EchangeInspecteur, ProfilTravail, RattachementModuleo):
        assert _compter(db_session, modele, "n.durand") == 0
    assert db_session.query(Message).count() == 0
    assert db_session.query(EvenementJournalModuleo).count() == journal_avant


def test_la_consommation_d_un_compte_supprime_reste_sous_compte_supprime(
    client, mistral_client_factice, jeton_store, seed_compte, db_session, admin, repertoire_pieces_jointes
):
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")
    _remplir_compte(client, mistral_client_factice, jeton_store, db_session, admin, "n.durand")
    cout_total = db_session.scalar(select(func.sum(Consommation.cout_usd)))
    cout_durand = _cout(db_session, "n.durand")
    assert cout_durand > 0

    client.delete("/comptes/n.durand", headers=admin)
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")

    assert _cout(db_session, "n.durand") == 0
    assert db_session.scalar(select(func.sum(Consommation.cout_usd))) == cout_total
    comptes = client.get("/comptes/consommation", headers=admin).json()
    (supprime,) = [c for c in comptes if (c["prenom"], c["nom"]) == ("Compte", "supprimé")]
    assert Decimal(supprime["cout_usd"]) == cout_durand
    assert "n.durand" not in {c["identifiant"] for c in comptes}


def test_supprimer_un_compte_ne_touche_pas_aux_donnees_d_un_autre_compte(
    client, mistral_client_factice, jeton_store, seed_compte, db_session, admin, repertoire_pieces_jointes
):
    seed_compte("n.durand", "secret", "Castries", ["Foncier"], "Nadia", "Durand")
    seed_compte("p.leroy", "secret", "Castries", ["DAO"], "Paul", "Leroy")
    _remplir_compte(client, mistral_client_factice, jeton_store, db_session, admin, "n.durand")
    fichiers_leroy = _remplir_compte(client, mistral_client_factice, jeton_store, db_session, admin, "p.leroy")
    avant = {modele: _compter(db_session, modele, "p.leroy") for modele in (Conversation, PieceJointe, EchangeInspecteur)}
    cout_leroy = _cout(db_session, "p.leroy")

    client.delete("/comptes/n.durand", headers=admin)

    assert {modele: _compter(db_session, modele, "p.leroy") for modele in avant} == avant
    assert _compter(db_session, ProfilTravail, "p.leroy") == 1
    assert _compter(db_session, RattachementModuleo, "p.leroy") == 1
    assert _cout(db_session, "p.leroy") == cout_leroy
    assert all((repertoire_pieces_jointes / chemin).exists() for chemin in fichiers_leroy.values())


def test_le_refus_de_supprimer_le_dernier_administrateur_ne_supprime_aucune_donnee(
    client, mistral_client_factice, jeton_store, db_session, admin, repertoire_pieces_jointes
):
    fichiers = _remplir_compte(client, mistral_client_factice, jeton_store, db_session, admin, "a.martin")

    assert client.delete("/comptes/a.martin", headers=admin).status_code == 409

    assert _compter(db_session, Conversation, "a.martin") == 1
    assert _compter(db_session, PieceJointe, "a.martin") == 2
    assert _compter(db_session, ProfilTravail, "a.martin") == 1
    assert _compter(db_session, RattachementModuleo, "a.martin") == 1
    assert all((repertoire_pieces_jointes / chemin).exists() for chemin in fichiers.values())


# --- Nettoyage au démarrage --------------------------------------------------


def test_le_demarrage_nettoie_les_donnees_orphelines_et_un_second_demarrage_n_a_aucun_effet(
    tmp_path, monkeypatch
):
    dossier = tmp_path / "pieces_jointes"
    dossier.mkdir()
    monkeypatch.setattr("vm_centrale.database.PIECES_JOINTES_DIR", str(dossier))
    engine = create_engine(f"sqlite:///{tmp_path / 'vm.db'}")
    init_db(engine)
    maintenant = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(Compte(identifiant="p.leroy", mot_de_passe_hash="x", prenom="Paul", nom="Leroy", agence="Castries"))
        for identifiant in ("p.leroy", "n.durand"):
            conversation = Conversation(
                identifiant_compte=identifiant, titre="T", date_creation=maintenant, date_derniere_activite=maintenant
            )
            db.add(conversation)
            db.flush()
            db.add(Message(conversation_id=conversation.id, role="user", contenu="Bonjour", date_creation=maintenant))
            (dossier / f"{identifiant}.pdf").write_bytes(b"%PDF")
            db.add(
                PieceJointe(
                    identifiant_compte=identifiant, conversation_id=None, nom_fichier="a.pdf",
                    type_mime="application/pdf", taille_octets=4, chemin_fichier=f"{identifiant}.pdf",
                    date_creation=maintenant,
                )
            )
            db.add(ProfilTravail(identifiant_compte=identifiant, contenu="Profil", date_derniere_maj=maintenant))
            db.add(RattachementModuleo(identifiant_compte=identifiant))
            db.add(
                EchangeInspecteur(
                    identifiant_compte=identifiant, conversation_id=None, origine="mistral", type_appel="chat",
                    modele="m", requete_payload={}, statut="succes", date_creation=maintenant,
                )
            )
            db.add(
                Consommation(
                    identifiant_compte=identifiant, conversation_id=conversation.id, type_appel="chat", modele="m",
                    tokens_entree=1, tokens_sortie=1, tokens_total=2, cout_usd=Decimal("1.00"), date_creation=maintenant,
                )
            )
        db.add(
            EvenementJournalModuleo(date=maintenant, identifiant_admin="n.durand", action="Rattachement", cible="n.durand")
        )
        db.commit()

    init_db(engine)

    def etat() -> dict:
        with Session(engine) as db:
            return {
                modele.__name__: sorted(ligne.identifiant_compte for ligne in db.query(modele))
                for modele in (Conversation, PieceJointe, ProfilTravail, RattachementModuleo, EchangeInspecteur, Consommation)
            } | {
                "messages": db.query(Message).count(),
                "journal": db.query(EvenementJournalModuleo).count(),
                "fichiers": sorted(f.name for f in dossier.iterdir()),
            }

    apres_premier = etat()
    assert apres_premier == {
        "Conversation": ["p.leroy"],
        "PieceJointe": ["p.leroy"],
        "ProfilTravail": ["p.leroy"],
        "RattachementModuleo": ["p.leroy"],
        "EchangeInspecteur": ["p.leroy"],
        "Consommation": ["", "p.leroy"],
        "messages": 1,
        "journal": 1,
        "fichiers": ["p.leroy.pdf"],
    }

    init_db(engine)

    assert etat() == apres_premier
