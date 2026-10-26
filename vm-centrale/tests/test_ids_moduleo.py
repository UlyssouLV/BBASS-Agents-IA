import json

from flux_sse import fin

from vm_centrale.models import EchangeInspecteur, Message

# Ids Moduléo lisibles par le modèle, jamais affichés (spec 1.5.2, #203) :
# les fiches portent `[id Moduléo <n>]` sur leur ligne de référence, une
# consigne système interdit de le citer, et la VM le retire de la réponse
# envoyée au poste et du message enregistré.

_OUTIL = "chercher_affaires_moduleo"
_CONSIGNE = "Ne cite jamais un id Moduléo"


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _resume_et_profil() -> str:
    return json.dumps({"resume_contexte": "Résumé", "profil_travail": None})


def _affaire(faux_moduleo) -> None:
    faux_moduleo.ajouter_utilisateur(1, "Jean", "Martin", tel_fixe="04 67 12 34 56")
    faux_moduleo.ajouter_affaire(1234, "2024-123", "Bornage du lot B", IdResponsable=1)


def _retrouver(client, mistral_client_factice, jeton: str, reponse: str):
    mistral_client_factice.repondre_avec_appel_outil(_OUTIL, {"numero": "2024-123"})
    mistral_client_factice.repondre(reponse, "Titre")
    return client.post(
        "/conversations", json={"message": "Retrouve l'affaire 2024-123"}, headers=_autorisation(jeton)
    )


def _systemes(mistral_client_factice, appel: int = 0) -> str:
    return "\n".join(
        m["content"]
        for m in mistral_client_factice.appels_reponse[appel]
        if isinstance(m, dict) and m["role"] == "system"
    )


def test_le_motif_est_retire_du_flux_et_du_message_enregistre(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _affaire(faux_moduleo)

    reponse = _retrouver(
        client,
        mistral_client_factice,
        jeton_valide,
        "L'affaire 2024-123 [id Moduléo 1234] est suivie par Jean Martin.",
    )

    # La réponse n'arrive au poste qu'une fois filtrée, dans l'événement
    # `fin` : aucun morceau du flux ne porte le motif, même en partie.
    assert "id Moduléo" not in reponse.text
    assert fin(reponse)["reponse"] == "L'affaire 2024-123 est suivie par Jean Martin."
    (enregistre,) = db_session.query(Message).filter(Message.role == "assistant").all()
    assert enregistre.contenu == "L'affaire 2024-123 est suivie par Jean Martin."


def test_le_motif_est_retire_au_message_suivant_aussi(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _affaire(faux_moduleo)
    premiere = _retrouver(client, mistral_client_factice, jeton_valide, "Voici l'affaire.")
    mistral_client_factice.repondre(
        "[id Moduléo 1234] Affaire 2024-123 ([id Moduléo 1234]).", resume_et_profil=_resume_et_profil()
    )

    reponse = client.post(
        f"/conversations/{fin(premiere)['conversation']['id']}/messages",
        json={"message": "Et son id ?"},
        headers=_autorisation(jeton_valide),
    )

    assert "id Moduléo" not in reponse.text
    assert fin(reponse)["reponse"] == "Affaire 2024-123 ()."
    dernier = db_session.query(Message).filter(Message.role == "assistant").order_by(Message.id.desc()).first()
    assert "id Moduléo" not in dernier.contenu


def test_linspecteur_garde_la_reponse_brute_avec_lid(
    client, faux_moduleo, mistral_client_factice, jeton_valide, db_session
):
    _affaire(faux_moduleo)

    _retrouver(client, mistral_client_factice, jeton_valide, "L'affaire 2024-123 [id Moduléo 1234].")

    (garde_fous,) = db_session.query(EchangeInspecteur).filter(EchangeInspecteur.type_appel == "garde_fous").all()
    assert garde_fous.requete_payload["reponse_brute"] == "L'affaire 2024-123 [id Moduléo 1234]."
    assert garde_fous.reponse_payload["reponse_visible"] == "L'affaire 2024-123."


def test_les_sources_citent_toujours_laffaire_par_sa_reference(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    _affaire(faux_moduleo)

    reponse = _retrouver(
        client,
        mistral_client_factice,
        jeton_valide,
        "Jean Martin [id Moduléo 1234] suit l'affaire, tél. 04 67 12 34 56.",
    )

    assert fin(reponse)["reponse"] == (
        "Jean Martin suit l'affaire, tél. 04 67 12 34 56.\n\nSources : Moduléo, affaire 2024-123"
    )


def test_consigne_presente_quand_un_outil_moduleo_est_propose(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    mistral_client_factice.repondre("Bonjour.", "Titre")
    premiere = client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))
    mistral_client_factice.repondre("Encore.", resume_et_profil=_resume_et_profil())
    client.post(
        f"/conversations/{fin(premiere)['conversation']['id']}/messages",
        json={"message": "Et ensuite ?"},
        headers=_autorisation(jeton_valide),
    )

    assert _CONSIGNE in _systemes(mistral_client_factice, 0)
    assert _CONSIGNE in _systemes(mistral_client_factice, -1)


def test_sans_outil_moduleo_pas_de_consigne(client, mistral_client_factice, jeton_valide):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    assert _CONSIGNE not in _systemes(mistral_client_factice)
