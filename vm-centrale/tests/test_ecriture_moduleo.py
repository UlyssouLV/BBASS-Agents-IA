import json

import pytest

from faux_moduleo import FauxModuleo
from flux_sse import evenements, fin

from vm_centrale.main import app
from vm_centrale.moduleo.client import ClientModuleo, get_client_moduleo
from vm_centrale.models import DroitModuleo, EchangeInspecteur, EcritureModuleo, GroupeModuleo, GroupeModuleoDroit, Message
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


def test_ecrire_consigne_de_proposer_la_carte_sans_question_en_texte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    # Tests humains #206 (#256) : « Souhaitez-vous que je crée cette tâche ? »
    # avant la carte, 3 fois sur 8. La carte est la confirmation.
    _demander(client, mistral_client_factice, jeton_valide)

    (ecrire,) = [
        outil for outil in mistral_client_factice.tools_appels_reponse[0] if outil["function"]["name"] == _ECRIRE
    ]
    description = ecrire["function"]["description"]
    assert "sans demander de confirmation en texte" in description
    assert "la carte est la confirmation" in description


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


_SANS_RECHERCHE = (
    "Champs sans moyen de retrouver l'id à partir d'un nom (l'API ne les lit que par id) : {champs}. "
    "Ne devine jamais leur valeur : utilise seulement un id donné par le collaborateur. Sinon, dis-lui "
    "qu'il n'existe pas, depuis le chat, de moyen de retrouver l'élément à partir de son nom, et propose "
    "l'écriture sans ce champ s'il est facultatif."
)


@pytest.mark.parametrize(
    ("route", "champs"),
    [("POST moduleo/tacheafaire", "IdCategorieTacheAFaire"), ("PUT cogeo/note/{idNote}", "IdCategorieNote")],
)
def test_decrire_signale_les_champs_sans_moyen_de_retrouver_l_id_par_un_nom(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, route, champs
):
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": route})
    mistral_client_factice.repondre("Voici les champs.", "Titre")

    client.post("/conversations", json={"message": "Quels champs ?"}, headers=_autorisation(jeton_valide))

    assert _resultat_outil(mistral_client_factice).endswith(_SANS_RECHERCHE.format(champs=champs))


