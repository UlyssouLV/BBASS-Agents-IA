from datetime import date

import pytest

from flux_sse import fin

from vm_centrale.routers import conversations

# « Cette semaine », « la semaine dernière », un jour nommé : du lundi au
# dimanche, comme le collaborateur les entend (#200, test humain #195
# scénario 4 : « la semaine dernière » le lundi 26/10/2026 devenait les
# sept derniers jours). La consigne de date donne le jour en lettres et les
# bornes de la semaine en cours ; le garde-fou chiffres laisse ces bornes.

_PHRASE_SANS_DONNEES = "Je n'ai trouvé ni page ni document pour appuyer une réponse chiffrée."


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _consigne(client, mistral_client_factice, jeton: str) -> str:
    mistral_client_factice.repondre("Réponse", "Titre")
    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton))
    return mistral_client_factice.appels_reponse[0][0]["content"]


def _repondre(client, mistral_client_factice, jeton: str, reponse: str) -> str:
    mistral_client_factice.repondre(reponse, "Titre")
    resultat = client.post("/conversations", json={"message": "Quelle semaine ?"}, headers=_autorisation(jeton))
    return fin(resultat)["reponse"]


def test_un_lundi_la_consigne_donne_le_jour_en_lettres_et_la_semaine_en_cours(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 26))

    consigne = _consigne(client, mistral_client_factice, jeton_valide)

    assert "lundi 26 octobre 2026" in consigne
    assert "2026-10-26" in consigne
    assert "dimanche 1er novembre 2026" in consigne
    assert "2026-11-01" in consigne
    assert "« la semaine dernière »" in consigne


def test_la_consigne_donne_les_bornes_de_la_semaine_derniere_toutes_calculees(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    # Rejeu du test humain #195 (scénario 4) après #200 : avec la seule
    # semaine en cours, le modèle calculait lui-même « la semaine dernière »
    # le lundi 26/10/2026 et appelait du 20 au 26/10, « du lundi 20 au
    # dimanche 26 octobre ». Les bornes sont données, à recopier.
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 26))

    consigne = _consigne(client, mistral_client_factice, jeton_valide)

    assert "Semaine dernière : du lundi 19 octobre 2026 (2026-10-19) au dimanche 25 octobre 2026 (2026-10-25)" in consigne


def test_un_dimanche_la_semaine_derniere_finit_le_dimanche_precedent(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 11, 1))

    consigne = _consigne(client, mistral_client_factice, jeton_valide)

    assert "Semaine dernière : du lundi 19 octobre 2026 (2026-10-19) au dimanche 25 octobre 2026 (2026-10-25)" in consigne


def test_un_dimanche_la_semaine_en_cours_commence_le_lundi_precedent(
    client, mistral_client_factice, jeton_valide, monkeypatch
):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 25))

    consigne = _consigne(client, mistral_client_factice, jeton_valide)

    assert "dimanche 25 octobre 2026" in consigne
    assert "lundi 19 octobre 2026" in consigne
    assert "2026-10-19" in consigne
    assert "lundi 26" not in consigne


@pytest.mark.parametrize("outil", ["chercher_temps_passes_moduleo", "chercher_planning_moduleo"])
def test_les_descriptions_temps_passes_et_planning_disent_du_lundi_au_dimanche(
    client, faux_moduleo, mistral_client_factice, jeton_valide, outil
):
    mistral_client_factice.repondre("Bonjour.", "Titre")

    client.post("/conversations", json={"message": "Bonjour"}, headers=_autorisation(jeton_valide))

    (schema,) = [o for o in mistral_client_factice.tools_appels_reponse[0] if o["function"]["name"] == outil]
    description = schema["function"]["description"]
    assert "« Cette semaine »" in description
    assert "« la semaine dernière »" in description
    assert "du lundi au dimanche" in description


@pytest.mark.parametrize(
    "reponse",
    [
        "Cette semaine va du lundi 26 octobre au dimanche 1er novembre 2026.",
        "Cette semaine va du 26/10/2026 au 01/11/2026.",
        "Nous sommes le lundi 26.",
        "La semaine dernière va du lundi 19 octobre au dimanche 25 octobre 2026.",
        "La semaine dernière va du 19/10/2026 au 25/10/2026.",
    ],
)
def test_les_bornes_des_deux_semaines_restent_dans_la_reponse(
    client, mistral_client_factice, jeton_valide, monkeypatch, reponse
):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 26))

    assert _repondre(client, mistral_client_factice, jeton_valide, reponse) == reponse


def test_un_autre_jour_hors_des_bornes_reste_controle(client, mistral_client_factice, jeton_valide, monkeypatch):
    monkeypatch.setattr(conversations, "_date_du_jour", lambda: date(2026, 10, 26))

    reponse = _repondre(client, mistral_client_factice, jeton_valide, "Rendez-vous le mardi 27 octobre 2026.")

    assert reponse == _PHRASE_SANS_DONNEES
