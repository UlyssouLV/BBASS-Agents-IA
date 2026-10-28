use bbass_lanceur_coeur::configuration::url_de_la_sante;

#[test]
fn l_adresse_du_serveur_bbass_vient_du_fichier_de_configuration() {
    let fichier = r#"{"serveur_bbass": {"hote": " 10.0.0.5 ", "port": 8000}}"#;

    assert_eq!(url_de_la_sante(Some(fichier)).as_deref(), Some("http://10.0.0.5:8000/sante"));
}

#[test]
fn sans_fichier_de_configuration_ni_adresse_prod_le_serveur_bbass_est_inconnu() {
    // Adresse prod vide en 1.6.2 : le poste ouvre la Configuration.
    assert_eq!(url_de_la_sante(None), None);
}

#[test]
fn un_fichier_illisible_ou_un_hote_vide_ne_donne_pas_d_adresse() {
    for fichier in ["pas du json", r#"{"serveur_bbass": {"hote": "", "port": 8000}}"#, r#"{"serveur_bbass": {"hote": "10.0.0.5"}}"#] {
        assert_eq!(url_de_la_sante(Some(fichier)), None, "{fichier}");
    }
}