def test_decrire_sans_champ_de_ce_genre_ne_signale_rien(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": _TELEPHONE})
    mistral_client_factice.repondre("Voici les champs.", "Titre")

    client.post("/conversations", json={"message": "Quels champs ?"}, headers=_autorisation(jeton_valide))

    assert "Champs sans moyen" not in _resultat_outil(mistral_client_factice)


def test_categorie_terrain_demandee_par_son_nom_pas_de_carte_devinee(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    # Tests humains #206 : « catégorie Terrain ». Le modèle lit les champs,
    # apprend que la catégorie ne se retrouve pas par son nom, et le dit
    # sans proposer de carte.
    faux_moduleo.ajouter_categorie_tache_a_faire(1, "Terrain")
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": "POST moduleo/tacheafaire"})
    reponse_du_modele = (
        "Il n'existe pas, depuis le chat, de moyen de retrouver la catégorie « Terrain » à partir de son nom. "
        "Je peux créer la tâche sans catégorie."
    )
    mistral_client_factice.repondre(reponse_du_modele, "Titre")

    reponse = client.post(
        "/conversations",
        json={"message": "Crée une tâche à faire « Relevé sur place », catégorie Terrain"},
        headers=_autorisation(jeton_valide),
    )

    assert "IdCategorieTacheAFaire" in _resultat_outil(mistral_client_factice)
    assert "Ne devine jamais leur valeur" in _resultat_outil(mistral_client_factice)
    assert _cartes(reponse) == []
    assert fin(reponse)["reponse"] == reponse_du_modele
    assert faux_moduleo.appels == [] and faux_moduleo.ecritures == []
    assert _journal(db_session) == []


@pytest.mark.parametrize("route", ["POST moduleo/inconnue", "POST webhook", "cogeo/note", "DELETE webhook"])
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
    # Titre en langage métier, pas la phrase de la doc de la route (#256).
    assert carte["titre"] == "Créer un numéro de téléphone"
    assert carte["lignes"] == [
        {"champ": "Contact", "valeur": "Étude Dupont", "avant": None},
        {"champ": "Numero", "valeur": "04 67 00 00 00", "avant": None},
        {"champ": "Lieu", "valeur": "Bureau", "avant": None},
    ]
    # La carte part avant la fin du tour.
    noms = [nom for nom, _ in evenements(reponse)]
    assert noms.index("carte") < noms.index("fin")


def test_carte_nomme_affaire_utilisateur_et_categorie_de_note(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_categorie_note(3, "Rendez-vous")
    note = {
        "route": "POST cogeo/note",
        "parametres": {},
        "corps": {"Message": "Rappeler le client", "IdAffaire": 12, "IdsDestinataires": [7], "IdCategorieNote": 3},
    }

    reponse = _proposer(client, mistral_client_factice, jeton_valide, note)

    (carte,) = _cartes(reponse)
    assert carte["lignes"] == [
        {"champ": "Message", "valeur": "Rappeler le client", "avant": None},
        {"champ": "Affaire", "valeur": "affaire 2024-123", "avant": None},
        {"champ": "Destinataires", "valeur": "Jean Martin", "avant": None},
        {"champ": "CategorieNote", "valeur": "Rendez-vous", "avant": None},
    ]
    assert faux_moduleo.ecritures == []


def _tache_a_faire(**corps) -> dict:
    return {
        "route": "POST moduleo/tacheafaire",
        "parametres": {},
        "corps": {"Libelle": "Relevé sur place", "IdCategorieTacheAFaire": 1, "IdUtilisateursAffectes": [7], **corps},
    }


def test_carte_d_une_tache_a_faire_nomme_sa_categorie_et_signale_un_id_non_resolu(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    # Tests humains #206 : « 1 (non résolu) » cachait une catégorie inventée.
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_categorie_tache_a_faire(1, "Terrain")

    tache = _tache_a_faire(IdEffectueePar=7, IdGedElement=8)

    reponse = _proposer(client, mistral_client_factice, jeton_valide, tache)

    (carte,) = _cartes(reponse)
    # Un id qu'aucun résolveur ne sait nommer reste affiché brut.
    assert carte["lignes"] == [
        {"champ": "Libelle", "valeur": "Relevé sur place", "avant": None},
        {"champ": "CategorieTacheAFaire", "valeur": "Terrain", "avant": None},
        {"champ": "UtilisateursAffectes", "valeur": "Jean Martin", "avant": None},
        {"champ": "EffectueePar", "valeur": "Jean Martin", "avant": None},
        {"champ": "GedElement", "valeur": "8 (non résolu)", "avant": None},
    ]


def test_carte_d_une_tache_a_faire_titre_metier_et_dates_lisibles_heure_de_paris(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    # Tests humains #206 (#256) : « DateLimite 2026-11-15T00:00:00+01:00 ».
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_categorie_tache_a_faire(1, "Terrain")
    tache = _tache_a_faire(DateLimite="2026-11-15T00:00:00+01:00", DateRealisationSouhaitee="2026-11-02T13:30:00Z")

    reponse = _proposer(client, mistral_client_factice, jeton_valide, tache)

    (carte,) = _cartes(reponse)
    assert carte["titre"] == "Créer une tâche à faire"
    lignes = {ligne["champ"]: ligne["valeur"] for ligne in carte["lignes"]}
    assert lignes["DateLimite"] == "15 novembre 2026"
    # 13:30 UTC le 2 novembre : 14:30 à Paris (UTC+1).
    assert lignes["DateRealisationSouhaitee"] == "2 novembre 2026 à 14:30"


@pytest.mark.parametrize(
    ("corps", "phrase"),
    [
        ({"IdCategorieTacheAFaire": 3}, "CategorieTacheAFaire 3"),
        ({"IdUtilisateursAffectes": [7, 99]}, "UtilisateursAffectes 99"),
        ({"IdAffaire": 404}, "Affaire 404"),
    ],
    ids=["categorie-null", "utilisateur-404", "affaire-absente-du-multi"],
)
def test_id_introuvable_dans_moduleo_pas_de_carte_et_demander_au_collaborateur(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session, corps, phrase
):
    # Tests humains #206 : la catégorie 3 n'existe pas ; Moduléo a refusé
    # l'écriture confirmée (403). Elle ne doit plus arriver sur une carte.
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_categorie_tache_a_faire(1, "Terrain")

    reponse = _proposer(client, mistral_client_factice, jeton_valide, _tache_a_faire(**corps))

    assert _cartes(reponse) == []
    assert faux_moduleo.ecritures == []
    assert _journal(db_session) == []
    assert _resultat_outil(mistral_client_factice) == (
        f"Élément introuvable dans Moduléo : {phrase}. Écriture non proposée. Rien n'a été écrit. "
        "N'essaie pas un autre id : demande au collaborateur quel élément il veut."
    )


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


# PUT et DELETE (#205) : la VM relit l'élément avant la carte. PUT : les
# seuls champs qui changent, ancien → nouveau, en noms. DELETE : la fiche
# entière, sous « Sera supprimé ».

_TELEPHONE_EXISTANT = "moduleo/telephone/{idTelephone}"
_INTROUVABLE_A_LA_RELECTURE = (
    "L'élément visé n'existe pas dans Moduléo : écriture non proposée. Rien n'a été écrit."
)


def _telephone_existant(faux_moduleo) -> None:
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_contact(41, "Cabinet Martin")
    faux_moduleo.ajouter_telephone(30, 40, "04 67 00 00 00", "Bureau")


def _modifier_telephone(id_telephone: int = 30, **corps) -> dict:
    existant = {"IdTelephone": id_telephone, "IdContact": 40, "Numero": "04 67 00 00 00", "Lieu": "Bureau"}
    return {
        "route": f"PUT {_TELEPHONE_EXISTANT}",
        "parametres": {"idTelephone": id_telephone},
        "corps": {**existant, **corps},
    }


def _supprimer(route: str, **parametres) -> dict:
    return {"route": f"DELETE {route}", "parametres": parametres}


def test_put_relit_l_element_et_la_carte_montre_les_seuls_champs_modifies_en_noms(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _telephone_existant(faux_moduleo)

    reponse = _proposer(
        client, mistral_client_factice, jeton_valide, _modifier_telephone(IdContact=41, Numero="04 67 11 11 11")
    )

    assert (_TELEPHONE_EXISTANT, {"idTelephone": 30}) in faux_moduleo.appels
    assert faux_moduleo.ecritures == []
    assert _resultat_outil(mistral_client_factice).startswith(_PROPOSEE)
    (carte,) = _cartes(reponse)
    assert (carte["methode"], carte["statut"], carte["rubrique"]) == ("PUT", "proposee", None)
    # « Met à jour un … en fonction de son identifiant unique. » (#256).
    assert carte["titre"] == "Modifier un numéro de téléphone"
    assert carte["lignes"] == [
        {"champ": "Contact", "avant": "Étude Dupont", "valeur": "Cabinet Martin"},
        {"champ": "Numero", "avant": "04 67 00 00 00", "valeur": "04 67 11 11 11"},
    ]


def test_put_champ_vide_avant_ou_apres(client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide):
    faux_moduleo.ajouter_tache(8, "Bornage", "2026-10-12T08:00:00", "2026-10-12T12:00:00", Emplacement="Lot A")
    tache = {
        "route": "PUT planning/tacheplanning/{idTachePlanning}",
        "parametres": {"idTachePlanning": 8},
        "corps": {"IdTachePlanning": 8, "Libelle": "Bornage lot B", "Emplacement": None, "Commentaire": "GPS"},
    }

    reponse = _proposer(client, mistral_client_factice, jeton_valide, tache)

    (carte,) = _cartes(reponse)
    assert carte["lignes"] == [
        {"champ": "Libelle", "avant": "Bornage", "valeur": "Bornage lot B"},
        {"champ": "Emplacement", "avant": "Lot A", "valeur": "(vide)"},
        {"champ": "Commentaire", "avant": "(vide)", "valeur": "GPS"},
    ]


def test_put_sans_aucun_changement_pas_de_carte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    _telephone_existant(faux_moduleo)

    reponse = _proposer(client, mistral_client_factice, jeton_valide, _modifier_telephone())

    assert _cartes(reponse) == []
    assert _resultat_outil(mistral_client_factice) == (
        "Écriture non proposée : le corps ne change aucun champ de l'élément visé. Rien n'a été écrit."
    )
    assert _journal(db_session) == []


# Élément visé d'un PUT (#253, test humain #206) : la carte ne disait pas
# quelle tâche elle modifiait. Comme pour un DELETE, la fiche de l'élément
# relu, au-dessus des différences.


def test_put_carte_avec_la_fiche_de_l_element_vise_aussi_au_rechargement(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_tache(
        8, "Bornage", "2026-10-12T08:00:00", "2026-10-12T12:00:00", IdAffaire=12, Emplacement="Lot A"
    )
    tache = {
        "route": "PUT planning/tacheplanning/{idTachePlanning}",
        "parametres": {"idTachePlanning": 8},
        "corps": {"IdTachePlanning": 8, "Libelle": "Bornage lot B"},
    }

    reponse = _proposer(client, mistral_client_factice, jeton_valide, tache)

    (carte,) = _cartes(reponse)
    assert carte["fiche"].startswith("Tâche « Bornage »")
    for attendu in ("Date : 12/10/2026", "Affaire : 2024-123", "Lieu : Lot A"):
        assert attendu in carte["fiche"]
    assert "id Moduléo" not in carte["fiche"]
    assert carte["lignes"] == [{"champ": "Libelle", "avant": "Bornage", "valeur": "Bornage lot B"}]
    conversation_id = fin(reponse)["conversation"]["id"]
    detail = client.get(f"/conversations/{conversation_id}", headers=_autorisation(jeton_valide)).json()
    (rechargee,) = detail["messages"][1]["cartes"]
    assert (rechargee["fiche"], rechargee["lignes"]) == (carte["fiche"], carte["lignes"])


def test_put_sans_fiche_de_lecture_l_element_vise_en_noms(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _telephone_existant(faux_moduleo)

    reponse = _proposer(client, mistral_client_factice, jeton_valide, _modifier_telephone(Numero="04 67 11 11 11"))

    (carte,) = _cartes(reponse)
    assert carte["fiche"] == "Numero : 04 67 00 00 00\nLieu : Bureau\nContact : Étude Dupont"
    assert carte["lignes"] == [{"champ": "Numero", "avant": "04 67 00 00 00", "valeur": "04 67 11 11 11"}]


def test_delete_carte_sera_supprime_avec_la_fiche_existante(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_temps_passe(70, "2026-10-07T00:00:00", 4.0, 7, IdAffaire=12, Lieu="Terrain")

    reponse = _proposer(
        client, mistral_client_factice, jeton_valide, _supprimer("cogeo/tempspasse/{idTempsPasse}", idTempsPasse=70)
    )

    assert faux_moduleo.ecritures == []
    (carte,) = _cartes(reponse)
    assert (carte["methode"], carte["rubrique"], carte["lignes"]) == ("DELETE", "Sera supprimé", [])
    assert carte["fiche"].startswith("Temps passé du 07/10/2026")
    for attendu in ("Collaborateur : Jean Martin", "Affaire : 2024-123", "Heures : 4 h", "Lieu : Terrain"):
        assert attendu in carte["fiche"]
    assert "id Moduléo" not in carte["fiche"]


def test_delete_sans_fiche_existante_les_champs_en_noms(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _telephone_existant(faux_moduleo)

    reponse = _proposer(
        client, mistral_client_factice, jeton_valide, _supprimer(_TELEPHONE_EXISTANT, idTelephone=30)
    )

    (carte,) = _cartes(reponse)
    assert (carte["rubrique"], carte["fiche"]) == ("Sera supprimé", None)
    assert carte["lignes"] == [
        {"champ": "Numero", "valeur": "04 67 00 00 00", "avant": None},
        {"champ": "Lieu", "valeur": "Bureau", "avant": None},
        {"champ": "Contact", "valeur": "Étude Dupont", "avant": None},
    ]


@pytest.mark.parametrize(
    "appel",
    [_modifier_telephone(999, Numero="06 00 00 00 00"), _supprimer(_TELEPHONE_EXISTANT, idTelephone=999)],
    ids=["PUT", "DELETE"],
)
def test_element_introuvable_a_la_relecture_pas_de_carte_phrase_fixe(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, appel
):
    _telephone_existant(faux_moduleo)

    reponse = _proposer(client, mistral_client_factice, jeton_valide, appel)

    assert _cartes(reponse) == []
    assert faux_moduleo.ecritures == []
    assert _resultat_outil(mistral_client_factice) == _INTROUVABLE_A_LA_RELECTURE


def _groupe_cogeo(db_session, *chemins: str) -> None:
    # Rattache j.dupont au seul groupe Cogeo « Test », qui n'a que `chemins`.
    groupe = GroupeModuleo(application="cogeo", nom="Test")
    db_session.add(groupe)
    db_session.flush()
    for droit in db_session.query(DroitModuleo).filter(DroitModuleo.chemin.in_(chemins)):
        db_session.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
    rattacher(db_session, "j.dupont", "Test", None, None)
    db_session.commit()


def test_relecture_refusee_par_le_garde_pas_de_carte_phrase_fixe(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    # Une tâche à faire s'écrit avec « Supprimer / Éditer les tâches à faire
    # dont il n'est pas le créateur » mais se lit avec « Voir les tâches à
    # faire des autres » : sans ce dernier, la VM ne peut pas montrer ce qui
    # changerait.
    _groupe_cogeo(db_session, "Tâches à faire › Supprimer / Éditer les tâches à faire dont il n'est pas le créateur")
    tache = {
        "route": "PUT moduleo/tacheafaire/{idTacheAFaire}",
        "parametres": {"idTacheAFaire": 5},
        "corps": {"IdTacheAFaire": 5, "Libelle": "Relancer le client"},
    }

    reponse = _proposer(client, mistral_client_factice, jeton_valide, tache)

    assert _cartes(reponse) == []
    assert faux_moduleo.appels == [] and faux_moduleo.ecritures == []
    phrase = (
        "Votre compte ne peut pas lire l'élément visé dans Moduléo : écriture non proposée. Rien n'a été écrit. "
        "Demandez à un compte administrateur si vous en avez besoin."
    )
    assert _resultat_outil(mistral_client_factice) == phrase
    assert [(e.statut, e.carte, e.erreur) for e in _journal(db_session)] == [("refusee", None, phrase)]


@pytest.mark.parametrize(
    ("appel", "attendue"),
    [
        (
            _modifier_telephone(Numero="04 67 11 11 11"),
            (
                "PUT",
                _TELEPHONE_EXISTANT,
                {"idTelephone": 30},
                {
                    "IdTelephone": 30,
                    "IdContact": 40,
                    "Numero": "04 67 11 11 11",
                    "Lieu": "Bureau",
                    "ProprietesModifiees": ["Numero"],
                },
            ),
        ),
        (_supprimer(_TELEPHONE_EXISTANT, idTelephone=30), ("DELETE", _TELEPHONE_EXISTANT, {"idTelephone": 30}, None)),
    ],
    ids=["PUT", "DELETE"],
)
def test_confirmer_put_ou_delete_une_seule_requete_avec_la_bonne_methode(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session, appel, attendue
):
    _telephone_existant(faux_moduleo)
    (carte,) = _cartes(_proposer(client, mistral_client_factice, jeton_valide, appel))

    reponse = _decider(client, jeton_valide, carte["id"])

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["statut"] == "confirmee"
    # La carte confirmée garde ce qu'elle montrait.
    assert (reponse.json()["lignes"], reponse.json()["rubrique"]) == (carte["lignes"], carte["rubrique"])
    assert faux_moduleo.ecritures == [attendue]
    assert [(e.methode, e.statut) for e in _journal(db_session)] == [(attendue[0], "confirmee")]


# Notes (#208) : la relecture d'une note s'ouvre au droit de son écriture,
# « Notes › Supprimer / Éditer les notes des autres ».

_NOTE = "cogeo/note/{idNote}"


def _note_existante(faux_moduleo) -> None:
    _contact_et_affaire(faux_moduleo)
    faux_moduleo.ajouter_affaire(13, "2024-124", "Division du lot C")
    faux_moduleo.ajouter_note(5, "Rappeler le client", IdContact=40, IdAffaire=12, TypeNote=1)


def _modifier_note(**corps) -> dict:
    existant = {"IdNote": 5, "Message": "Rappeler le client", "IdContact": 40, "IdAffaire": 12, "TypeNote": 1}
    return {"route": f"PUT {_NOTE}", "parametres": {"idNote": 5}, "corps": {**existant, **corps}}


def test_put_note_carte_avec_les_seuls_champs_modifies_en_noms(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _note_existante(faux_moduleo)

    reponse = _proposer(
        client, mistral_client_factice, jeton_valide, _modifier_note(Message="Relancer le géomètre", IdAffaire=13)
    )

    assert (_NOTE, {"idNote": 5}) in faux_moduleo.appels
    assert faux_moduleo.ecritures == []
    (carte,) = _cartes(reponse)
    assert (carte["methode"], carte["statut"], carte["rubrique"]) == ("PUT", "proposee", None)
    assert carte["lignes"] == [
        {"champ": "Message", "avant": "Rappeler le client", "valeur": "Relancer le géomètre"},
        {"champ": "Affaire", "avant": "affaire 2024-123", "valeur": "affaire 2024-124"},
    ]


def test_delete_note_carte_sera_supprime_avec_les_champs_en_noms(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _note_existante(faux_moduleo)

    reponse = _proposer(client, mistral_client_factice, jeton_valide, _supprimer(_NOTE, idNote=5))

    assert faux_moduleo.ecritures == []
    (carte,) = _cartes(reponse)
    assert (carte["methode"], carte["rubrique"], carte["fiche"]) == ("DELETE", "Sera supprimé", None)
    assert carte["lignes"] == [
        {"champ": "Message", "valeur": "Rappeler le client", "avant": None},
        {"champ": "Contact", "valeur": "Étude Dupont", "avant": None},
        {"champ": "Affaire", "valeur": "affaire 2024-123", "avant": None},
        {"champ": "TypeNote", "valeur": "1", "avant": None},
    ]


@pytest.mark.parametrize(
    "appel", [_modifier_note(Message="Relancer le géomètre"), _supprimer(_NOTE, idNote=5)], ids=["PUT", "DELETE"]
)
def test_note_sans_le_droit_refusee_par_le_garde_sans_carte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session, appel
):
    # « Supprimer / Éditer ses propres notes » n'ouvre ni la lecture ni
    # l'écriture d'une note.
    _note_existante(faux_moduleo)
    _groupe_cogeo(db_session, "Notes › Supprimer / Éditer ses propres notes")

    reponse = _proposer(client, mistral_client_factice, jeton_valide, appel)

    assert _cartes(reponse) == []
    assert faux_moduleo.appels == [] and faux_moduleo.ecritures == []
    assert _resultat_outil(mistral_client_factice) == (
        "Votre compte n'a pas le droit Moduléo « Supprimer / Éditer les notes des autres ». Rien n'a été écrit. "
        "Demandez à un compte administrateur si vous en avez besoin."
    )


# Route classée mais non ouverte au compte (#255, tests humains #206,
# scénario 20 bis) : la phrase du garde nomme le droit manquant, dès
# decrire_ecriture_moduleo.

_MODIFIER_TACHE = "PUT moduleo/tacheafaire/{idTacheAFaire}"
_SANS_EDITION_TACHE = (
    "Votre compte n'a pas le droit Moduléo « Supprimer / Éditer les tâches à faire dont il n'est pas le créateur ». "
    "Rien n'a été écrit. Demandez à un compte administrateur si vous en avez besoin."
)


def test_decrire_route_hors_des_droits_du_compte_nomme_le_droit_manquant(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    # Groupe Cogeo sans droit : la note reste ouverte, la tâche à faire non.
    _groupe_cogeo(db_session)
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": _MODIFIER_TACHE})
    mistral_client_factice.repondre("Votre compte n'a pas ce droit.", "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Renomme la tâche à faire 5"}, headers=_autorisation(jeton_valide)
    )

    assert _resultat_outil(mistral_client_factice) == _SANS_EDITION_TACHE
    assert _cartes(reponse) == []
    assert faux_moduleo.appels == [] and faux_moduleo.ecritures == []
    assert _journal(db_session) == []
    db_session.expire_all()
    (echange,) = db_session.query(EchangeInspecteur).filter_by(type_appel=f"outil:{_DECRIRE}").all()
    assert echange.reponse_payload["garde_des_droits"] == (
        "refusé, droit manquant « Tâches à faire › Supprimer / Éditer les tâches à faire dont il n'est pas le "
        "créateur » (PUT moduleo/tacheafaire/{idTacheAFaire})"
    )


def _groupe_planning_avec_ecriture(db_session) -> None:
    # Rattache j.dupont au seul groupe Planning « Test », avec « Créer une tâche ».
    groupe = GroupeModuleo(application=PLANNING, nom="Test")
    db_session.add(groupe)
    db_session.flush()
    droit = db_session.query(DroitModuleo).filter_by(chemin="Planning › Créer une tâche").one()
    db_session.add(GroupeModuleoDroit(groupe_id=groupe.id, droit_id=droit.id))
    rattacher(db_session, "j.dupont", None, "Test", None)
    db_session.commit()


def test_decrire_sans_le_groupe_de_l_application_le_nomme(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    # Groupe Planning seul, avec un droit d'écriture qui ouvre les outils :
    # une route Cogeo demandée, le groupe Cogeo manque.
    _groupe_planning_avec_ecriture(db_session)
    mistral_client_factice.repondre_avec_appel_outil(_DECRIRE, {"route": _MODIFIER_TACHE})
    mistral_client_factice.repondre("Non.", "Titre")

    client.post("/conversations", json={"message": "Renomme la tâche"}, headers=_autorisation(jeton_valide))

    assert _resultat_outil(mistral_client_factice) == (
        "Votre compte n'est rattaché à aucun groupe Moduléo Cogeo. Rien n'a été écrit. "
        "Demandez à un compte administrateur si vous en avez besoin."
    )


def test_ecrire_route_hors_des_droits_du_compte_nomme_le_droit_manquant_sans_carte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    _groupe_cogeo(db_session)
    tache = {
        "route": _MODIFIER_TACHE,
        "parametres": {"idTacheAFaire": 5},
        "corps": {"IdTacheAFaire": 5, "Libelle": "Relancer le client"},
    }

    reponse = _proposer(client, mistral_client_factice, jeton_valide, tache)

    assert _resultat_outil(mistral_client_factice) == _SANS_EDITION_TACHE
    assert _cartes(reponse) == []
    assert faux_moduleo.appels == [] and faux_moduleo.ecritures == []
    assert [(e.statut, e.carte) for e in _journal(db_session)] == [("refusee", None)]


# PUT partiel (#251) : le PUT de Moduléo remet à vide un champ absent du
# corps, sauf `ProprietesModifiees`. La VM y met les seuls champs de la
# carte : un champ non annoncé garde sa valeur.


def test_put_partiel_confirme_ne_change_que_les_champs_de_la_carte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _note_existante(faux_moduleo)
    partiel = {"route": f"PUT {_NOTE}", "parametres": {"idNote": 5}, "corps": {"IdNote": 5, "Message": "Relancer"}}
    (carte,) = _cartes(_proposer(client, mistral_client_factice, jeton_valide, partiel))
    assert [ligne["champ"] for ligne in carte["lignes"]] == ["Message"]

    reponse = _decider(client, jeton_valide, carte["id"])

    assert reponse.status_code == 200, reponse.text
    assert faux_moduleo.note(5) == {
        "IdNote": 5,
        "Message": "Relancer",
        "IdContact": 40,
        "IdAffaire": 12,
        "TypeNote": 1,
    }


def test_put_proprietes_modifiees_du_modele_remplacees_par_les_champs_de_la_carte(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    # Le modèle liste un champ qu'il n'envoie pas : il serait effacé.
    _note_existante(faux_moduleo)
    corps = {"IdNote": 5, "Message": "Relancer", "TypeNote": 1, "ProprietesModifiees": ["Message", "IdAffaire"]}
    appel = {"route": f"PUT {_NOTE}", "parametres": {"idNote": 5}, "corps": corps}
    (carte,) = _cartes(_proposer(client, mistral_client_factice, jeton_valide, appel))

    _decider(client, jeton_valide, carte["id"])

    ((_, _, _, envoye),) = faux_moduleo.ecritures
    assert envoye["ProprietesModifiees"] == ["Message"]
    assert faux_moduleo.note(5)["IdAffaire"] == 12


# Écriture annoncée sans carte (#252, test humain #206) : le modèle écrivait
# une fausse carte en texte, ou « a été créée dans Moduléo », sans appeler
# ecrire_moduleo. La VM relance le tour en imposant l'outil.

_FAUSSE_CARTE = (
    "Voici la carte de confirmation :\n```json\n{\"route\": \"POST moduleo/tacheafaire\", "
    "\"corps\": {\"Libelle\": \"Rappeler\"}}\n```\nValider pour appliquer."
)
_ECRIRE_IMPOSE = {"type": "function", "function": {"name": _ECRIRE}}


def _annoncer(client, mistral_client_factice, jeton: str, *reponses: str, force: dict | None = None):
    # Le modèle répond d'abord `reponses[0]` sans outil ; `force` : les
    # arguments de ecrire_moduleo à l'appel où l'outil est imposé.
    if force is not None:
        mistral_client_factice.repondre_a_l_outil_impose(_ECRIRE, force)
    mistral_client_factice.repondre(*reponses, "Titre")
    return client.post(
        "/conversations", json={"message": "Ajoute le téléphone du bureau"}, headers=_autorisation(jeton)
    )


def test_fausse_carte_en_texte_relance_le_tour_en_imposant_ecrire_moduleo(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)

    reponse = _annoncer(
        client, mistral_client_factice, jeton_valide, _FAUSSE_CARTE, "Voici la carte.", force=_telephone()
    )

    assert mistral_client_factice.tool_choices_appels_reponse[:2] == [None, _ECRIRE_IMPOSE]
    (carte,) = _cartes(reponse)
    assert carte["route"] == "moduleo/telephone"
    assert fin(reponse)["reponse"] == "Voici la carte."
    assert faux_moduleo.ecritures == []


def _sans_droit_telephone(db_session) -> None:
    # Groupe Cogeo sans « Rechercher des contacts » : le téléphone refusé.
    db_session.add(GroupeModuleo(application="cogeo", nom="Sans droit"))
    db_session.flush()
    rattacher(db_session, "j.dupont", "Sans droit", None, None)
    db_session.commit()


def test_relance_refusee_par_le_garde_la_reponse_qui_suit_dit_le_refus(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    _sans_droit_telephone(db_session)
    refus = "Votre compte n'a pas le droit Moduléo « Rechercher des contacts » : rien n'a été écrit."

    reponse = _annoncer(client, mistral_client_factice, jeton_valide, _FAUSSE_CARTE, refus, force=_telephone())

    assert mistral_client_factice.tool_choices_appels_reponse[1] == _ECRIRE_IMPOSE
    assert _resultat_outil(mistral_client_factice, appel=2).startswith("Votre compte n'a pas le droit Moduléo")
    assert _cartes(reponse) == []
    assert fin(reponse)["reponse"] == refus
    assert [e.statut for e in _journal(db_session)] == ["refusee"]


def test_relance_sans_carte_et_reponse_qui_annonce_encore_phrase_fixe(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    _sans_droit_telephone(db_session)

    reponse = _annoncer(
        client, mistral_client_factice, jeton_valide, _FAUSSE_CARTE, "Le téléphone a été ajouté dans Moduléo.",
        force=_telephone(),
    )

    assert _cartes(reponse) == []
    assert fin(reponse)["reponse"] == (
        "Aucune carte de confirmation n'a été ouverte : rien n'a été écrit dans Moduléo. "
        "Reformulez la demande d'écriture si besoin."
    )
    # Une seule relance par message.
    assert mistral_client_factice.tool_choices_appels_reponse.count(_ECRIRE_IMPOSE) == 1


def test_ecriture_dite_faite_sans_outil_d_ecriture_phrase_fixe_sans_relance(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    reponse = _annoncer(client, mistral_client_factice, jeton_valide, "La tâche Rappeler a été créée dans Moduléo.")

    assert _ECRIRE_IMPOSE not in mistral_client_factice.tool_choices_appels_reponse
    assert fin(reponse)["reponse"].startswith("Aucune carte de confirmation n'a été ouverte")


def test_carte_ouverte_la_reponse_ne_dit_pas_l_ecriture_faite(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)

    reponse = _proposer(
        client,
        mistral_client_factice,
        jeton_valide,
        _telephone(),
        reponse="Le téléphone a été ajouté dans Moduléo. Vérifiez la carte.",
    )

    assert len(_cartes(reponse)) == 1
    assert fin(reponse)["reponse"] == "Vérifiez la carte."
    # Une vraie carte : pas de relance.
    assert _ECRIRE_IMPOSE not in mistral_client_factice.tool_choices_appels_reponse


def test_apres_une_confirmation_le_modele_peut_redire_l_ecriture_faite(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    conversation_id, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    _decider(client, jeton_valide, ecriture_id)
    mistral_client_factice.repondre("Le téléphone a été ajouté dans Moduléo.", resume_et_profil=_resume_et_profil())

    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "C'est fait ?"}, headers=_autorisation(jeton_valide)
    )

    assert fin(reponse)["reponse"] == "Le téléphone a été ajouté dans Moduléo."
    assert _ECRIRE_IMPOSE not in mistral_client_factice.tool_choices_appels_reponse


def test_apres_une_confirmation_l_id_renvoye_cite_ne_laisse_pas_de_phrase_coupee(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide, db_session
):
    # Tests humains #206 : « … enregistrée dans Moduléo sous l'. ».
    conversation_id, ecriture_id = _une_carte(client, faux_moduleo, mistral_client_factice, jeton_valide)
    _decider(client, jeton_valide, ecriture_id)
    mistral_client_factice.repondre(
        "Le téléphone est enregistré dans Moduléo sous l'[id Moduléo 4].", resume_et_profil=_resume_et_profil()
    )

    reponse = client.post(
        f"/conversations/{conversation_id}/messages", json={"message": "C'est fait ?"}, headers=_autorisation(jeton_valide)
    )

    assert "id Moduléo" not in reponse.text
    assert fin(reponse)["reponse"] == "Le téléphone est enregistré dans Moduléo."
    dernier = db_session.query(Message).filter(Message.role == "assistant").order_by(Message.id.desc()).first()
    assert dernier.contenu == "Le téléphone est enregistré dans Moduléo."


def test_fausse_carte_au_message_suivant_aussi_relancee(
    client, faux_moduleo, ecriture_active, mistral_client_factice, jeton_valide
):
    _contact_et_affaire(faux_moduleo)
    conversation_id = fin(_demander(client, mistral_client_factice, jeton_valide))["conversation"]["id"]
    mistral_client_factice.repondre_a_l_outil_impose(_ECRIRE, _telephone())
    mistral_client_factice.repondre(_FAUSSE_CARTE, "Voici la carte.", resume_et_profil=_resume_et_profil())

    reponse = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Ajoute le téléphone du bureau"},
        headers=_autorisation(jeton_valide),
    )

    assert len(_cartes(reponse)) == 1
    assert fin(reponse)["reponse"] == "Voici la carte."
