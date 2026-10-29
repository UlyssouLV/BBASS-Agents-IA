# Second passage des tests humains de la 1.5.2 (#206, #258) : une réponse
# de lecture négative (« Aucun contact … n'est enregistré dans Moduléo. »)
# était prise pour une écriture annoncée et relancée.

import pytest

from vm_centrale.garde_fous import affirme_une_ecriture, retirer_ecriture_affirmee


@pytest.mark.parametrize(
    "reponse",
    [
        "Aucun contact Client Exemple 10 n'est enregistré dans Moduléo.",
        "Aucune tâche au planning n'est enregistrée dans Moduléo pour cette semaine.",
        "Aucun téléphone enregistré dans Moduléo pour ce contact.",
        "Ce contact n'a pas été créé dans Moduléo.",
        "Les contacts ne sont pas encore saisis dans Moduléo.",
        "L'affaire SCPT-0010 est enregistrée dans Moduléo au nom de Client Exemple 10.",
        "Ses contacts sont enregistrés dans Moduléo depuis 2024.",
    ],
)
def test_une_lecture_negative_ou_un_constat_n_affirme_pas_d_ecriture(reponse):
    assert not affirme_une_ecriture(reponse)


@pytest.mark.parametrize(
    "reponse",
    [
        "La tâche Rappeler a été créée dans Moduléo.",
        "Le téléphone a été ajouté dans Moduléo.",
        "Les deux tâches ont été ajoutées dans Moduléo.",
        "Pas de souci, la tâche a été créée dans Moduléo.",
        "Aucun souci : le téléphone a été ajouté dans Moduléo.",
        "Le contact a bien été enregistré dans Moduléo.",
    ],
)
def test_une_ecriture_dite_faite_reste_affirmee(reponse):
    assert affirme_une_ecriture(reponse)


def test_avec_une_carte_ouverte_seule_l_ecriture_affirmee_part_pas_la_lecture():
    reponse = (
        "Aucun téléphone n'est enregistré dans Moduléo pour ce contact. "
        "Le téléphone a été ajouté dans Moduléo. Vérifiez la carte."
    )

    assert retirer_ecriture_affirmee(reponse) == (
        "Aucun téléphone n'est enregistré dans Moduléo pour ce contact. Vérifiez la carte."
    )
