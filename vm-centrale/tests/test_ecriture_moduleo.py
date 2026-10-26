import json

import pytest

from faux_moduleo import FauxModuleo
from flux_sse import evenements, fin

from vm_centrale.main import app
from vm_centrale.moduleo.client import ClientModuleo, get_client_moduleo
from vm_centrale.models import EchangeInspecteur, EcritureModuleo, GroupeModuleo
from vm_centrale.moduleo.client import (
    ModuleoDonneesRefusees,
    ModuleoIndisponible,
    ModuleoIntrouvable,
    ModuleoRefuse,
)
from vm_centrale.moduleo.droits import GROUPE_DEV, PLANNING, rattacher

# Écrire dans Moduléo depuis le chat (spec 1.5.2, #204, ADR-0019) : le
# modèle propose une écriture (`ecrire_moduleo`), rien ne part ; le
# collaborateur la confirme ou l'annule par la Carte de confirmation, hors
# du modèle, et la VM l'envoie alors une seule fois au serveur de test.

_DECRIRE = "decrire_ecriture_moduleo"
_ECRIRE = "ecrire_moduleo"
_TELEPHONE = "POST moduleo/telephone"
_CORPS_TELEPHONE = {"IdContact": 40, "Numero": "04 67 00 00 00", "Lieu": "Bureau"}
_PROPOSEE = "Écriture proposée au collaborateur, en attente de sa confirmation. Rien n'a été écrit."


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


@pytest.fixture
def ecriture_active(monkeypatch):
    monkeypatch.setenv("MODULEO_ECRITURE", "1")


def _noms_outils(mistral_client_factice, appel: int = 0) -> set[str]:
    return {outil["function"]["name"] for outil in mistral_client_factice.tools_appels_reponse[appel] or []}


def _demander(client, mistral_client_factice, jeton: str, message: str = "Bonjour"):
    mistral_client_factice.repondre("Bonjour.", "Titre")
    return client.post("/conversations", json={"message": message}, headers=_autorisation(jeton))


def _proposer(client, mistral_client_factice, jeton: str, *appels: dict, reponse: str = "Voici la carte."):
    # Un tour qui appelle ecrire_moduleo une fois par élément de `appels`
    # (arguments de l'outil), dans la même réponse du modèle.
    mistral_client_factice.repondre_avec_appels_outils([(_ECRIRE, arguments, "") for arguments in appels])
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Ajoute le téléphone du bureau"}, headers=_autorisation(jeton)
    )


def _telephone(**corps) -> dict:
    return {"route": _TELEPHONE, "parametres": {}, "corps": {**_CORPS_TELEPHONE, **corps}}


def _cartes(reponse) -> list[dict]:
    return [donnees for nom, donnees in evenements(reponse) if nom == "carte"]


# Barrière : outils proposés seulement sur un serveur de test, réglage actif,
# compte avec au moins une route d'écriture.


def test_outils_d_ecriture_absents_sans_moduleo_ecriture(client, faux_moduleo, mistral_client_factice, jeton_valide):
    _demander(client, mistral_client_factice, jeton_valide)

    noms = _noms_outils(mistral_client_factice)
    assert "chercher_affaires_moduleo" in noms
    assert {_DECRIRE, _ECRIRE}.isdisjoint(noms)


