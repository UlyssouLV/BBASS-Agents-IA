use std::fs;
use std::io::Write;
use std::path::PathBuf;

use bbass_lanceur_coeur::setup::{assembler, desinstaller, installer, lire_paquet_embarque, Choix, PaquetEmbarque};
use bbass_lanceur_coeur::signature::CleSecrete;

fn dossier(nom: &str) -> PathBuf {
    let dossier = std::env::temp_dir().join(format!("bbass-setup-{nom}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dossier);
    fs::create_dir_all(&dossier).unwrap();
    dossier
}

fn paquet(fichiers: &[(&str, &[u8])]) -> Vec<u8> {
    let mut zip = zip::ZipWriter::new(std::io::Cursor::new(Vec::new()));
    for (nom, octets) in fichiers {
        zip.start_file(*nom, zip::write::SimpleFileOptions::default()).unwrap();
        zip.write_all(octets).unwrap();
    }
    zip.finish().unwrap().into_inner()
}

#[test]
fn le_setup_porte_le_paquet_poste_et_sa_signature_derriere_le_lanceur() {
    let dossier = dossier("assemble");
    let zip = paquet(&[("BBASS.exe", b"Lanceur 1.6.2")]);
    let signature = CleSecrete::generer().signer(&zip);
    let setup = dossier.join("BBASS-Setup-v1.6.2.exe");
    fs::write(&setup, assembler(b"MZ Lanceur 1.6.2", &zip, &signature)).unwrap();

    let embarque = lire_paquet_embarque(&setup).unwrap().expect("paquet embarqué");

    assert_eq!(embarque.zip, zip);
    assert_eq!(embarque.signature, signature);
    assert!(fs::read(&setup).unwrap().starts_with(b"MZ Lanceur 1.6.2"));
}

#[test]
fn un_lanceur_installe_n_embarque_aucun_paquet() {
    let dossier = dossier("lanceur-seul");
    let exe = dossier.join("BBASS.exe");
    fs::write(&exe, b"MZ Lanceur 1.6.2 sans rien derriere").unwrap();

    assert!(lire_paquet_embarque(&exe).unwrap().is_none());
}

fn paquet_signe(cle: &CleSecrete, version: &str) -> PaquetEmbarque {
    let lanceur = format!("Lanceur {version}");
    let zip = paquet(&[("BBASS.exe", lanceur.as_bytes()), (r"poste-backend\poste-backend.exe", b"backend")]);
    let signature = cle.signer(&zip);
    PaquetEmbarque { zip, signature }
}

fn choix() -> Choix {
    Choix { hote: " 10.0.0.5 ".into(), port: 8000, demarrage_windows: true }
}

fn configuration(racine: &std::path::Path) -> serde_json::Value {
    serde_json::from_str(&fs::read_to_string(racine.join("configuration.json")).unwrap()).unwrap()
}

#[test]
fn l_installation_pose_le_lanceur_la_version_embarquee_et_la_configuration() {
    let racine = dossier("installation");
    let cle = CleSecrete::generer();

    let exe = installer(&racine, "1.6.2".parse().unwrap(), &paquet_signe(&cle, "1.6.2"), &cle.cle_publique(), &choix()).unwrap();

    assert_eq!(exe, racine.join("BBASS.exe"));
    assert_eq!(fs::read(&exe).unwrap(), b"Lanceur 1.6.2");
    assert!(racine.join("versions/v1.6.2/poste-backend/poste-backend.exe").is_file());
    let configuration = configuration(&racine);
    assert_eq!(configuration["serveur_bbass"], serde_json::json!({"hote": "10.0.0.5", "port": 8000}));
    assert_eq!(configuration["demarrage_windows"], true);
}

#[test]
fn reinstaller_garde_les_autres_reglages_de_la_configuration() {
    let racine = dossier("reinstallation");
    fs::write(
        racine.join("configuration.json"),
        r#"{"serveur_bbass": {"hote": "10.0.0.9", "port": 9000}, "demarrage_windows": true, "autre": 1}"#,
    )
    .unwrap();
    let cle = CleSecrete::generer();
    let choix = Choix { demarrage_windows: false, ..choix() };

    installer(&racine, "1.6.2".parse().unwrap(), &paquet_signe(&cle, "1.6.2"), &cle.cle_publique(), &choix).unwrap();

    let configuration = configuration(&racine);
    assert_eq!(configuration["serveur_bbass"], serde_json::json!({"hote": "10.0.0.5", "port": 8000}));
    assert_eq!(configuration["demarrage_windows"], false);
    assert_eq!(configuration["autre"], 1);
}

#[test]
fn un_setup_dont_le_paquet_n_est_pas_signe_par_la_ci_n_installe_rien() {
    let racine = dossier("altere");
    let cle = CleSecrete::generer();
    let autre = CleSecrete::generer();

    let erreur = installer(&racine, "1.6.2".parse().unwrap(), &paquet_signe(&autre, "1.6.2"), &cle.cle_publique(), &choix())
        .unwrap_err();

    assert!(erreur.contains("signature"), "{erreur}");
    assert!(!racine.join("BBASS.exe").exists());
    assert!(!racine.join("versions").exists());
    assert!(!racine.join("configuration.json").exists());
}

#[test]
fn la_desinstallation_retire_le_programme_et_les_versions_et_garde_configuration_et_journaux() {
    let racine = dossier("desinstallation");
    let cle = CleSecrete::generer();
    installer(&racine, "1.6.2".parse().unwrap(), &paquet_signe(&cle, "1.6.2"), &cle.cle_publique(), &choix()).unwrap();
    for fichier in ["BBASS.old.exe", "BBASS.echec.exe", "mise-a-jour.json"] {
        fs::write(racine.join(fichier), b"x").unwrap();
    }
    fs::create_dir_all(racine.join("journaux")).unwrap();
    fs::write(racine.join("journaux/lanceur.log"), b"journal").unwrap();

    desinstaller(&racine).unwrap();

    for retire in ["BBASS.exe", "BBASS.old.exe", "BBASS.echec.exe", "mise-a-jour.json", "versions"] {
        assert!(!racine.join(retire).exists(), "{retire} encore là");
    }
    assert!(racine.join("configuration.json").is_file());
    assert!(racine.join("journaux/lanceur.log").is_file());
}

#[test]
fn desinstaller_un_poste_deja_desinstalle_ne_fait_rien() {
    let racine = dossier("deja-desinstalle");

    desinstaller(&racine).unwrap();
    desinstaller(&racine.join("absent")).unwrap();
}
