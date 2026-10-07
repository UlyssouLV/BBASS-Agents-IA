from datetime import datetime, timezone

import httpx
from flux_sse import evenements

from poste.vm_centrale_client import (
    Conversation,
    ConversationDetail,
    ConversationIntrouvableError,
    JetonInvalideError,
    Message,
    PieceJointeCreee,
    PieceJointeIntrouvableError,
    PieceJointeRefuseeError,
    PieceJointeResume,
)


def _message(
    id: int, role: str, contenu: str, date_creation: datetime, tokens_contexte: int | None = None
) -> Message:
    return Message(
        id=id,
        role=role,
        contenu=contenu,
        date_creation=date_creation,
        tokens_contexte=tokens_contexte,
        fenetre_contexte=262_144,
    )


# Flux SSE de la VM (spec 1.4.4, ADR-0016), relayé tel quel par le poste.
_FIN_CREATION = (
    "fin",
    {
        "conversation": {"id": 1, "titre": "Salutations"},
        "reponse": "Bonjour",
        "tokens_contexte": 3_000,
        "fenetre_contexte": 262_144,
    },
)
_FIN_ENVOI = ("fin", {"reponse": "Réponse suivante", "tokens_contexte": 45_210, "fenetre_contexte": 262_144})
_VM_INDISPONIBLE = "Le service de conversations de la VM centrale est indisponible"


def _connecter(client, vm_centrale_client_factice, identifiant="j.dupont"):
    vm_centrale_client_factice.accepter()
    client.post("/connexion", json={"identifiant": identifiant, "mot_de_passe": "x"})


