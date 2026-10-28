use std::fs;
use std::path::{Path, PathBuf};

use bbass_lanceur_coeur::journal::Journal;

fn dossier_vide(nom: &str) -> PathBuf {
    let dossier = std::env::temp_dir().join(format!("bbass-journal-{nom}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dossier);
    dossier
}

fn fichiers(dossier: &Path) -> Vec<PathBuf> {
    let mut fichiers: Vec<_> = fs::read_dir(dossier).unwrap().map(|f| f.unwrap().path()).collect();
    fichiers.sort();
    fichiers
}

#[test]
fn le_journal_cree_son_dossier_et_ajoute_chaque_ligne() {
    let dossier = dossier_vide("ajout");
    let journal = Journal::new(dossier.join("journaux").join("lanceur.log"), 1_000, 2);

    journal.ecrire("Démarrage");
    journal.ecrire("Backend prêt");

    let contenu = fs::read_to_string(dossier.join("journaux").join("lanceur.log")).unwrap();
    assert_eq!(contenu, "Démarrage\nBackend prêt\n");
}

#[test]
fn le_journal_tourne_sans_depasser_sa_taille_ni_son_nombre_d_archives() {
    let dossier = dossier_vide("rotation");
    let journal = Journal::new(dossier.join("lanceur.log"), 100, 2);

    for i in 0..100 {
        journal.ecrire(&format!("ligne numéro {i:03}"));
    }

    let fichiers = fichiers(&dossier);
    let noms: Vec<_> = fichiers.iter().map(|f| f.file_name().unwrap().to_string_lossy().into_owned()).collect();
    assert_eq!(noms, ["lanceur.log", "lanceur.log.1", "lanceur.log.2"]);
    assert!(fichiers.iter().all(|f| f.metadata().unwrap().len() <= 100));
    let courant = fs::read_to_string(dossier.join("lanceur.log")).unwrap();
    assert!(courant.ends_with("ligne numéro 099\n"));
    let precedent = fs::read_to_string(dossier.join("lanceur.log.1")).unwrap();
    assert!(precedent.lines().last().unwrap() < courant.lines().next().unwrap());
}

#[test]
fn un_journal_impossible_a_ecrire_ne_fait_pas_echouer_le_lanceur() {
    let dossier = dossier_vide("bloque");
    fs::create_dir_all(&dossier).unwrap();
    // Un fichier à la place du dossier des journaux : rien ne peut s'y écrire.
    fs::write(dossier.join("journaux"), "").unwrap();
    let journal = Journal::new(dossier.join("journaux").join("lanceur.log"), 100, 2);

    journal.ecrire("Démarrage");
}
