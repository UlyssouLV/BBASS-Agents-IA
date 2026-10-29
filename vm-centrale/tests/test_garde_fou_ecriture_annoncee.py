# Second passage des tests humains de la 1.5.2 (#206, #258) : une réponse
# de lecture négative (« Aucun contact … n'est enregistré dans Moduléo. »)
# était prise pour une écriture annoncée et relancée.

import pytest

from vm_centrale.garde_fous import affirme_une_ecriture, annonce_une_carte, retirer_ecriture_affirmee


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


# Second passage des tests humains de la 1.5.2 (#206, #259) : des carte,
# écriture ou confirmation annoncées autrement, sans vraie carte.


@pytest.mark.parametrize(
    "reponse",
    [
        "L'écriture est prête à être confirmée par vos soins.",
        "Validez-la sur la carte qui s'affiche.",
        "Vérifiez les informations, puis confirmez sur la carte.",
        "Route : PUT moduleo/telephone/{idTelephone}",
        "Corps : Numero = 04 67 12 34 56",
        "Confirmez le déplacement du numéro vers le contact Cabinet Martin.",
        "Souhaitez-vous que je procède à la saisie de la note ?",
        "Voulez-vous que je crée la tâche Rappeler ?",
    ],
)
def test_une_carte_ou_une_confirmation_dite_en_texte_est_annoncee(reponse):
    assert annonce_une_carte(reponse)


@pytest.mark.parametrize(
    "reponse",
    [
        "Le contact Étude Dupont a deux téléphones.",
        "Confirmez-vous qu'il s'agit bien de l'affaire 2024-123 ou de la 2024-124 ?",
        "La carte du secteur n'est pas dans Moduléo.",
    ],
)
def test_une_lecture_ou_une_clarification_n_annonce_pas_de_carte(reponse):
    assert not annonce_une_carte(reponse)


@pytest.mark.parametrize(
    "reponse",
    [
        "La note Rappeler le client est supprimée.",
        "Le numéro a bien été déplacé.",
        "C'est fait : la tâche Rappeler a été créée.",
    ],
)
def test_une_ecriture_dite_faite_sans_nommer_moduleo_reste_affirmee(reponse):
    assert affirme_une_ecriture(reponse)


def test_une_fiche_lue_avec_sa_date_de_creation_n_affirme_pas_d_ecriture():
    assert not affirme_une_ecriture("La tâche a été créée le 3 mars par Jean Martin.")


def test_apres_une_confirmation_seul_le_resultat_de_son_element_peut_etre_redit():
    confirmees = ["moduleo/telephone"]

    assert not affirme_une_ecriture("Écrit dans Moduléo.", confirmees)
    assert not affirme_une_ecriture("Le numéro est enregistré.", confirmees)
    assert not affirme_une_ecriture("Le téléphone a été ajouté dans Moduléo.", confirmees)
    assert affirme_une_ecriture("La note Rappeler le client est supprimée.", confirmees)


def test_avec_une_carte_ouverte_les_phrases_de_route_de_parametres_ou_de_corps_partent():
    reponse = (
        "Voici la modification du numéro.\n"
        "Route : PUT moduleo/telephone/{idTelephone}\n"
        "Paramètre : idTelephone = 152\n"
        "Corps : Numero = 04 67 12 34 56\n"
        "Confirmez ou annulez sur la carte."
    )

    assert retirer_ecriture_affirmee(reponse) == "Voici la modification du numéro.\nConfirmez ou annulez sur la carte."
