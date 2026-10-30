from flux_sse import fin

# Une réponse corrigée par un garde-fou reste lisible et dit ce qui manque
# (#131, spec 1.6.3, point 8) : un chiffre hors source devient « [non
# trouvé] » au lieu d'un trou (`** €**`), une phrase fixe le signale en fin
# de réponse, la mise en forme (sous-listes, tableaux) n'est pas touchée,
# et un lien inventé ne laisse ni son texte comme source ni `()`.

_URL_PAGE = "https://www.leboncoin.fr/aide/tarifs"
_PAGE = (
    "<html><head><title>Tarifs</title></head><body><nav>Menu du site</nav><article>"
    "<h1>Tarifs des options</h1>"
    "<p>Les options de mise en avant d'une annonce rendent celle-ci plus visible auprès des acheteurs "
    "pendant toute leur durée, sur le site comme dans l'application mobile du service.</p>"
    "<p>Chaque option se commande depuis la page de l'annonce, au moment du dépôt ou plus tard, "
    "et son prix est affiché avant le paiement, toutes taxes comprises.</p>"
    "<p>La remontée en tête de liste coûte 5 € pour une durée de 7 jours.</p>"
    "</article><footer>Mentions légales</footer></body></html>"
)
_PHRASE_FIXE = "Certaines informations n'ont pas été trouvées dans les sources consultées."


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _reponse_apres_recherche(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton: str, reponse: str
) -> str:
    moteur_recherche_factice.repondre(("Tarifs", _URL_PAGE, "Les options de mise en avant."))
    telechargeur_pages_factice.servir(_URL_PAGE, _PAGE)
    mistral_client_factice.repondre_avec_appel_outil(
        "rechercher_web", {"requete": "tarif mise en avant", "besoin": "Prix des options"}
    )
    mistral_client_factice.repondre(reponse, "Titre")
    resultat = client.post(
        "/conversations", json={"message": "Combien coûtent les options ?"}, headers=_autorisation(jeton)
    )
    assert resultat.status_code == 200
    return fin(resultat)["reponse"]


def _sans_sources(contenu: str) -> str:
    return contenu.split("\n\nSources : ")[0]


def test_un_chiffre_non_source_devient_le_marqueur_et_la_phrase_fixe_termine_la_reponse(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_apres_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "La remontée coûte 5 € pour 7 jours. Le pack urgent coûte à partir de **4,99 €** par semaine.",
    )

    assert contenu.startswith(
        "La remontée coûte 5 € pour 7 jours. Le pack urgent coûte à partir de **[non trouvé] €** par semaine."
    )
    assert contenu.endswith(f"\n\n{_PHRASE_FIXE}")


def test_une_reponse_sans_retrait_na_ni_marqueur_ni_phrase_fixe(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_apres_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "La remontée en tête de liste coûte 5 € pour 7 jours.",
    )

    assert "[non trouvé]" not in contenu
    assert _PHRASE_FIXE not in contenu


def test_apres_retrait_lindentation_des_listes_et_lalignement_dun_tableau_sont_conserves(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_apres_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "- Options :\n"
        "   - Remontée : 5 € pour 7 jours.\n"
        "   - Pack urgent : 14,99 €.\n\n"
        "| Option     | Prix   |\n"
        "| ---------- | ------ |\n"
        "| Remontée   | 5 €    |\n"
        "| Urgent     | 2,99 € |",
    )

    assert _sans_sources(contenu) == (
        "- Options :\n"
        "   - Remontée : 5 € pour 7 jours.\n"
        "   - Pack urgent : [non trouvé] €.\n\n"
        "| Option     | Prix   |\n"
        "| ---------- | ------ |\n"
        "| Remontée   | 5 €    |\n"
        "| Urgent     | [non trouvé] € |"
    )


def test_un_entier_dun_chiffre_suivi_dune_unite_monetaire_ou_de_duree_est_controle(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_apres_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "La remontée coûte 5 € pour 7 jours. Le logo coûte 3 € et la vitrine 9€ pour 3 jours. Il y a 3 options.",
    )

    assert _sans_sources(contenu).startswith(
        "La remontée coûte 5 € pour 7 jours. Le logo coûte [non trouvé] € et la vitrine [non trouvé]€ "
        "pour [non trouvé] jours. Il y a 3 options."
    )


def test_un_lien_invente_dont_le_texte_est_une_url_ne_laisse_pas_de_parentheses_vides(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_apres_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "Consultez **Météo France** ([www.meteofrance.com](https://www.meteofrance.com)) pour la semaine.",
    )

    assert contenu == f"Consultez **Météo France** pour la semaine.\n\n{_PHRASE_FIXE}"


def test_le_texte_dun_lien_invente_nest_pas_affiche_comme_une_source(
    client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide
):
    contenu = _reponse_apres_recherche(
        client, mistral_client_factice, moteur_recherche_factice, telechargeur_pages_factice, jeton_valide,
        "La facture est obligatoire, comme le confirme : "
        "[Leboncoin – Centre d'aide – Facturation](https://inventee.example.org/facturation).",
    )

    assert "Centre d'aide" not in contenu
    assert contenu == f"La facture est obligatoire, comme le confirme : [non trouvé].\n\n{_PHRASE_FIXE}"
