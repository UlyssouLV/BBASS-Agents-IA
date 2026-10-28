use std::cell::RefCell;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

use bbass_lanceur_coeur::mise_a_jour::{Etape, MiseAJour, Reseau, Suite};
use bbass_lanceur_coeur::signature::CleSecrete;

/// Serveur BBASS et Releases simulés : `/sante` répond `sante`, chaque URL connue rend ses octets.
struct ReseauFactice {
    sante: Option<String>,
    fichiers: Vec<(String, Vec<u8>)>,
    telechargements: RefCell<Vec<String>>,
}

impl ReseauFactice {
    fn injoignable() -> Self {
        Self { sante: None, fichiers: Vec::new(), telechargements: RefCell::new(Vec::new()) }
    }

    fn annoncant(version: &str) -> Self {
        Self { sante: Some(format!(r#"{{"statut":"ok","version":"{version}"}}"#)), ..Self::injoignable() }
    }

    fn avec_paquet(mut self, version: &str, zip: Vec<u8>, signature: String) -> Self {
        let url = format!(
            "https://github.com/UlyssouLV/BBASS-Agents-IA/releases/download/v{version}/bbass-poste-v{version}-windows-x64.zip"
        );
        self.fichiers.push((format!("{url}.sig"), signature.into_bytes()));
        self.fichiers.push((url, zip));
        self
    }

    fn telechargements(&self) -> Vec<String> {
        self.telechargements.borrow().clone()
    }
}

impl Reseau for ReseauFactice {
    fn sante(&self) -> Option<String> {
        self.sante.clone()
    }

    fn telecharger(&self, url: &str, progression: &mut dyn FnMut(u64, Option<u64>)) -> Result<Vec<u8>, String> {
        self.telechargements.borrow_mut().push(url.to_string());
        let (_, octets) = self.fichiers.iter().find(|(u, _)| u == url).ok_or("404 Not Found")?;
        progression(octets.len() as u64 / 2, Some(octets.len() as u64));
        progression(octets.len() as u64, Some(octets.len() as u64));
        Ok(octets.clone())
    }
}

/// `%LOCALAPPDATA%\BBASS` simulé, installé en `version` comme le pose l'installateur.
struct Poste {
    racine: PathBuf,
    cle: CleSecrete,
}

impl Poste {
    fn installe_en(nom: &str, version: &str) -> Self {
        let racine = std::env::temp_dir().join(format!("bbass-maj-{nom}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&racine);
        let dossier = racine.join("versions").join(format!("v{version}"));
        fs::create_dir_all(dossier.join("poste-backend")).unwrap();
        fs::write(dossier.join("BBASS.exe"), lanceur(version)).unwrap();
        fs::write(dossier.join("poste-backend").join("poste-backend.exe"), b"backend").unwrap();
        fs::write(racine.join("BBASS.exe"), lanceur(version)).unwrap();
        Self { racine, cle: CleSecrete::generer() }
    }

    fn lanceur(&self, version: &str) -> MiseAJour<'static> {
        MiseAJour::new(
            self.racine.clone(),
            version.parse().unwrap(),
            self.racine.join("mise-a-jour.json"),
            self.cle.cle_publique(),
            "2026-10-28T09:00:00+01:00".to_string(),
            &|_| {},
        )
    }

    fn paquet_signe(&self, version: &str) -> (Vec<u8>, String) {
        let zip = paquet(version, &[("BBASS.exe", &lanceur(version)), (r"poste-backend\poste-backend.exe", b"backend")]);
        let signature = self.cle.signer(&zip);
        (zip, signature)
    }

    fn lire(&self, chemin: &str) -> Option<Vec<u8>> {
        fs::read(self.racine.join(chemin)).ok()
    }

    fn existe(&self, chemin: &str) -> bool {
        self.racine.join(chemin).exists()
    }

    fn etat(&self) -> serde_json::Value {
        serde_json::from_str(&fs::read_to_string(self.racine.join("mise-a-jour.json")).unwrap()).unwrap()
    }
}

fn lanceur(version: &str) -> Vec<u8> {
    format!("Lanceur {version}").into_bytes()
}

/// Zip du Paquet poste ; `version` ne sert qu'à distinguer les contenus.
fn paquet(_version: &str, fichiers: &[(&str, &[u8])]) -> Vec<u8> {
    let mut zip = zip::ZipWriter::new(std::io::Cursor::new(Vec::new()));
    for (nom, octets) in fichiers {
        zip.start_file(*nom, zip::write::SimpleFileOptions::default()).unwrap();
        zip.write_all(octets).unwrap();
    }
    zip.finish().unwrap().into_inner()
}

fn lancer(maj: &MiseAJour, reseau: &dyn Reseau) -> (Suite, Vec<Etape>) {
    let mut etapes = Vec::new();
    let suite = maj.au_lancement(reseau, &mut |etape| etapes.push(etape));
    (suite, etapes)
}

const BANDEAU_V163: &str = "Mise à jour vers v1.6.3 impossible : certaines fonctionnalités peuvent ne pas fonctionner tant qu'elle n'a pas réussi. Nouvel essai au prochain lancement.";

#[test]
fn a_version_identique_rien_n_est_telecharge() {
    let poste = Poste::installe_en("identique", "1.6.2");
    let reseau = ReseauFactice::annoncant("1.6.2");

    let (suite, etapes) = lancer(&poste.lanceur("1.6.2"), &reseau);

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert_eq!(etapes, vec![Etape::Verification, Etape::Demarrage]);
    assert!(reseau.telechargements().is_empty());
    let etat = poste.etat();
    assert_eq!(etat["resultat"], "a_jour");
    assert_eq!(etat["version_poste"], "1.6.2");
    assert_eq!(etat["version_serveur"], "1.6.2");
    assert_eq!(etat["date"], "2026-10-28T09:00:00+01:00");
    assert!(etat["bandeau"].is_null());
}

#[test]
fn le_backend_demarre_est_celui_de_la_version_du_lanceur() {
    let poste = Poste::installe_en("backend", "1.6.2");

    assert_eq!(
        poste.lanceur("1.6.2").backend(),
        poste.racine.join("versions").join("v1.6.2").join("poste-backend").join("poste-backend.exe")
    );
}

#[test]
fn a_version_differente_le_paquet_signe_est_installe_et_le_lanceur_bascule() {
    let poste = Poste::installe_en("bascule", "1.6.2");
    let (zip, signature) = poste.paquet_signe("1.6.3");
    let reseau = ReseauFactice::annoncant("1.6.3").avec_paquet("1.6.3", zip, signature);

    let (suite, etapes) = lancer(&poste.lanceur("1.6.2"), &reseau);

    assert_eq!(suite, Suite::Redemarrer);
    assert_eq!(etapes.first(), Some(&Etape::Verification));
    assert!(etapes.contains(&Etape::MiseAJour { version: "1.6.3".parse().unwrap(), recus: 0, total: None }));
    assert!(etapes.iter().any(|e| matches!(e, Etape::MiseAJour { recus, total: Some(total), .. } if recus == total)));
    assert_eq!(poste.lire("BBASS.exe"), Some(lanceur("1.6.3")));
    assert_eq!(poste.lire("BBASS.old.exe"), Some(lanceur("1.6.2")));
    assert!(poste.existe("versions/v1.6.3/poste-backend/poste-backend.exe"));
    assert!(poste.existe("versions/v1.6.2"));
}

#[test]
fn le_nouveau_lanceur_essaie_sa_version_sans_reverifier_puis_la_confirme() {
    let poste = Poste::installe_en("confirmation", "1.6.2");
    let (zip, signature) = poste.paquet_signe("1.6.3");
    let reseau = ReseauFactice::annoncant("1.6.3").avec_paquet("1.6.3", zip, signature);
    lancer(&poste.lanceur("1.6.2"), &reseau);
    let nouveau = poste.lanceur("1.6.3");
    let muet = ReseauFactice::injoignable();

    let (suite, etapes) = lancer(&nouveau, &muet);
    nouveau.confirmer();

    assert_eq!(suite, Suite::Demarrer { essai: true });
    assert_eq!(etapes, vec![Etape::Demarrage]);
    assert_eq!(nouveau.backend(), poste.racine.join("versions").join("v1.6.3").join("poste-backend").join("poste-backend.exe"));
    let etat = poste.etat();
    assert_eq!(etat["resultat"], "mise_a_jour");
    assert_eq!(etat["version_poste"], "1.6.3");
    assert!(etat["bandeau"].is_null());
}

#[test]
fn une_confirmation_impossible_a_noter_n_annonce_pas_la_reussite_et_refait_l_essai() {
    let poste = Poste::installe_en("confirmation-impossible", "1.6.2");
    let (zip, signature) = poste.paquet_signe("1.6.3");
    lancer(&poste.lanceur("1.6.2"), &ReseauFactice::annoncant("1.6.3").avec_paquet("1.6.3", zip, signature));
    let fichier = poste.racine.join("versions").join("installation.json");
    let mut permissions = fs::metadata(&fichier).unwrap().permissions();
    permissions.set_readonly(true);
    fs::set_permissions(&fichier, permissions.clone()).unwrap();
    let nouveau = poste.lanceur("1.6.3");
    lancer(&nouveau, &ReseauFactice::injoignable());

    nouveau.confirmer();
    let (suite, _) = lancer(&nouveau, &ReseauFactice::injoignable());

    #[allow(clippy::permissions_set_readonly_false)]
    permissions.set_readonly(false);
    fs::set_permissions(&fichier, permissions).unwrap();
    assert_eq!(poste.etat()["resultat"], "echec");
    assert!(poste.etat()["bandeau"].is_null());
    assert_eq!(suite, Suite::Demarrer { essai: true });
}

#[test]
fn le_lancement_suivant_nettoie_le_lanceur_precedent_et_ne_garde_qu_une_version_precedente() {
    let poste = Poste::installe_en("nettoyage", "1.6.2");
    for (de, vers) in [("1.6.2", "1.6.3"), ("1.6.3", "1.6.4")] {
        let (zip, signature) = poste.paquet_signe(vers);
        lancer(&poste.lanceur(de), &ReseauFactice::annoncant(vers).avec_paquet(vers, zip, signature));
        let nouveau = poste.lanceur(vers);
        lancer(&nouveau, &ReseauFactice::injoignable());
        nouveau.confirmer();
    }

    let reseau = ReseauFactice::annoncant("1.6.4");
    let (suite, _) = lancer(&poste.lanceur("1.6.4"), &reseau);

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert!(reseau.telechargements().is_empty());
    assert!(!poste.existe("BBASS.old.exe"));
    assert!(poste.existe("versions/v1.6.4"));
    assert!(poste.existe("versions/v1.6.3"));
    assert!(!poste.existe("versions/v1.6.2"));
}

#[test]
fn un_paquet_a_la_signature_invalide_n_est_pas_installe() {
    let poste = Poste::installe_en("signature", "1.6.2");
    let (zip, _) = poste.paquet_signe("1.6.3");
    let signature_d_une_autre_cle = CleSecrete::generer().signer(&zip);
    let reseau = ReseauFactice::annoncant("1.6.3").avec_paquet("1.6.3", zip, signature_d_une_autre_cle);

    let (suite, etapes) = lancer(&poste.lanceur("1.6.2"), &reseau);

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert_eq!(etapes.last(), Some(&Etape::Demarrage));
    assert_eq!(poste.lire("BBASS.exe"), Some(lanceur("1.6.2")));
    assert!(!poste.existe("BBASS.old.exe"));
    assert!(!poste.existe("versions/v1.6.3"));
    let etat = poste.etat();
    assert_eq!(etat["resultat"], "echec");
    assert_eq!(etat["version_serveur"], "1.6.3");
    assert_eq!(etat["bandeau"], BANDEAU_V163);
    assert_eq!(etat["detail"], "Paquet poste v1.6.3 refusé : signature invalide.");
}

#[test]
fn un_paquet_signe_qui_sort_de_son_dossier_n_est_pas_installe() {
    let poste = Poste::installe_en("chemin", "1.6.2");
    let zip = paquet(
        "1.6.3",
        &[("BBASS.exe", b"x"), ("poste-backend/poste-backend.exe", b"x"), ("../../BBASS.exe", b"pirate")],
    );
    let signature = poste.cle.signer(&zip);
    let reseau = ReseauFactice::annoncant("1.6.3").avec_paquet("1.6.3", zip, signature);

    let (suite, _) = lancer(&poste.lanceur("1.6.2"), &reseau);

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert_eq!(poste.lire("BBASS.exe"), Some(lanceur("1.6.2")));
    assert!(!poste.existe("versions/v1.6.3"));
    assert_eq!(poste.etat()["bandeau"], BANDEAU_V163);
}

#[test]
fn un_telechargement_en_echec_demarre_la_version_installee_avec_le_bandeau() {
    let poste = Poste::installe_en("telechargement", "1.6.2");
    let reseau = ReseauFactice::annoncant("1.6.3");

    let (suite, _) = lancer(&poste.lanceur("1.6.2"), &reseau);

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert_eq!(poste.lire("BBASS.exe"), Some(lanceur("1.6.2")));
    let etat = poste.etat();
    assert_eq!(etat["bandeau"], BANDEAU_V163);
    assert_eq!(etat["detail"], "Téléchargement du Paquet poste v1.6.3 impossible.");
}

#[test]
fn une_nouvelle_version_muette_ramene_l_ancien_lanceur_et_l_ancienne_version() {
    let poste = Poste::installe_en("retour", "1.6.2");
    let (zip, signature) = poste.paquet_signe("1.6.3");
    lancer(&poste.lanceur("1.6.2"), &ReseauFactice::annoncant("1.6.3").avec_paquet("1.6.3", zip, signature));
    let nouveau = poste.lanceur("1.6.3");
    lancer(&nouveau, &ReseauFactice::injoignable());

    nouveau.revenir().unwrap();

    assert_eq!(poste.lire("BBASS.exe"), Some(lanceur("1.6.2")));
    let journal = RefCell::new(Vec::new());
    let ecrire = |ligne: &str| journal.borrow_mut().push(ligne.to_string());
    let retabli = MiseAJour::new(
        poste.racine.clone(),
        "1.6.2".parse().unwrap(),
        poste.racine.join("mise-a-jour.json"),
        poste.cle.cle_publique(),
        "2026-10-28T09:02:00+01:00".to_string(),
        &ecrire,
    );
    let reseau = ReseauFactice::annoncant("1.6.3");
    let (suite, etapes) = lancer(&retabli, &reseau);

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert_eq!(etapes, vec![Etape::Demarrage]);
    assert!(reseau.telechargements().is_empty(), "pas de nouvel essai avant le prochain lancement");
    assert_eq!(retabli.backend(), poste.racine.join("versions").join("v1.6.2").join("poste-backend").join("poste-backend.exe"));
    assert!(!poste.existe("versions/v1.6.3"));
    assert!(!poste.existe("BBASS.echec.exe"));
    let etat = poste.etat();
    assert_eq!(etat["resultat"], "echec");
    assert_eq!(etat["version_poste"], "1.6.2");
    assert_eq!(etat["bandeau"], BANDEAU_V163);
    assert_eq!(etat["detail"], "La version v1.6.3 n'a pas répondu : retour à la version v1.6.2.");
    assert!(journal.borrow().iter().any(|l| l.contains("v1.6.3 n'a pas répondu")));

    // Lancement suivant : nouvel essai.
    let (zip, signature) = poste.paquet_signe("1.6.3");
    let reseau = ReseauFactice::annoncant("1.6.3").avec_paquet("1.6.3", zip, signature);
    assert_eq!(lancer(&poste.lanceur("1.6.2"), &reseau).0, Suite::Redemarrer);
}

#[test]
fn un_serveur_bbass_injoignable_demarre_la_version_installee_avec_un_bandeau_sans_numero() {
    let poste = Poste::installe_en("injoignable", "1.6.2");

    let (suite, etapes) = lancer(&poste.lanceur("1.6.2"), &ReseauFactice::injoignable());

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert_eq!(etapes, vec![Etape::Verification, Etape::Demarrage]);
    let etat = poste.etat();
    assert_eq!(etat["resultat"], "echec");
    assert!(etat["version_serveur"].is_null());
    assert_eq!(
        etat["bandeau"],
        "Mise à jour impossible : certaines fonctionnalités peuvent ne pas fonctionner tant qu'elle n'a pas réussi. Nouvel essai au prochain lancement."
    );
}

#[test]
fn un_serveur_bbass_en_version_dev_ne_declenche_ni_telechargement_ni_bandeau() {
    let poste = Poste::installe_en("dev", "1.6.2");
    let reseau = ReseauFactice::annoncant("dev");

    let (suite, _) = lancer(&poste.lanceur("1.6.2"), &reseau);

    assert_eq!(suite, Suite::Demarrer { essai: false });
    assert!(reseau.telechargements().is_empty());
    let etat = poste.etat();
    assert_eq!(etat["resultat"], "version_non_publiee");
    assert!(etat["bandeau"].is_null());
}

#[test]
fn la_version_d_une_vm_dont_la_base_est_en_panne_compte_quand_meme() {
    let poste = Poste::installe_en("base", "1.6.2");
    let reseau = ReseauFactice {
        sante: Some(r#"{"statut":"base injoignable","version":"1.6.2"}"#.into()),
        ..ReseauFactice::injoignable()
    };

    lancer(&poste.lanceur("1.6.2"), &reseau);

    assert_eq!(poste.etat()["resultat"], "a_jour");
}

