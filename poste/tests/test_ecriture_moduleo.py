import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from flux_sse import evenements

from poste import config, vm_centrale_client
from poste.main import app
from poste.vm_centrale_client import (
    ConversationDetail,
    EcritureDejaDecideeError,
    EcritureIntrouvableError,
    JetonInvalideError,
    Message,
    VmCentraleClient,
    get_vm_centrale_client,
)

# Carte de confirmation d'une écriture Moduléo (spec 1.5.2, #204) : le
# poste relaie l'événement `carte`, les cartes d'une Conversation rechargée
# et le clic Confirmer / Annuler vers la VM centrale.

_CARTE = {
    "id": 7,
    "statut": "proposee",
    "methode": "POST",
    "route": "moduleo/telephone",
    "titre": "Crée un numéro de téléphone.",
    "lignes": [
        {"champ": "Contact", "valeur": "Étude Dupont", "avant": None},
        {"champ": "Numero", "valeur": "04 67 00 00 00", "avant": None},
    ],
    "rubrique": None,
    "fiche": None,
    "message": None,
}
# PUT et DELETE (#205) : différences (`avant`), puis la fiche sous « Sera
# supprimé ».
_CARTE_PUT = {
    **_CARTE,
    "id": 8,
    "methode": "PUT",
    "route": "moduleo/telephone/{idTelephone}",
    "lignes": [{"champ": "Numero", "valeur": "04 67 11 11 11", "avant": "04 67 00 00 00"}],
}
_CARTE_DELETE = {
    **_CARTE,
    "id": 9,
    "methode": "DELETE",
    "route": "cogeo/tempspasse/{idTempsPasse}",
    "lignes": [],
    "rubrique": "Sera supprimé",
    "fiche": "Temps passé du 07/10/2026\nCollaborateur : Jean Martin\nHeures : 4 h",
}
_FIN = (
    "fin",
    {
        "conversation": {"id": 1, "titre": "Téléphone"},
        "reponse": "Voici la carte.",
        "tokens_contexte": 3_000,
        "fenetre_contexte": 262_144,
    },
)
_EXPIREE = "Expirée : un nouveau message a été envoyé avant la confirmation. Rien n'a été écrit."


def _connecter(client, vm_centrale_client_factice):
    vm_centrale_client_factice.accepter()
    client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "x"})