def test_outils_d_ecriture_absents_hors_serveur_de_test(
    client, compte_tous_droits_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    faux = FauxModuleo(url="https://mwa-bbass.kipaware.fr/api")
    app.dependency_overrides[get_client_moduleo] = lambda: ClientModuleo(faux)

    _demander(client, mistral_client_factice, jeton_valide)

    assert {_DECRIRE, _ECRIRE}.isdisjoint(_noms_outils(mistral_client_factice))


def test_outils_d_ecriture_absents_sans_aucune_route_d_ecriture_autorisee(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    # Un groupe Planning seul, sans droit : aucune route d'écriture du
    # planning n'est `groupe_planning`.
    db_session.add(GroupeModuleo(application=PLANNING, nom="Lecture"))
    db_session.flush()
    rattacher(db_session, "j.dupont", None, "Lecture", None)
    db_session.commit()

    _demander(client, mistral_client_factice, jeton_valide)

    noms = _noms_outils(mistral_client_factice)
    assert "chercher_planning_moduleo" in noms
    assert {_DECRIRE, _ECRIRE}.isdisjoint(noms)


def test_outils_d_ecriture_proposes_barriere_ouverte_avec_un_droit(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _demander(client, mistral_client_factice, jeton_valide)

    assert {_DECRIRE, _ECRIRE} <= _noms_outils(mistral_client_factice)
    (ecrire,) = [
        outil for outil in mistral_client_factice.tools_appels_reponse[0] if outil["function"]["name"] == _ECRIRE
    ]
    description = ecrire["function"]["description"]
    # Une ligne par route ouverte au compte ; jamais une route fermée.
    assert "POST moduleo/telephone — Crée un numéro de téléphone." in description
    assert "webhook" not in description


def _resultat_outil(mistral_client_factice, appel: int = 1, rang: int = -1) -> str:
    # Contenu du message `tool` reçu par l'appel principal suivant.
    outils = [m for m in mistral_client_factice.appels_reponse[appel] if m.get("role") == "tool"]
    return outils[rang]["content"]


# decrire_ecriture_moduleo : champs et exemple de corps, sans appel à Moduléo.


def test_decrire_donne_parametres_exemple_de_corps_et_description(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": "POST cogeo/localisant?idAffaire={idAffaire}"})
    mistral_client_factice.repondre("Voici les champs.", "Titre")

    client.post("/conversations", json={"message": "Quels champs ?"}, headers=_autorisation(jeton_valide))

    resultat = _resultat_outil(mistral_client_factice)
    assert resultat.startswith("POST cogeo/localisant?idAffaire={idAffaire} : ")
    assert "Paramètres : idAffaire (int)" in resultat
    assert '"IdAffaire"' in resultat or "Exemple de corps JSON" in resultat
    assert faux_moduleo.appels == [] and faux_moduleo.ecritures == []


def test_decrire_route_du_telephone_avec_son_exemple(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": _TELEPHONE})
    mistral_client_factice.repondre("Voici les champs.", "Titre")

    client.post("/conversations", json={"message": "Quels champs ?"}, headers=_autorisation(jeton_valide))

    resultat = _resultat_outil(mistral_client_factice)
    assert "Crée un numéro de téléphone." in resultat
    assert "Paramètres : aucun" in resultat
    assert '"Numero": "sample string 1"' in resultat


@pytest.mark.parametrize("route", ["POST moduleo/inconnue", "POST webhook", "cogeo/note", "DELETE moduleo/telephone/{idTelephone}"])
def test_decrire_route_inconnue_ou_fermee_phrase_fixe(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, route
):
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": route})
    mistral_client_factice.repondre("Introuvable.", "Titre")

    client.post("/conversations", json={"message": "Quels champs ?"}, headers=_autorisation(jeton_valide))

    assert _resultat_outil(mistral_client_factice) == (
        f"Route d'écriture Moduléo inconnue ou fermée : « {route} ». Choisis une route listée dans la "
        "description de ecrire_moduleo, sous la forme « MÉTHODE route ». Rien n'a été écrit."
    )


# ecrire_moduleo : propose, n'envoie rien ; la carte arrive dans le flux, en noms.


def _contact_et_affaire(faux_moduleo) -> None:
    faux_moduleo.ajouter_contact(40, "Étude Dupont")
    faux_moduleo.ajouter_utilisateur(7, "Jean", "Martin")
    faux_moduleo.ajouter_affaire(12, "2024-123", "Bornage du lot B")


def test_ecrire_n_envoie_rien_et_la_carte_arrive_en_noms(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)

    reponse = _proposer(client, mistral_client_factice, jeton_valide, _telephone())

    assert faux_moduleo.ecritures == []
    assert _resultat_outil(mistral_client_factice).startswith(_PROPOSEE)
    (carte,) = _cartes(reponse)
    assert carte["statut"] == "proposee"
    assert carte["methode"] == "POST" and carte["route"] == "moduleo/telephone"
    assert carte["titre"] == "Crée un numéro de téléphone."
    assert carte["lignes"] == [
        {"champ": "Contact", "valeur": "Étude Dupont"},
        {"champ": "Numero", "valeur": "04 67 00 00 00"},
        {"champ": "Lieu", "valeur": "Bureau"},
    ]
    # La carte part avant la fin du tour.
    noms = [nom for nom, _ in evenements(reponse)]
    assert noms.index("carte") < noms.index("fin")


def test_carte_nomme_affaire_et_utilisateur_et_signale_un_id_non_resolu(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)
    note = {
        "route": "POST cogeo/note",
        "parametres": {},
        "corps": {"Message": "Rappeler le client", "IdAffaire": 12, "IdsDestinataires": [7, 99], "IdCategorieNote": 3},
    }

    reponse = _proposer(client, mistral_client_factice, jeton_valide, note)

    (carte,) = _cartes(reponse)
    assert carte["lignes"] == [
        {"champ": "Message", "valeur": "Rappeler le client"},
        {"champ": "Affaire", "valeur": "affaire 2024-123"},
        {"champ": "Destinataires", "valeur": "Jean Martin, 99 (non résolu)"},
        {"champ": "CategorieNote", "valeur": "3 (non résolu)"},
    ]
    assert faux_moduleo.ecritures == []


def test_ecrire_sans_le_droit_refuse_phrase_fixe_sans_carte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    # Groupe Cogeo sans « Rechercher des contacts » : la note reste ouverte
    # (groupe Cogeo), le téléphone non.
    db_session.add(GroupeModuleo(application="cogeo", nom="Sans droit"))
    db_session.flush()
    rattacher(db_session, "j.dupont", "Sans droit", None, None)
    db_session.commit()

    reponse = _proposer(client, mistral_client_factice, jeton_valide, _telephone())

    assert _cartes(reponse) == []
    assert faux_moduleo.ecritures == []
    assert _resultat_outil(mistral_client_factice) == (
        "Votre compte n'a pas le droit Moduléo « Rechercher des contacts ». Rien n'a été écrit. "
        "Demandez à un compte administrateur si vous en avez besoin."
    )
    assert [(e.statut, e.carte) for e in _journal(db_session)] == [("refusee", None)]


# Confirmation : un clic, hors du modèle, une seule écriture.


def _decider(client, jeton: str, ecriture_id: int, decision: str = "confirmer"):
    return client.post(
        f"/ecritures-moduleo/{ecriture_id}", json={"decision": decision}, headers=_autorisation(jeton)
    )


def _journal(db_session) -> list[EcritureModuleo]:
    db_session.expire_all()
    return db_session.query(EcritureModuleo).order_by(EcritureModuleo.id).all()


def _une_carte(client, faux_moduleo, mistral_client_factice, jeton: str) -> tuple[int, int]:
    # (id de la conversation, id de l'écriture proposée).
    _contact_et_affaire(faux_moduleo)
    reponse = _proposer(client, mistral_client_factice, jeton, _telephone())
    (carte,) = _cartes(reponse)
    return fin(reponse)["conversation"]["id"], carte["id"]


def test_confirmer_envoie_une_seule_ecriture_et_journalise_l_id_renvoye(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    _, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    faux_moduleo.reponse_ecriture = 456

    reponse = _decider(client, jeton_valide, ecriture_id)

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["statut"] == "confirmee"
    assert reponse.json()["message"] == "Écrit dans Moduléo."
    assert faux_moduleo.ecritures == [("POST", "moduleo/telephone", {}, _CORPS_TELEPHONE)]
    (ecriture,) = _journal(db_session)
    assert (ecriture.statut, ecriture.id_renvoye, ecriture.identifiant_compte) == ("confirmee", "456", "j.dupont")
    assert ecriture.corps == _CORPS_TELEPHONE and ecriture.erreur is None


def test_double_clic_une_seule_ecriture(client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide):
    _, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)

    premier = _decider(client, jeton_valide, ecriture_id)
    second = _decider(client, jeton_valide, ecriture_id)

    assert premier.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["statut"] == "confirmee"
    assert len(faux_moduleo.ecritures) == 1


def test_resultat_ajoute_a_la_conversation_vu_par_le_modele_au_tour_suivant(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    conversation_id, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    faux_moduleo.reponse_ecriture = 456
    appels_avant = len(mistral_client_factice.appels_reponse)
    _decider(client, jeton_valide, ecriture_id)
    # Le clic ne relance pas le modèle.
    assert len(mistral_client_factice.appels_reponse) == appels_avant

    mistral_client_factice.repondre("C'est noté.", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "Merci"}, headers=_autorisation(jeton_valide)
    )

    messages = mistral_client_factice.appels_reponse[appels_avant]
    resultat = (
        "Résultat de l'outil ecrire_moduleo (POST moduleo/telephone), après la décision du collaborateur sur "
        "la Carte de confirmation : Écrit dans Moduléo. Id renvoyé : [id Moduléo 456]."
    )
    rangs = [n for n, m in enumerate(messages) if m["content"] == resultat]
    assert rangs, messages
    # Juste après la réponse du tour qui l'a proposée.
    assert messages[rangs[0] - 1] == {"role": "assistant", "content": "Voici la carte."}


def test_annuler_n_envoie_rien(client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session):
    _, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)

    reponse = _decider(client, jeton_valide, ecriture_id, "annuler")

    assert reponse.json()["statut"] == "annulee"
    assert faux_moduleo.ecritures == []
    assert [e.statut for e in _journal(db_session)] == ["annulee"]
    assert _decider(client, jeton_valide, ecriture_id).status_code == 409
    assert faux_moduleo.ecritures == []


def test_nouveau_message_fait_expirer_la_carte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    conversation_id, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    mistral_client_factice.repondre("Autre chose.", resume_et_profil=_resume_et_profil())

    client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "oui"}, headers=_autorisation(jeton_valide)
    )
    reponse = _decider(client, jeton_valide, ecriture_id)

    assert reponse.status_code == 409
    assert reponse.json()["detail"]["statut"] == "expiree"
    assert faux_moduleo.ecritures == []
    assert [e.statut for e in _journal(db_session)] == ["expiree"]


def test_carte_d_un_autre_compte_refusee(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, jeton_store, db_session
):
    _, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    rattacher(db_session, "a.martin", GROUPE_DEV, GROUPE_DEV, None)
    db_session.commit()

    reponse = _decider(client, jeton_store.emettre("a.martin"), ecriture_id)

    assert reponse.status_code == 404
    assert faux_moduleo.ecritures == []
    assert [e.statut for e in _journal(db_session)] == ["proposee"]


def test_droit_retire_entre_proposition_et_clic_refus_journalise(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    _, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    db_session.add(GroupeModuleo(application="cogeo", nom="Sans droit"))
    db_session.flush()
    rattacher(db_session, "j.dupont", "Sans droit", None, None)
    db_session.commit()

    reponse = _decider(client, jeton_valide, ecriture_id)

    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "refusee"
    assert reponse.json()["message"].startswith("Votre compte n'a pas le droit Moduléo « Rechercher des contacts ».")
    assert faux_moduleo.ecritures == []
    assert [e.statut for e in _journal(db_session)] == ["refusee"]


@pytest.mark.parametrize(
    ("erreur", "message"),
    [
        (
            ModuleoDonneesRefusees("Le numéro est invalide."),
            "Moduléo a refusé les données envoyées : Le numéro est invalide.",
        ),
        (ModuleoRefuse("401 sur moduleo/telephone"), "Moduléo refuse cette écriture. Rien n'a été écrit."),
        (ModuleoRefuse("403 sur moduleo/telephone"), "Moduléo refuse cette écriture. Rien n'a été écrit."),
        (
            ModuleoIntrouvable("404 sur moduleo/telephone"),
            "L'élément visé n'existe pas dans Moduléo. Rien n'a été écrit.",
        ),
        (
            ModuleoIndisponible("délai dépassé"),
            "Moduléo est indisponible : l'écriture n'a pas pu être vérifiée. "
            "Vérifiez dans Moduléo avant de recommencer.",
        ),
    ],
)
def test_erreur_moduleo_phrase_fixe_sur_la_carte_journal_en_echec(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session, erreur, message
):
    _, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    faux_moduleo.echouer(erreur)

    reponse = _decider(client, jeton_valide, ecriture_id)

    assert reponse.status_code == 200
    assert (reponse.json()["statut"], reponse.json()["message"]) == ("en_echec", message)
    assert len(faux_moduleo.ecritures) == 1
    (ecriture,) = _journal(db_session)
    assert (ecriture.statut, ecriture.erreur) == ("en_echec", message)


def test_plusieurs_cartes_dans_un_tour_chacune_confirmee_seule_et_rechargees(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)
    portable = _telephone(Numero="06 00 00 00 00", Lieu="Portable")
    reponse = _proposer(client, mistral_client_factice, jeton_valide, _telephone(), portable)
    premiere, seconde = _cartes(reponse)
    conversation_id = fin(reponse)["conversation"]["id"]

    _decider(client, jeton_valide, seconde["id"])

    assert faux_moduleo.ecritures == [("POST", "moduleo/telephone", {}, portable["corps"])]
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)).json()
    user, assistant = detail["messages"]
    assert user["cartes"] == []
    assert [(c["id"], c["statut"]) for c in assistant["cartes"]] == [
        (premiere["id"], "proposee"),
        (seconde["id"], "confirmee"),
    ]
    assert assistant["cartes"][1]["message"] == "Écrit dans Moduléo."
    assert assistant["cartes"][0]["lignes"] == premiere["lignes"]


def test_inspecteur_proposition_et_confirmation_sans_cle_ni_security_code(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    _, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    faux_moduleo.reponse_ecriture = {"IdTelephone": 456}
    _decider(client, jeton_valide, ecriture_id)

    db_session.expire_all()
    (proposition,) = db_session.query(EchangeInspecteur).filter_by(type_appel="outil:ecrire_moduleo").all()
    assert proposition.reponse_payload["route"] == "POST moduleo/telephone"
    assert proposition.reponse_payload["corps"] == _CORPS_TELEPHONE
    assert proposition.reponse_payload["carte"]["id"] == ecriture_id
    (confirmation,) = db_session.query(EchangeInspecteur).filter_by(type_appel="confirmation:ecrire_moduleo").all()
    assert confirmation.origine == "local"
    assert confirmation.requete_payload == {
        "ecriture_id": ecriture_id,
        "decision": "confirmer",
        "methode": "POST",
        "route": "moduleo/telephone",
        "parametres": {},
        "corps": _CORPS_TELEPHONE,
    }
    assert confirmation.reponse_payload["reponse_moduleo"] == {"IdTelephone": 456}
    assert confirmation.reponse_payload["statut"] == "confirmee"
    echanges = [proposition, confirmation]
    texte = json.dumps([[e.requete_payload, e.reponse_payload] for e in echanges], ensure_ascii=False)
    assert "ApiKey" not in texte and "SecurityCode" not in texte
    (ecriture,) = _journal(db_session)
    assert ecriture.id_renvoye == "456"
