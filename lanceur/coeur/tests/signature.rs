use bbass_lanceur_coeur::signature::{ClePublique, CleSecrete, ErreurSignature};

const PAQUET: &[u8] = b"PK\x03\x04 contenu du Paquet poste";

#[test]
fn un_paquet_signe_se_verifie_avec_la_cle_publique_de_sa_cle_secrete() {
    let cle = CleSecrete::generer();

    let signature = cle.signer(PAQUET);

    assert_eq!(cle.cle_publique().verifier(PAQUET, &signature), Ok(()));
}

#[test]
fn un_paquet_modifie_d_un_octet_est_refuse() {
    let cle = CleSecrete::generer();
    let signature = cle.signer(PAQUET);
    let mut altere = PAQUET.to_vec();
    altere[10] ^= 1;

    assert_eq!(cle.cle_publique().verifier(&altere, &signature), Err(ErreurSignature::SignatureInvalide));
}

#[test]
fn un_paquet_signe_par_une_autre_cle_est_refuse() {
    let signature = CleSecrete::generer().signer(PAQUET);

    assert_eq!(
        CleSecrete::generer().cle_publique().verifier(PAQUET, &signature),
        Err(ErreurSignature::SignatureInvalide)
    );
}

#[test]
fn une_signature_qui_n_est_pas_du_base64_de_64_octets_est_refusee() {
    let cle = CleSecrete::generer().cle_publique();

    assert_eq!(cle.verifier(PAQUET, "pas une signature"), Err(ErreurSignature::SignatureMalformee));
    assert_eq!(cle.verifier(PAQUET, "AAAA"), Err(ErreurSignature::SignatureMalformee));
}

#[test]
fn les_cles_en_texte_signent_et_verifient_comme_les_originales() {
    let cle = CleSecrete::generer();
    // Le secret GitHub et le fichier committé peuvent finir par un saut de ligne.
    let secrete = CleSecrete::depuis_texte(&format!("{}\n", cle.en_texte())).unwrap();
    let publique = ClePublique::depuis_texte(&format!("{}\r\n", cle.cle_publique().en_texte())).unwrap();

    assert_eq!(publique.verifier(PAQUET, &secrete.signer(PAQUET)), Ok(()));
}

#[test]
fn une_cle_qui_n_est_pas_du_base64_de_32_octets_est_refusee() {
    assert_eq!(ClePublique::depuis_texte("AAAA").err(), Some(ErreurSignature::CleInvalide));
    assert_eq!(CleSecrete::depuis_texte("").err(), Some(ErreurSignature::CleInvalide));
}

#[test]
fn la_cle_publique_committee_est_une_cle_ed25519_valide() {
    assert!(ClePublique::du_paquet_poste().is_ok());
}
