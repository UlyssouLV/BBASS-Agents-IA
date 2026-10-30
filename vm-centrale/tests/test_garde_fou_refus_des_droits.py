# Revue de la 1.5.2 : « droit » et « accès » sont des mots du métier, seule
# la phrase qui redit le refus part.

import pytest

from vm_centrale.garde_fous import montrer_refus_des_droits

_REFUS = "Votre compte n'a pas le droit Moduléo « Planning ». Aucune lecture n'a été faite."


@pytest.mark.parametrize(
    "phrase",
    [
        "L'accès à la parcelle passe par le droit de passage nord.",
        "Le dossier est chez l'administration.",
    ],
)
def test_une_phrase_du_metier_reste(phrase):
    assert montrer_refus_des_droits(phrase, [_REFUS]) == f"{_REFUS}\n\n{phrase}"


@pytest.mark.parametrize(
    "phrase",
    [
        "Je n'ai pas accès au planning.",
        "Votre compte n'a pas les droits nécessaires.",
        "Contactez un administrateur.",
        "Il vous manque cette permission.",
    ],
)
def test_une_reformulation_du_refus_part(phrase):
    assert montrer_refus_des_droits(phrase, [_REFUS]) == _REFUS
