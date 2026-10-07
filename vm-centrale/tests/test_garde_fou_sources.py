# Corrections du test humain 2 de la 1.4.3 (#162, conversations 105 et
# 106) : un seul bloc de sources, une page par chiffre, années ignorées.

from vm_centrale.garde_fous import PageSource, ajouter_sources

_BORNAGE = PageSource("https://www.bornage.fr/duree", "Durée d'un bornage", "Un bornage dure 6 à 12 semaines.")
_JUDICIAIRE = PageSource(
    "https://www.justice.fr/bornage-judiciaire", "Bornage judiciaire", "En 2026, la procédure dure 18 mois."
)
_COUT = PageSource("https://www.geometre.fr/cout", "Coût du géomètre", "Un bornage coûte 1 500 € en 2026.")


def test_un_chiffre_garde_venu_dune_page_ajoute_une_ligne_sources():
    resultat = ajouter_sources("Un bornage dure 6 à 12 semaines.", [], [_BORNAGE])

    assert resultat == "Un bornage dure 6 à 12 semaines.\n\nSources : [Durée d'un bornage](https://www.bornage.fr/duree)"


def test_une_reponse_dont_le_seul_chiffre_est_une_annee_na_pas_de_ligne_sources():
    reponse = "En 2026, la procédure est la même."

    assert ajouter_sources(reponse, [], [_JUDICIAIRE, _COUT]) == reponse


def test_une_annee_ne_fait_citer_aucune_page_un_autre_chiffre_seulement_la_sienne():
    resultat = ajouter_sources("En 2026, un bornage coûte 1 500 €.", [], [_JUDICIAIRE, _COUT])

    assert resultat.endswith("\n\nSources : [Coût du géomètre](https://www.geometre.fr/cout)")


def test_deux_pages_avec_le_meme_chiffre_seule_la_plus_recente_est_citee():
    ancienne = PageSource("https://www.ancienne.fr", "Ancienne", "Délai de 12 semaines.")
    recente = PageSource("https://www.recente.fr", "Récente", "Comptez 12 semaines.")

    resultat = ajouter_sources("Comptez 12 semaines.", [], [ancienne, recente])

    assert resultat == "Comptez 12 semaines.\n\nSources : [Récente](https://www.recente.fr)"


def test_un_chiffre_couvert_par_une_page_deja_en_lien_najoute_rien():
    reponse = "Selon [cette page](https://www.bornage.fr/duree), un bornage dure 6 à 12 semaines."
    autre = PageSource("https://www.autre.fr", "Autre", "Entre 6 et 12 semaines.")

    assert ajouter_sources(reponse, [], [_BORNAGE, autre]) == reponse


def test_le_bloc_sources_du_modele_en_ligne_recoit_la_page_manquante():
    reponse = (
        "Un bornage dure 6 à 12 semaines et coûte 1 500 €.\n\n"
        "Sources : [Durée d'un bornage](https://www.bornage.fr/duree)"
    )

    resultat = ajouter_sources(reponse, [], [_BORNAGE, _COUT])

    assert resultat == reponse + ", [Coût du géomètre](https://www.geometre.fr/cout)"


def test_le_bloc_source_au_singulier_passe_au_pluriel():
    reponse = "Un bornage coûte 1 500 € et dure 18 mois.\n\n**Source :** [Coût du géomètre](https://www.geometre.fr/cout)"

    resultat = ajouter_sources(reponse, [], [_COUT, _JUDICIAIRE])

    assert resultat == (
        "Un bornage coûte 1 500 € et dure 18 mois.\n\n**Sources :** [Coût du géomètre](https://www.geometre.fr/cout), "
        "[Bornage judiciaire](https://www.justice.fr/bornage-judiciaire)"
    )


def test_le_bloc_sources_du_modele_en_liste_recoit_une_puce_de_plus():
    reponse = (
        "Un bornage dure 6 à 12 semaines et coûte 1 500 €.\n\n"
        "Sources :\n"
        "* [Durée d'un bornage](https://www.bornage.fr/duree)"
    )

    resultat = ajouter_sources(reponse, [], [_BORNAGE, _COUT])

    assert resultat == reponse + "\n* [Coût du géomètre](https://www.geometre.fr/cout)"


def test_un_bloc_sources_qui_nest_pas_a_la_fin_ne_recoit_rien():
    reponse = (
        "Sources : [Durée d'un bornage](https://www.bornage.fr/duree)\n\n"
        "Un bornage dure 6 à 12 semaines et coûte 1 500 €."
    )

    resultat = ajouter_sources(reponse, [], [_BORNAGE, _COUT])

    assert resultat == reponse + "\n\nSources : [Coût du géomètre](https://www.geometre.fr/cout)"


def test_une_page_lue_deux_fois_nest_citee_quune_fois_avec_le_premier_titre():
    relue = PageSource("https://www.bornage.fr/duree/", "", "Un bornage dure 6 à 12 semaines.")

    resultat = ajouter_sources("Un bornage dure 6 à 12 semaines.", [], [_BORNAGE, relue])

    assert resultat.endswith("\n\nSources : [Durée d'un bornage](https://www.bornage.fr/duree/)")