def test_l_evenement_carte_est_relaye_dans_le_flux(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    flux = (("statut", {"libelle": "Réflexion…"}), ("carte", _CARTE), _FIN)
    vm_centrale_client_factice.creation_conversation_reussit(*flux)

    reponse = client.post("/conversations", json={"message": "Ajoute le téléphone"})

    assert evenements(reponse) == list(flux)


def test_les_cartes_sont_rechargees_avec_la_conversation(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    maintenant = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.detail_conversation_retourne(
        ConversationDetail(
            id=1,
            titre="Téléphone",
            date_creation=maintenant,
            date_derniere_activite=maintenant,
            messages=[
                Message(1, "user", "Ajoute le téléphone", maintenant, None, 262_144),
                Message(
                    2,
                    "assistant",
                    "Voici les cartes.",
                    maintenant,
                    3_000,
                    262_144,
                    cartes=[_CARTE, _CARTE_PUT, _CARTE_DELETE],
                ),
            ],
            a_des_messages_plus_anciens=False,
        )
    )

    corps = client.get("/conversations/1").json()

    assert [m["cartes"] for m in corps["messages"]] == [[], [_CARTE, _CARTE_PUT, _CARTE_DELETE]]


def test_confirmer_relaie_le_clic_et_renvoie_la_carte(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    decidee = {**_CARTE, "statut": "confirmee", "message": "Écrit dans Moduléo."}
    vm_centrale_client_factice.decision_ecriture_reussit(decidee)

    reponse = client.post("/ecritures-moduleo/7", json={"decision": "confirmer"})

    assert reponse.status_code == 200
    assert reponse.json() == decidee
    assert vm_centrale_client_factice._decisions_ecriture == [("jeton-factice", 7, "confirmer")]


def test_decision_inconnue_rejetee_sans_appeler_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/ecritures-moduleo/7", json={"decision": "oui"})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._decisions_ecriture == []


def test_carte_deja_decidee_retourne_409_avec_son_etat(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    expiree = {**_CARTE, "statut": "expiree", "message": _EXPIREE}
    vm_centrale_client_factice.decision_ecriture_echoue(EcritureDejaDecideeError(expiree))

    reponse = client.post("/ecritures-moduleo/7", json={"decision": "confirmer"})

    assert reponse.status_code == 409
    assert reponse.json()["detail"] == expiree


def test_carte_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.decision_ecriture_echoue(EcritureIntrouvableError())

    assert client.post("/ecritures-moduleo/7", json={"decision": "annuler"}).status_code == 404


def test_decision_sans_session_refusee(client, vm_centrale_client_factice):
    assert client.post("/ecritures-moduleo/7", json={"decision": "confirmer"}).status_code == 401
    assert vm_centrale_client_factice._decisions_ecriture == []


def test_decision_jeton_invalide_ferme_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.decision_ecriture_echoue(JetonInvalideError())

    assert client.post("/ecritures-moduleo/7", json={"decision": "confirmer"}).status_code == 401
    assert client.get("/compte").status_code == 401


def test_decision_vm_indisponible_retourne_502(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.decision_ecriture_echoue(httpx.ConnectError("refus"))

    assert client.post("/ecritures-moduleo/7", json={"decision": "confirmer"}).status_code == 502


@pytest.mark.parametrize("decision", ["confirmer", "annuler"])
def test_poste_installe_la_decision_atteint_le_serveur_relie(client, monkeypatch, tmp_path, decision):
    # Vrai client de la VM centrale, réseau simulé (#279) : le faux client des
    # tests ci-dessus ne voit ni l'adresse ni l'appel HTTP.
    appels: list[tuple[str, str, dict, str | None]] = []
    decidee = {**_CARTE, "statut": "annulee" if decision == "annuler" else "confirmee"}

    def repondre(requete: httpx.Request) -> httpx.Response:
        if requete.url.path == "/auth":
            return httpx.Response(
                200,
                json={
                    "prenom": "Jean",
                    "nom": "Dupont",
                    "jeton": "jeton-reel",
                    "agence": "Montpellier",
                    "poles": [],
                    "est_admin": False,
                    "doit_changer_mot_de_passe": False,
                },
            )
        appels.append(
            (requete.method, str(requete.url), json.loads(requete.content), requete.headers.get("Authorization"))
        )
        return httpx.Response(200, json=decidee)

    fichier = tmp_path / "BBASS" / "configuration.json"
    fichier.parent.mkdir()
    fichier.write_text(json.dumps({"serveur_bbass": {"hote": "10.0.0.5", "port": 8001}}), encoding="utf-8")
    monkeypatch.setattr(config, "EN_MODE_PAQUET", True)
    monkeypatch.setattr(config, "FICHIER_CONFIGURATION", fichier)
    monkeypatch.setattr(vm_centrale_client, "_http_client", httpx.Client(transport=httpx.MockTransport(repondre)))
    app.dependency_overrides[get_vm_centrale_client] = VmCentraleClient
    client.post("/connexion", json={"identifiant": "j.dupont", "mot_de_passe": "x"})

    reponse = client.post("/ecritures-moduleo/7", json={"decision": decision})

    assert reponse.status_code == 200
    assert reponse.json() == decidee
    assert appels == [
        ("POST", "http://10.0.0.5:8001/ecritures-moduleo/7", {"decision": decision}, "Bearer jeton-reel")
    ]


def test_le_client_n_utilise_jamais_l_adresse_reservee_au_developpement():
    # Garde-fou (#279) : hors de config.adresse_serveur_bbass(), cette adresse
    # ne vaut rien sur un poste installé.
    source = Path(vm_centrale_client.__file__).read_text(encoding="utf-8")

    assert "VM_CENTRALE_BASE_URL" not in source