def test_creer_une_conversation_relaie_le_flux_de_la_vm_dans_l_ordre(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    flux = (
        ("statut", {"libelle": "Réflexion…"}),
        ("statut", {"libelle": "Vérification de la réponse…"}),
        ("statut", {"libelle": "Titre de la conversation…"}),
        _FIN_CREATION,
    )
    vm_centrale_client_factice.creation_conversation_reussit(*flux)

    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert evenements(reponse) == list(flux)
    assert vm_centrale_client_factice._messages_creation_conversation == ["Bonjour"]
    assert vm_centrale_client_factice._jetons_creation_conversation == ["jeton-factice"]


def test_creer_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_creer_une_conversation_message_vide_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/conversations", json={"message": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._messages_creation_conversation == []


def test_creer_une_conversation_message_trop_long_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/conversations", json={"message": "x" * 8001})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._messages_creation_conversation == []


def test_creer_une_conversation_vm_indisponible_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


def test_creer_une_conversation_jeton_invalide_ferme_la_session(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_echoue(JetonInvalideError())

    reponse_creation = client.post("/conversations", json={"message": "Bonjour"})
    reponse_compte = client.get("/compte")

    assert reponse_creation.status_code == 401
    assert reponse_compte.status_code == 401


def test_lister_les_conversations_avec_session_active(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    date_activite = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.liste_conversations_retourne(
        [Conversation(id=1, titre="Salutations", date_derniere_activite=date_activite)]
    )

    reponse = client.get("/conversations")

    assert reponse.status_code == 200
    assert reponse.json() == [
        {"id": 1, "titre": "Salutations", "date_derniere_activite": "2026-09-10T12:00:00Z"}
    ]


def test_lister_les_conversations_sans_session_active_est_refuse(client):
    reponse = client.get("/conversations")

    assert reponse.status_code == 401


def test_consulter_une_conversation_retourne_le_detail_et_les_messages(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    maintenant = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.detail_conversation_retourne(
        ConversationDetail(
            id=1,
            titre="Salutations",
            date_creation=maintenant,
            date_derniere_activite=maintenant,
            messages=[
                _message(1, "user", "Bonjour", maintenant),
                _message(2, "assistant", "Bonjour !", maintenant),
            ],
            a_des_messages_plus_anciens=False,
        )
    )

    reponse = client.get("/conversations/1")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["titre"] == "Salutations"
    assert [(m["role"], m["contenu"]) for m in corps["messages"]] == [
        ("user", "Bonjour"),
        ("assistant", "Bonjour !"),
    ]
    assert corps["a_des_messages_plus_anciens"] is False
    assert vm_centrale_client_factice._ids_detail_conversation == [1]
    assert vm_centrale_client_factice._avant_ids_detail_conversation == [None]
    assert vm_centrale_client_factice._limites_detail_conversation == [None]


def test_consulter_une_conversation_relaie_les_parametres_de_pagination_a_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    maintenant = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.detail_conversation_retourne(
        ConversationDetail(
            id=1,
            titre="Salutations",
            date_creation=maintenant,
            date_derniere_activite=maintenant,
            messages=[],
            a_des_messages_plus_anciens=True,
        )
    )

    reponse = client.get("/conversations/1?avant_id=42&limite=5")

    assert reponse.status_code == 200
    assert reponse.json()["a_des_messages_plus_anciens"] is True
    assert vm_centrale_client_factice._avant_ids_detail_conversation == [42]
    assert vm_centrale_client_factice._limites_detail_conversation == [5]


def test_consulter_une_conversation_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.detail_conversation_echoue(ConversationIntrouvableError())

    reponse = client.get("/conversations/42")

    assert reponse.status_code == 404
    assert reponse.json()["detail"]


def test_consulter_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.get("/conversations/1")

    assert reponse.status_code == 401


def test_renommer_une_conversation(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    date_activite = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.renommage_conversation_reussit(
        Conversation(id=1, titre="Nouveau titre", date_derniere_activite=date_activite)
    )

    reponse = client.patch("/conversations/1", json={"titre": "Nouveau titre"})

    assert reponse.status_code == 200
    assert reponse.json()["titre"] == "Nouveau titre"
    assert vm_centrale_client_factice._requetes_renommage_conversation == [
        {"conversation_id": 1, "titre": "Nouveau titre"}
    ]


def test_renommer_une_conversation_titre_vide_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.patch("/conversations/1", json={"titre": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._requetes_renommage_conversation == []


def test_renommer_une_conversation_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.renommage_conversation_echoue(ConversationIntrouvableError())

    reponse = client.patch("/conversations/42", json={"titre": "Nouveau titre"})

    assert reponse.status_code == 404


def test_renommer_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.patch("/conversations/1", json={"titre": "Nouveau titre"})

    assert reponse.status_code == 401


def test_supprimer_une_conversation(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.delete("/conversations/1")

    assert reponse.status_code == 204
    assert vm_centrale_client_factice._ids_suppression_conversation == [1]


def test_supprimer_une_conversation_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.suppression_conversation_echoue(ConversationIntrouvableError())

    reponse = client.delete("/conversations/42")

    assert reponse.status_code == 404


def test_supprimer_une_conversation_sans_session_active_est_refuse(client):
    reponse = client.delete("/conversations/1")

    assert reponse.status_code == 401


def test_envoyer_un_message_dans_une_conversation_existante(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    flux = (("statut", {"libelle": "Réflexion…"}), ("statut", {"libelle": "Vérification de la réponse…"}), _FIN_ENVOI)
    vm_centrale_client_factice.envoi_message_conversation_reussit(*flux)

    reponse = client.post("/conversations/1/messages", json={"message": "Et ensuite ?"})

    assert evenements(reponse) == list(flux)
    assert vm_centrale_client_factice._requetes_envoi_message_conversation == [
        {"conversation_id": 1, "message": "Et ensuite ?"}
    ]
    assert vm_centrale_client_factice._jetons_envoi_message_conversation == ["jeton-factice"]


def test_envoyer_un_message_message_vide_est_rejete_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.post("/conversations/1/messages", json={"message": ""})

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._requetes_envoi_message_conversation == []


def test_envoyer_un_message_dans_une_conversation_introuvable_retourne_404(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_echoue(ConversationIntrouvableError())

    reponse = client.post("/conversations/42/messages", json={"message": "Et ensuite ?"})

    assert reponse.status_code == 404


def test_envoyer_un_message_sans_session_active_est_refuse(client):
    reponse = client.post("/conversations/1/messages", json={"message": "Et ensuite ?"})

    assert reponse.status_code == 401


def test_envoyer_un_message_jeton_revoque_pendant_l_usage_ferme_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_echoue(JetonInvalideError())

    reponse_message = client.post("/conversations/1/messages", json={"message": "Bonjour"})
    reponse_compte = client.get("/compte")

    assert reponse_message.status_code == 401
    assert reponse_compte.status_code == 401


def test_creer_une_conversation_relaie_la_cle_idempotence_a_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(_FIN_CREATION)

    client.post("/conversations", json={"message": "Bonjour", "cle_idempotence": "cle-1"})

    assert vm_centrale_client_factice._cles_idempotence_creation_conversation == ["cle-1"]


def test_creer_une_conversation_sans_cle_idempotence_en_relaie_labsence(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(_FIN_CREATION)

    client.post("/conversations", json={"message": "Bonjour"})

    assert vm_centrale_client_factice._cles_idempotence_creation_conversation == [None]


def test_envoyer_un_message_relaie_la_cle_idempotence_a_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_reussit(_FIN_ENVOI)

    client.post(
        "/conversations/1/messages",
        json={"message": "Et ensuite ?", "cle_idempotence": "cle-msg-1"},
    )

    assert vm_centrale_client_factice._cles_idempotence_envoi_message_conversation == ["cle-msg-1"]


def test_creer_une_conversation_relaie_le_piece_jointe_id_a_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(_FIN_CREATION)

    client.post("/conversations", json={"message": "Bonjour", "piece_jointe_id": 7})

    assert vm_centrale_client_factice._pieces_jointes_id_creation_conversation == [7]


def test_creer_une_conversation_sans_piece_jointe_en_relaie_labsence(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(_FIN_CREATION)

    client.post("/conversations", json={"message": "Bonjour"})

    assert vm_centrale_client_factice._pieces_jointes_id_creation_conversation == [None]


def test_creer_une_conversation_piece_jointe_refusee_retourne_400(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_echoue(
        PieceJointeRefuseeError("Pièce jointe déjà liée à un message")
    )

    reponse = client.post("/conversations", json={"message": "Bonjour", "piece_jointe_id": 7})

    assert reponse.status_code == 400
    assert reponse.json()["detail"] == "Pièce jointe déjà liée à un message"


def test_envoyer_un_message_relaie_le_piece_jointe_id_a_la_vm(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_reussit(_FIN_ENVOI)

    client.post("/conversations/1/messages", json={"message": "Et ensuite ?", "piece_jointe_id": 9})

    assert vm_centrale_client_factice._pieces_jointes_id_envoi_message_conversation == [9]


def test_envoyer_un_message_piece_jointe_introuvable_retourne_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.envoi_message_conversation_echoue(
        PieceJointeIntrouvableError("Pièce jointe introuvable")
    )

    reponse = client.post("/conversations/1/messages", json={"message": "Et ensuite ?", "piece_jointe_id": 9})

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Pièce jointe introuvable"


def test_televerser_une_piece_jointe_dans_une_conversation_existante(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.televersement_piece_jointe_reussit(
        PieceJointeCreee(
            piece_jointe=PieceJointeResume(id=3, nom_fichier="devis.pdf", type_mime="application/pdf"),
            echec_analyse=False,
        )
    )

    reponse = client.post(
        "/conversations/1/pieces-jointes",
        files={"fichier": ("devis.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
    )

    assert reponse.status_code == 201
    assert reponse.json() == {
        "piece_jointe": {"id": 3, "nom_fichier": "devis.pdf", "type_mime": "application/pdf"},
        "echec_analyse": False,
    }
    assert vm_centrale_client_factice._requetes_televersement_piece_jointe == [
        {
            "conversation_id": 1,
            "nom_fichier": "devis.pdf",
            "contenu": b"%PDF-1.4 contenu factice",
            "type_mime": "application/pdf",
        }
    ]
    assert vm_centrale_client_factice._jetons_televersement_piece_jointe == ["jeton-factice"]


def test_televerser_une_piece_jointe_signale_un_echec_danalyse_sans_erreur_http(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.televersement_piece_jointe_reussit(
        PieceJointeCreee(
            piece_jointe=PieceJointeResume(id=4, nom_fichier="scan.png", type_mime="image/png"),
            echec_analyse=True,
        )
    )

    reponse = client.post(
        "/conversations/1/pieces-jointes",
        files={"fichier": ("scan.png", b"donnees-image-factices", "image/png")},
    )

    assert reponse.status_code == 201
    assert reponse.json()["echec_analyse"] is True


def test_televerser_une_piece_jointe_sans_session_active_est_refuse(client):
    reponse = client.post(
        "/conversations/1/pieces-jointes",
        files={"fichier": ("devis.pdf", b"contenu", "application/pdf")},
    )

    assert reponse.status_code == 401


def test_televerser_une_piece_jointe_dans_une_conversation_dun_autre_compte_retourne_404(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.televersement_piece_jointe_echoue(ConversationIntrouvableError())

    reponse = client.post(
        "/conversations/1/pieces-jointes",
        files={"fichier": ("devis.pdf", b"contenu", "application/pdf")},
    )

    assert reponse.status_code == 404


def test_televerser_une_piece_jointe_type_non_supporte_retourne_400(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.televersement_piece_jointe_echoue(
        PieceJointeRefuseeError("Type de fichier non supporté")
    )

    reponse = client.post(
        "/conversations/1/pieces-jointes",
        files={"fichier": ("archive.zip", b"contenu", "application/zip")},
    )

    assert reponse.status_code == 400
    assert reponse.json()["detail"] == "Type de fichier non supporté"


def test_televerser_une_piece_jointe_sans_conversation(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.televersement_piece_jointe_sans_conversation_reussit(
        PieceJointeCreee(
            piece_jointe=PieceJointeResume(id=5, nom_fichier="notes.docx", type_mime="application/msword"),
            echec_analyse=False,
        )
    )

    reponse = client.post(
        "/pieces-jointes",
        files={"fichier": ("notes.docx", b"contenu-docx-factice", "application/msword")},
    )

    assert reponse.status_code == 201
    assert reponse.json()["piece_jointe"]["id"] == 5
    assert vm_centrale_client_factice._requetes_televersement_piece_jointe_sans_conversation == [
        {"nom_fichier": "notes.docx", "contenu": b"contenu-docx-factice", "type_mime": "application/msword"}
    ]


def test_televerser_une_piece_jointe_sans_conversation_sans_session_active_est_refuse(client):
    reponse = client.post(
        "/pieces-jointes",
        files={"fichier": ("notes.docx", b"contenu", "application/msword")},
    )

    assert reponse.status_code == 401


def test_televerser_une_piece_jointe_sans_conversation_fichier_trop_volumineux_retourne_400(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.televersement_piece_jointe_sans_conversation_echoue(
        PieceJointeRefuseeError("Fichier trop volumineux (max 20 Mo)")
    )

    reponse = client.post(
        "/pieces-jointes",
        files={"fichier": ("gros.pdf", b"contenu", "application/pdf")},
    )

    assert reponse.status_code == 400
    assert reponse.json()["detail"] == "Fichier trop volumineux (max 20 Mo)"


def test_une_erreur_de_la_vm_pendant_le_tour_est_relayee(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    flux = (
        ("statut", {"libelle": "Réflexion…"}),
        ("erreur", {"status": 502, "detail": "Le relais Mistral est indisponible"}),
    )
    vm_centrale_client_factice.envoi_message_conversation_reussit(*flux)

    reponse = client.post("/conversations/1/messages", json={"message": "Et ensuite ?"})

    assert evenements(reponse) == list(flux)


def test_une_vm_coupee_en_plein_flux_termine_par_une_erreur(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.creation_conversation_reussit(
        ("statut", {"libelle": "Réflexion…"}), coupure=httpx.ReadTimeout("délai dépassé")
    )

    reponse = client.post("/conversations", json={"message": "Bonjour"})

    assert evenements(reponse) == [
        ("statut", {"libelle": "Réflexion…"}),
        ("erreur", {"status": 502, "detail": _VM_INDISPONIBLE}),
    ]


def test_consulter_une_conversation_relaie_la_jauge_de_chaque_message(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    maintenant = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
    vm_centrale_client_factice.detail_conversation_retourne(
        ConversationDetail(
            id=1,
            titre="Salutations",
            date_creation=maintenant,
            date_derniere_activite=maintenant,
            messages=[
                _message(1, "assistant", "Réponse d'avant la jauge", maintenant),
                _message(2, "user", "Bonjour", maintenant),
                _message(3, "assistant", "Bonjour !", maintenant, tokens_contexte=45_210),
            ],
            a_des_messages_plus_anciens=False,
        )
    )

    corps = client.get("/conversations/1").json()

    assert [(m["tokens_contexte"], m["fenetre_contexte"]) for m in corps["messages"]] == [
        (None, 262_144),
        (None, 262_144),
        (45_210, 262_144),
    ]
