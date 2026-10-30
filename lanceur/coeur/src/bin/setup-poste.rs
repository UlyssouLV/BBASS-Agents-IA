//! Assemble `BBASS-Setup-vX.Y.Z.exe` (spec 1.6.2, point 8), depuis `lanceur/` :
//!
//! `cargo run -p bbass-lanceur-coeur --bin setup-poste -- <BBASS.exe> <paquet.zip> <signature> <sortie>`
//!
//! Le Setup est le Lanceur suivi du Paquet poste signé ; la signature est vérifiée avec la clé
//! publique compilée avant l'assemblage, comme le Setup le fera avant d'installer.

use std::fs;
use std::process::ExitCode;

use bbass_lanceur_coeur::setup::assembler;
use bbass_lanceur_coeur::signature::ClePublique;

const USAGE: &str = "usage : setup-poste <BBASS.exe> <paquet.zip> <signature> <sortie>";

fn lire(chemin: &str) -> Result<Vec<u8>, String> {
    fs::read(chemin).map_err(|e| format!("lecture de {chemin} : {e}"))
}

fn assembler_le_setup(lanceur: &str, paquet: &str, signature: &str, sortie: &str) -> Result<(), String> {
    let zip = lire(paquet)?;
    let signature = String::from_utf8(lire(signature)?).map_err(|_| "signature : texte non UTF-8".to_string())?;
    let signature = signature.trim();
    let cle = ClePublique::du_paquet_poste().map_err(|e| format!("clé publique committée : {e}"))?;
    cle.verifier(&zip, signature).map_err(|e| format!("{paquet} : {e}"))?;
    fs::write(sortie, assembler(&lire(lanceur)?, &zip, signature)).map_err(|e| format!("écriture de {sortie} : {e}"))?;
    println!("Setup écrit dans {sortie}");
    Ok(())
}

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let [lanceur, paquet, signature, sortie] = arguments.as_slice() else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    match assembler_le_setup(lanceur, paquet, signature, sortie) {
        Ok(()) => ExitCode::SUCCESS,
        Err(erreur) => {
            eprintln!("setup-poste : {erreur}");
            ExitCode::FAILURE
        }
    }
}
