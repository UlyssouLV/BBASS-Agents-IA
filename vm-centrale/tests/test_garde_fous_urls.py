import time

from vm_centrale.garde_fous import retirer_urls_inventees


def test_une_longue_suite_despaces_sans_url_est_traitee_en_temps_lineaire():
    # Avant le lookbehind de _MOTIF_URL_NUE : 39 s pour 50 000 espaces,
    # chaque espace relançait la lecture de toute la suite.
    texte = "début" + " " * 50_000 + "fin"

    depart = time.perf_counter()
    resultat = retirer_urls_inventees(texte, [])

    assert time.perf_counter() - depart < 1
    assert resultat == texte


def test_lespace_qui_precede_une_url_inventee_part_avec_elle():
    assert retirer_urls_inventees("Voir   https://inventee.example.org fin", []) == "Voir fin"
