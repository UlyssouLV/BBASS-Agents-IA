import json

import pytest

from flux_sse import fin

from vm_centrale.garde_fous import remplacer_contact_non_lu

# Corrections du test humain 2 de la 1.5.0 (conversation 116, « Affaires en
# cours depuis octobre », #183) : sur quatre demandes de coordonnées, le
# modèle n'a jamais appelé chercher_contacts_moduleo et a répondu « pas
# disponibles dans Moduléo » à partir des seules fiches d'affaire.

_AFFAIRES = "chercher_affaires_moduleo"
_CONTACTS = "chercher_contacts_moduleo"
_PHRASE = "Moduléo n'a pas encore été consulté pour ce contact. Précisez son nom pour que je le cherche."
_ABSENT = "Les coordonnées de Céline Bourdoncle ne sont pas disponibles dans Moduléo."


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _affaire(faux_moduleo) -> None:
    faux_moduleo.ajouter_contact(20, "Céline Bourdoncle")
    faux_moduleo.ajouter_contact(30, "Office notarial Rives")
    faux_moduleo.ajouter_affaire(101, "22_369-152", "Bornage", IdClient=20, QualiteClient="Propriétaire")
    faux_moduleo.ajouter_intervenant(900, 101, 30, "Notaire")


def _contenu_outil(mistral_client_factice) -> str:
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def test_la_description_des_affaires_renvoie_vers_les_contacts_seulement_sur_demande(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == _AFFAIRES]
    description = schema["function"]["description"]
    assert "sans leurs coordonnées" in description
    assert _CONTACTS in description
    assert "seulement quand le collaborateur les demande" in description


def test_la_fiche_daffaire_dit_ou_lire_les_coordonnees_du_client_et_des_intervenants(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire(faux_moduleo)
    mistral_client_factice.repondre_avec_appel_outil(_AFFAIRES, {"numero": "22_369-152"})
    mistral_client_factice.repondre("Voici l'affaire.", "Titre")

    client.post("/conversations", json={"message": "L'affaire 22_369-152"}, headers=_autorisation(jeton_valide))

    fiche = _contenu_outil(mistral_client_factice)
    assert "Coordonnées du client et des intervenants" in fiche
    assert _CONTACTS in fiche
    assert "seulement si le collaborateur les demande" in fiche


def test_presenter_une_affaire_nappelle_jamais_loutil_contacts(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire(faux_moduleo)
    mistral_client_factice.repondre_avec_appel_outil(_AFFAIRES, {"numero": "22_369-152"})
    mistral_client_factice.repondre("Voici l'affaire.", "Titre")

    client.post("/conversations", json={"message": "L'affaire 22_369-152"}, headers=_autorisation(jeton_valide))

    assert not [route for route in faux_moduleo.routes_appelees() if route.startswith("cogeo/contact?texte=")]


def test_une_absence_dans_moduleo_sans_lecture_de_contact_est_remplacee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire(faux_moduleo)
    mistral_client_factice.repondre_avec_appel_outil(_AFFAIRES, {"numero": "22_369-152"})
    mistral_client_factice.repondre(_ABSENT, "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Coordonnées de Céline Bourdoncle"}, headers=_autorisation(jeton_valide)
    )

    assert fin(reponse)["reponse"] == _PHRASE


def test_la_meme_absence_apres_une_lecture_de_contact_nest_pas_remplacee(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire(faux_moduleo)
    mistral_client_factice.repondre_avec_appel_outil(_CONTACTS, {"texte": "Bourdoncle"})
    mistral_client_factice.repondre(_ABSENT, "Titre")

    reponse = client.post(
        "/conversations", json={"message": "Coordonnées de Céline Bourdoncle"}, headers=_autorisation(jeton_valide)
    )

    assert fin(reponse)["reponse"] == _ABSENT


@pytest.mark.parametrize(
    "reponse",
    [
        "Les coordonnées du client ne sont pas disponibles dans Moduléo.",
        "Moduléo ne contient aucun numéro de téléphone pour les intervenants de l'affaire 25_862-17.",
        "Je n'ai pas trouvé d'email pour Céline Bourdoncle dans Moduleo.",
        "Voici l'affaire.\n\nSon téléphone n'apparaît pas dans moduléo, désolé.",
    ],
)
def test_une_absence_de_coordonnees_dans_moduleo_est_reconnue(reponse):
    assert remplacer_contact_non_lu(reponse, contacts_lus=False) == _PHRASE


@pytest.mark.parametrize(
    "reponse",
    [
        "Le client de l'affaire 22_369-152 est Céline Bourdoncle (Propriétaire).",
        "Voulez-vous que je cherche ses coordonnées dans Moduléo ?",
        "Aucune affaire ne correspond dans Moduléo.",
        "Ses coordonnées ne sont pas dans la pièce jointe.",
    ],
)
def test_une_reponse_sans_absence_de_coordonnees_dans_moduleo_est_inchangee(reponse):
    assert remplacer_contact_non_lu(reponse, contacts_lus=False) == reponse


def test_apres_une_lecture_de_contact_le_garde_fou_ne_change_rien():
    assert remplacer_contact_non_lu(_ABSENT, contacts_lus=True) == _ABSENT


def test_le_tour_suivant_la_phrase_fixe_contact_na_pas_de_note_de_remplacement(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre(_ABSENT, "Titre")
    reponse = client.post(
        "/conversations", json={"message": "Coordonnées de Céline Bourdoncle"}, headers=_autorisation(jeton_valide)
    )
    conversation_id = fin(reponse)["conversation"]["id"]
    prompt_titrage = mistral_client_factice.appels_reponse[-1]

    mistral_client_factice.repondre("Je la cherche.", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"message": "Céline Bourdoncle"},
        headers=_autorisation(jeton_valide),
    )

    assert "Assistant" not in prompt_titrage
    messages = mistral_client_factice.appels_reponse[-1]
    assert not [m for m in messages if m["role"] == "system" and "remplacée par la VM" in m["content"]]
