use bbass_lanceur_coeur::lancement::{Lancement, ARGUMENT_DEMARRAGE_WINDOWS};

fn lancement(arguments: &[&str]) -> Lancement {
    Lancement::depuis_arguments(arguments.iter().map(|a| a.to_string()))
}

#[test]
fn un_lancement_ordinaire_ouvre_la_fenetre() {
    assert_eq!(lancement(&["BBASS.exe"]), Lancement::AvecFenetre);
}

#[test]
fn le_demarrage_avec_windows_lance_en_fond_sans_fenetre() {
    assert_eq!(lancement(&["BBASS.exe", ARGUMENT_DEMARRAGE_WINDOWS]), Lancement::EnFond);
}

#[test]
fn le_nom_de_l_exe_n_est_pas_pris_pour_l_argument() {
    assert_eq!(lancement(&[ARGUMENT_DEMARRAGE_WINDOWS]), Lancement::AvecFenetre);
}
