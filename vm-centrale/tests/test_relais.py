def test_ancien_relais_nexiste_plus(client, jeton_valide):
    reponse = client.post(
        "/relais",
        json={"message": "Bonjour"},
        headers={"Authorization": f"Bearer {jeton_valide}"},
    )

    assert reponse.status_code == 404
