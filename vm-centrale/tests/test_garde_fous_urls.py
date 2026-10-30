import time

from vm_centrale.garde_fous import retirer_urls_inventees


def test_une_longue_suite_despaces_sans_url_est_traitee_en_temps_lineaire():
    # Avant le lookbehind de _MOTIF_URL_NUE : 39 s pour 50 000 espaces,
    # chaque espace relançait la lecture de toute la suite.
    texte = "début" + " " * 50_000 + "fin"

    depart = time.perf_counter()
    resultat = retirer_urls_inventees(texte, [])

    assert time.perf_counter() - depart < 1
    assert resultat == (texte, False)


def test_une_url_inventee_devient_le_marqueur_les_espaces_qui_la_precedent_restent():
    assert retirer_urls_inventees("Voir   https://inventee.example.org fin", []) == (
        "Voir   [non trouvé] fin",
        True,
    )


def test_une_parenthese_qui_ne_contenait_que_des_liens_inventes_part_entiere():
    assert retirer_urls_inventees(
        "Voir **Météo France** ([a](https://a.example.org), https://b.example.org) puis la suite.", []
    ) == ("Voir **Météo France** puis la suite.", True)
