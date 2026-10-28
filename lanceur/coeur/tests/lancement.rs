use bbass_lanceur_coeur::lancement::{
    demande_de_verification, processus_a_attendre, Lancement, ARGUMENT_ATTENDRE_FIN, ARGUMENT_DEMARRAGE_WINDOWS,
    ARGUMENT_VERIFICATION,
};

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

fn attendu(arguments: &[&str]) -> Option<u32> {
    processus_a_attendre(arguments.iter().map(|a| a.to_string()))
}

#[test]
fn le_lanceur_redemarre_apres_une_bascule_attend_la_fin_du_precedent() {
    assert_eq!(attendu(&["BBASS.exe", ARGUMENT_ATTENDRE_FIN, "4242"]), Some(4242));
    assert_eq!(attendu(&["BBASS.exe", ARGUMENT_DEMARRAGE_WINDOWS, ARGUMENT_ATTENDRE_FIN, "7"]), Some(7));
}

#[test]
fn un_lancement_ordinaire_n_attend_aucun_processus() {
    assert_eq!(attendu(&["BBASS.exe"]), None);
    assert_eq!(attendu(&["BBASS.exe", ARGUMENT_ATTENDRE_FIN, "abc"]), None);
}

#[test]
fn le_redemarrage_en_fond_reste_en_fond() {
    assert_eq!(lancement(&["BBASS.exe", ARGUMENT_DEMARRAGE_WINDOWS, ARGUMENT_ATTENDRE_FIN, "7"]), Lancement::EnFond);
}

#[test]
fn verifier_les_mises_a_jour_maintenant_relance_avec_la_fenetre_sur_a_propos() {
    assert_eq!(lancement(&["BBASS.exe", ARGUMENT_VERIFICATION, ARGUMENT_ATTENDRE_FIN, "7"]), Lancement::Verification);
}

#[test]
fn la_verification_l_emporte_sur_le_demarrage_en_fond() {
    // Demandée depuis le navigateur pendant que BBASS tourne en fond : la fenêtre rouvre quand même.
    assert_eq!(lancement(&["BBASS.exe", ARGUMENT_DEMARRAGE_WINDOWS, ARGUMENT_VERIFICATION]), Lancement::Verification);
}

#[test]
fn le_backend_demande_une_verification_par_l_instance_unique() {
    // Arguments transmis au Lanceur en cours par le second BBASS.exe que lance le backend.
    let arguments = |a: &[&str]| a.iter().map(|a| a.to_string()).collect::<Vec<_>>();
    assert!(demande_de_verification(arguments(&[r"C:\BBASS\BBASS.exe", ARGUMENT_VERIFICATION])));
    assert!(!demande_de_verification(arguments(&[r"C:\BBASS\BBASS.exe"])));
    assert!(!demande_de_verification(arguments(&[ARGUMENT_VERIFICATION])));
}
