use bbass_lanceur_coeur::configuration::url_de_la_sante;

#[test]
fn l_adresse_du_serveur_bbass_vient_du_fichier_de_configuration() {
    let fichier = r#"{"serveur_bbass": {"hote": " 10.0.0.5 ", "port": 8000}}"#;

    assert_eq!(url_de_la_sante(Some(fichier)), "http://10.0.0.5:8000/sante");
}

#[test]
fn sans_fichier_de_configuration_l_adresse_par_defaut_du_backend_s_applique() {
    assert_eq!(url_de_la_sante(None), "http://localhost:8000/sante");
}

#[test]
fn un_fichier_illisible_ou_un_hote_vide_donne_l_adresse_par_defaut() {
    for fichier in ["pas du json", r#"{"serveur_bbass": {"hote": "", "port": 8000}}"#, r#"{"serveur_bbass": {"hote": "10.0.0.5"}}"#] {
        assert_eq!(url_de_la_sante(Some(fichier)), "http://localhost:8000/sante", "{fichier}");
    }
}
