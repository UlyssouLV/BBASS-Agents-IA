from datetime import date

import pytest

from vm_centrale.outils.moduleo.devis import outil as outil_devis
from vm_centrale.outils.moduleo.factures import outil as outil_factures

# Objet des devis, factures et affaires en texte lisible (#198, tests
# humains #195) : `Objet` est du RTF, `ObjetBrut` du texte simple ; les deux
# gardent les champs de modèle Moduléo `$…$` non remplis.

# Relevés sur Moduléo (RichTextBox .NET) : accents `\'e9`, `\par`, `\b`.
_OBJET_RTF = (
    r"{\rtf1\ansi\ansicpg1252\deff0\deflang1036{\fonttbl{\f0\fnil\fcharset0 Microsoft Sans Serif;}}"
    "\r\n"
    r"\viewkind4\uc1\pard\fs17 R\'e9tablissement de limite entre la parcelle A894 et A893\par"
    "\r\n"
    r"$Affaire.Commune$ : Section $Affaire.GE.Cbl.SectionParc$\par"
    "\r\n"
    r"\b Lot \b0 2 \'e0 Saint-Cl\'e9ment\par"
    "\r\n}"
)
_OBJET_BRUT = (
    "Rétablissement de limite entre la parcelle A894 et A893\r\n"
    "$Affaire.Commune$ : Section $Affaire.GE.Cbl.SectionParc$\r\n"
    "Lot 2 à Saint-Clément\r\n"
)
_LISIBLE = "Rétablissement de limite entre la parcelle A894 et A893 Lot 2 à Saint-Clément"
_NOMBRES_DU_RTF = ("1252", "1036", "17", "rtf", "fs")


@pytest.fixture(autouse=True)
def _aujourdhui(monkeypatch):
    monkeypatch.setattr(outil_devis, "_date_du_jour", lambda: date(2026, 10, 9))
    monkeypatch.setattr(outil_factures, "_date_du_jour", lambda: date(2026, 10, 9))


def _autorisation(jeton: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton}"}


def _contenu_outil(client, mistral_client_factice, jeton: str, outil: str, arguments: dict) -> str:
    mistral_client_factice.repondre_avec_appel_outil(outil, arguments)
    mistral_client_factice.repondre("Voici.", "Titre")
    reponse = client.post("/conversations", json={"message": "Quel est l'objet ?"}, headers=_autorisation(jeton))
    assert reponse.status_code == 200
    (message,) = [
        m for m in mistral_client_factice.appels_reponse[-2] if isinstance(m, dict) and m["role"] == "tool"
    ]
    return message["content"]


def _devis(client, faux_moduleo, mistral_client_factice, jeton: str, objet: str, **champs) -> str:
    faux_moduleo.ajouter_devis(
        501, "D-2026-042", objet, DateCreation="2026-09-10T00:00:00+02:00", MontantTotalHT=1200.0, **champs
    )
    return _contenu_outil(client, mistral_client_factice, jeton, "chercher_devis_moduleo", {"texte": "D-2026-042"})


def _facture(client, faux_moduleo, mistral_client_factice, jeton: str, objet: str, **champs) -> str:
    faux_moduleo.ajouter_facture(
        601, "F-2026-118", objet, DateCreation="2026-09-10T00:00:00+02:00", MontantTotalTTC=1440.0, **champs
    )
    return _contenu_outil(
        client, mistral_client_factice, jeton, "chercher_factures_moduleo", {"texte": "F-2026-118"}
    )


def _affaire(client, faux_moduleo, mistral_client_factice, jeton: str, objet: str, **champs) -> str:
    faux_moduleo.ajouter_affaire(101, "2024-123", objet, **champs)
    return _contenu_outil(client, mistral_client_factice, jeton, "chercher_affaires_moduleo", {"numero": "2024-123"})


_FICHES = [_devis, _facture, _affaire]


@pytest.mark.parametrize("fiche", _FICHES)
def test_lobjet_brut_sans_les_champs_de_modele(client, faux_moduleo, mistral_client_factice, jeton_valide, fiche):
    contenu = fiche(client, faux_moduleo, mistral_client_factice, jeton_valide, _OBJET_RTF, ObjetBrut=_OBJET_BRUT)

    assert f"Objet : {_LISIBLE}" in contenu.splitlines()
    assert "$" not in contenu
    assert "Section" not in contenu


@pytest.mark.parametrize("fiche", _FICHES)
def test_sans_objet_brut_lobjet_rtf_en_texte_lisible(
    client, faux_moduleo, mistral_client_factice, jeton_valide, fiche
):
    contenu = fiche(client, faux_moduleo, mistral_client_factice, jeton_valide, _OBJET_RTF)

    assert f"Objet : {_LISIBLE}" in contenu.splitlines()
    assert "\\" not in contenu
    assert "{" not in contenu
    for nombre in _NOMBRES_DU_RTF:
        assert nombre not in contenu


@pytest.mark.parametrize("fiche", _FICHES)
def test_un_objet_vide_apres_nettoyage_na_pas_de_ligne(
    client, faux_moduleo, mistral_client_factice, jeton_valide, fiche
):
    objet_rtf = r"{\rtf1\ansi\ansicpg1252\deff0\pard\fs17 $Affaire.Commune$ : Section $Affaire.GE.Cbl.SectionParc$\par }"

    contenu = fiche(
        client,
        faux_moduleo,
        mistral_client_factice,
        jeton_valide,
        objet_rtf,
        ObjetBrut="$Affaire.Commune$ : Section $Affaire.GE.Cbl.SectionParc$",
    )

    assert "Objet" not in contenu


def test_un_champ_de_modele_dans_une_ligne_utile_disparait_seul(
    client, faux_moduleo, mistral_client_factice, jeton_valide
):
    contenu = _affaire(
        client,
        faux_moduleo,
        mistral_client_factice,
        jeton_valide,
        "",
        ObjetBrut="Division $Affaire.Numero$ du lot B, $Affaire.Commune$",
    )

    assert "Objet : Division du lot B" in contenu.splitlines()


def test_un_objet_en_texte_simple_reste_tel_quel(client, faux_moduleo, mistral_client_factice, jeton_valide):
    contenu = _affaire(
        client, faux_moduleo, mistral_client_factice, jeton_valide, "Bornage ALCARAZ\r\nZac Le Solan (lot 3)"
    )

    assert "Objet : Bornage ALCARAZ Zac Le Solan (lot 3)" in contenu.splitlines()
