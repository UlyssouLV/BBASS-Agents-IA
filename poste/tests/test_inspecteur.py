from poste.vm_centrale_client import (
    CleAdminInvalideError,
    EchangeIntrouvableError,
    InspecteurCompte,
    InspecteurConversation,
    InspecteurEchangeDetail,
    InspecteurEchangeResume,
    JetonInvalideError,
)

_CLE_ADMIN = "cle-admin-de-test"


def _connecter(client, vm_centrale_client_factice, est_admin=False):
    vm_centrale_client_factice.accepter(est_admin=est_admin)
    client.post("/connexion", json={"identifiant": "a.martin", "mot_de_passe": "x"})


def _entetes_admin(cle_admin: str = _CLE_ADMIN) -> dict[str, str]:
    return {"X-Admin-Key": cle_admin}


# --- GET /inspecteur/comptes ---------------------------------------------------


def test_liste_comptes_avec_session_et_cle_admin_retourne_les_comptes(client, vm_centrale_client_factice):
    # Pas besoin d'une session est_admin=true (spec 1.3.0) : n'importe quel
    # compte connecté suffit, contrairement à GET /comptes.
    _connecter(client, vm_centrale_client_factice, est_admin=False)
    vm_centrale_client_factice.inspecteur_comptes_retournes(
        [InspecteurCompte(identifiant_compte="j.dupont"), InspecteurCompte(identifiant_compte="p.leroy")]
    )

    reponse = client.get("/inspecteur/comptes", headers=_entetes_admin())

    assert reponse.status_code == 200
    assert {c["identifiant_compte"] for c in reponse.json()} == {"j.dupont", "p.leroy"}


