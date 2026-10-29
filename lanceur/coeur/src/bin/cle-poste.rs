//! Clé de signature du Paquet poste (ADR-0022), depuis `lanceur/` :
//!
//! - `cargo run -p bbass-lanceur-coeur --bin cle-poste -- generer <fichier-cle-secrete>` :
//!   écrit la clé secrète (à coller dans le secret GitHub `POSTE_CLE_SIGNATURE`) et
//!   réécrit `lanceur/cle-publique-poste.txt`, à committer.
//! - `… -- signer <paquet>` : signe avec `POSTE_CLE_SIGNATURE`, écrit `<paquet>.sig`.
//! - `… -- verifier <paquet> <signature>` : vérifie avec la clé publique compilée.

use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::{env, fs};

use bbass_lanceur_coeur::signature::{ClePublique, CleSecrete};

const VARIABLE_CLE_SECRETE: &str = "POSTE_CLE_SIGNATURE";
const USAGE: &str = "usage : cle-poste generer <fichier-cle-secrete> | signer <paquet> | verifier <paquet> <signature>";

fn chemin_cle_publique() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("cle-publique-poste.txt")
}

fn generer(cle_secrete: &Path) -> Result<(), String> {
    if cle_secrete.exists() {
        return Err(format!("{} existe déjà : choisissez un autre fichier.", cle_secrete.display()));
    }
    let cle = CleSecrete::generer();
    fs::write(cle_secrete, cle.en_texte() + "\n").map_err(|e| format!("écriture de {} : {e}", cle_secrete.display()))?;
    let publique = chemin_cle_publique();
    fs::write(&publique, cle.cle_publique().en_texte() + "\n").map_err(|e| format!("écriture de {} : {e}", publique.display()))?;
    println!("Clé secrète écrite dans {}", cle_secrete.display());
    println!("  → la coller dans le secret GitHub {VARIABLE_CLE_SECRETE}, en ranger une copie dans le gestionnaire de mots de passe, puis supprimer ce fichier.");
    println!("Clé publique écrite dans {} : à committer.", publique.display());
    Ok(())
}

fn lire(chemin: &str) -> Result<Vec<u8>, String> {
    fs::read(chemin).map_err(|e| format!("lecture de {chemin} : {e}"))
}

fn signer(paquet: &str) -> Result<(), String> {
    let texte = env::var(VARIABLE_CLE_SECRETE).unwrap_or_default();
    if texte.trim().is_empty() {
        return Err(format!("la variable {VARIABLE_CLE_SECRETE} est vide ou absente : aucune clé pour signer."));
    }
    let cle = CleSecrete::depuis_texte(&texte).map_err(|e| format!("{VARIABLE_CLE_SECRETE} : {e}"))?;
    let sortie = format!("{paquet}.sig");
    fs::write(&sortie, cle.signer(&lire(paquet)?) + "\n").map_err(|e| format!("écriture de {sortie} : {e}"))?;
    println!("Signature écrite dans {sortie}");
    Ok(())
}

fn verifier(paquet: &str, signature: &str) -> Result<(), String> {
    let cle = ClePublique::du_paquet_poste().map_err(|e| format!("clé publique committée : {e}"))?;
    let signature = String::from_utf8(lire(signature)?).map_err(|_| "signature : texte non UTF-8".to_string())?;
    cle.verifier(&lire(paquet)?, &signature).map_err(|e| format!("{paquet} : {e}"))?;
    println!("Signature valide pour {paquet}");
    Ok(())
}

fn main() -> ExitCode {
    let arguments: Vec<String> = env::args().skip(1).collect();
    let resultat = match arguments.iter().map(String::as_str).collect::<Vec<_>>()[..] {
        ["generer", cle_secrete] => generer(Path::new(cle_secrete)),
        ["signer", paquet] => signer(paquet),
        ["verifier", paquet, signature] => verifier(paquet, signature),
        _ => Err(USAGE.to_string()),
    };
    match resultat {
        Ok(()) => ExitCode::SUCCESS,
        Err(erreur) => {
            eprintln!("Erreur : {erreur}");
            ExitCode::FAILURE
        }
    }
}