def test_liste_comptes_transmet_le_jeton_de_session_et_la_cle_admin_telle_quelle(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_comptes_retournes([])

    client.get("/inspecteur/comptes", headers=_entetes_admin("cle-saisie-par-le-developpeur"))

    assert vm_centrale_client_factice._jetons_inspecteur_comptes == ["jeton-factice"]
    assert vm_centrale_client_factice._cles_admin_inspecteur_comptes == ["cle-saisie-par-le-developpeur"]


def test_liste_comptes_sans_session_active_est_refusee(client):
    reponse = client.get("/inspecteur/comptes", headers=_entetes_admin())

    assert reponse.status_code == 401
    assert reponse.json()["detail"]


def test_liste_comptes_sans_en_tete_cle_admin_est_rejetee_sans_appeler_la_vm(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)

    reponse = client.get("/inspecteur/comptes")

    assert reponse.status_code == 422
    assert vm_centrale_client_factice._jetons_inspecteur_comptes == []


def test_liste_comptes_avec_cle_admin_invalide_est_refusee_sans_fermer_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_comptes_echoue(CleAdminInvalideError())

    reponse_liste = client.get("/inspecteur/comptes", headers=_entetes_admin("mauvaise-cle"))
    reponse_compte = client.get("/compte")

    assert reponse_liste.status_code == 401
    assert reponse_liste.json()["detail"]
    assert reponse_compte.status_code == 200


def test_liste_comptes_avec_jeton_revoque_renvoie_401_et_ferme_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_comptes_echoue(JetonInvalideError())

    reponse_liste = client.get("/inspecteur/comptes", headers=_entetes_admin())
    reponse_compte = client.get("/compte")

    assert reponse_liste.status_code == 401
    assert reponse_compte.status_code == 401


def test_liste_comptes_avec_vm_centrale_injoignable_retourne_une_erreur_propre(
    client, vm_centrale_client_factice
):
    import httpx

    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_comptes_echoue(httpx.ConnectError("connexion refusée"))

    reponse = client.get("/inspecteur/comptes", headers=_entetes_admin())

    assert reponse.status_code == 502
    assert reponse.json()["detail"]


# --- GET /inspecteur/comptes/{identifiant_compte}/conversations ----------------


def test_liste_conversations_avec_session_et_cle_admin_retourne_les_conversations(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_conversations_retournees(
        [
            InspecteurConversation(
                id=1,
                titre="Bonjour",
                date_creation="2026-10-05T10:00:00+00:00",
                date_derniere_activite="2026-10-05T10:05:00+00:00",
            )
        ]
    )

    reponse = client.get("/inspecteur/comptes/j.dupont/conversations", headers=_entetes_admin())

    assert reponse.status_code == 200
    assert [c["id"] for c in reponse.json()] == [1]


def test_liste_conversations_transmet_le_jeton_lidentifiant_et_la_cle_admin(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_conversations_retournees([])

    client.get("/inspecteur/comptes/j.dupont/conversations", headers=_entetes_admin())

    assert vm_centrale_client_factice._jetons_inspecteur_conversations == ["jeton-factice"]
    assert vm_centrale_client_factice._identifiants_inspecteur_conversations == ["j.dupont"]
    assert vm_centrale_client_factice._cles_admin_inspecteur_conversations == [_CLE_ADMIN]


def test_liste_conversations_sans_session_active_est_refusee(client):
    reponse = client.get("/inspecteur/comptes/j.dupont/conversations", headers=_entetes_admin())

    assert reponse.status_code == 401


def test_liste_conversations_avec_cle_admin_invalide_est_refusee_sans_fermer_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_conversations_echoue(CleAdminInvalideError())

    reponse_liste = client.get(
        "/inspecteur/comptes/j.dupont/conversations", headers=_entetes_admin("mauvaise-cle")
    )
    reponse_compte = client.get("/compte")

    assert reponse_liste.status_code == 401
    assert reponse_compte.status_code == 200


def test_liste_conversations_avec_jeton_revoque_renvoie_401_et_ferme_la_session(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_conversations_echoue(JetonInvalideError())

    reponse_liste = client.get("/inspecteur/comptes/j.dupont/conversations", headers=_entetes_admin())
    reponse_compte = client.get("/compte")

    assert reponse_liste.status_code == 401
    assert reponse_compte.status_code == 401


# --- GET /inspecteur/conversations/{conversation_id}/echanges ------------------


def test_liste_echanges_avec_session_et_cle_admin_retourne_les_echanges_dans_lordre(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_echanges_retournes(
        [
            InspecteurEchangeResume(
                id=1,
                origine="mistral",
                type_appel="chat",
                statut="succes",
                date_creation="2026-10-05T10:00:00+00:00",
            ),
            InspecteurEchangeResume(
                id=2,
                origine="local",
                type_appel="garde_fous",
                statut="succes",
                date_creation="2026-10-05T10:00:01+00:00",
            ),
            InspecteurEchangeResume(
                id=3,
                origine="mistral",
                type_appel="titrage",
                statut="succes",
                date_creation="2026-10-05T10:00:02+00:00",
            ),
        ]
    )

    reponse = client.get("/inspecteur/conversations/42/echanges", headers=_entetes_admin())

    assert reponse.status_code == 200
    assert [(e["origine"], e["type_appel"]) for e in reponse.json()] == [
        ("mistral", "chat"),
        ("local", "garde_fous"),
        ("mistral", "titrage"),
    ]


def test_liste_echanges_transmet_lid_de_conversation_le_jeton_et_la_cle_admin(
    client, vm_centrale_client_factice
):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_echanges_retournes([])

    client.get("/inspecteur/conversations/42/echanges", headers=_entetes_admin())

    assert vm_centrale_client_factice._jetons_inspecteur_echanges == ["jeton-factice"]
    assert vm_centrale_client_factice._ids_conversation_inspecteur_echanges == [42]
    assert vm_centrale_client_factice._cles_admin_inspecteur_echanges == [_CLE_ADMIN]


def test_liste_echanges_sans_session_active_est_refusee(client):
    reponse = client.get("/inspecteur/conversations/42/echanges", headers=_entetes_admin())

    assert reponse.status_code == 401


# --- GET /inspecteur/echanges/{echange_id} --------------------------------------


def test_detail_echange_avec_session_et_cle_admin_retourne_le_detail(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_echange_detail_retourne(
        InspecteurEchangeDetail(
            id=1,
            identifiant_compte="j.dupont",
            conversation_id=42,
            piece_jointe_id=None,
            origine="mistral",
            type_appel="chat",
            modele="mistral-small-latest",
            requete_payload={"messages": [{"role": "user", "content": "Bonjour"}]},
            reponse_payload={"choices": [{"message": {"content": "Réponse"}}]},
            statut="succes",
            erreur=None,
            date_creation="2026-10-05T10:00:00+00:00",
        )
    )

    reponse = client.get("/inspecteur/echanges/1", headers=_entetes_admin())

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "succes"
    assert corps["origine"] == "mistral"
    assert corps["requete_payload"]["messages"][0]["content"] == "Bonjour"
    assert corps["reponse_payload"]["choices"][0]["message"]["content"] == "Réponse"


def test_detail_echange_transmet_lid_dechange_le_jeton_et_la_cle_admin(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_echange_detail_retourne(
        InspecteurEchangeDetail(
            id=1,
            identifiant_compte="j.dupont",
            conversation_id=None,
            piece_jointe_id=None,
            origine="mistral",
            type_appel="chat",
            modele="mistral-small-latest",
            requete_payload={},
            reponse_payload=None,
            statut="echec",
            erreur="panne",
            date_creation="2026-10-05T10:00:00+00:00",
        )
    )

    client.get("/inspecteur/echanges/1", headers=_entetes_admin())

    assert vm_centrale_client_factice._jetons_inspecteur_echange_detail == ["jeton-factice"]
    assert vm_centrale_client_factice._ids_inspecteur_echange_detail == [1]
    assert vm_centrale_client_factice._cles_admin_inspecteur_echange_detail == [_CLE_ADMIN]


def test_detail_echange_sans_session_active_est_refuse(client):
    reponse = client.get("/inspecteur/echanges/1", headers=_entetes_admin())

    assert reponse.status_code == 401


def test_detail_echange_introuvable_renvoie_404(client, vm_centrale_client_factice):
    _connecter(client, vm_centrale_client_factice)
    vm_centrale_client_factice.inspecteur_echange_detail_echoue(EchangeIntrouvableError())

    reponse = client.get("/inspecteur/echanges/9999", headers=_entetes_admin())

    assert reponse.status_code == 404
    assert reponse.json()["detail"]
