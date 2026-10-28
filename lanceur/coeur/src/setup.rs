//! Setup du Poste (`BBASS-Setup-vX.Y.Z.exe`, spec 1.6.2 point 8) : le Lanceur lui-même,
//! suivi du Paquet poste signé de sa version (installation hors ligne possible).
//!
//! ```text
//! BBASS.exe | paquet.zip | signature | taille du zip (u64 LE) | taille de la signature (u64 LE) | MAGIE
//! ```
//!
//! Windows ignore ce qui suit l'image PE : le Setup se lance comme `BBASS.exe`.

use std::fs::{self, File};
use std::io::{self, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

use crate::configuration;
use crate::installation::Installation;
use crate::signature::ClePublique;
use crate::version::Version;

/// Résultat de la dernière vérification de mise à jour : propre à l'installation retirée.
const ETAT_MISE_A_JOUR: &str = "mise-a-jour.json";

const MAGIE: &[u8; 8] = b"BBASSPQ1";
const FIN: u64 = 8 + 8 + MAGIE.len() as u64;

/// Paquet poste et signature portés par le Setup.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PaquetEmbarque {
    pub zip: Vec<u8>,
    pub signature: String,
}

/// Réponses de l'assistant d'installation écrites dans `configuration.json`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Choix {
    pub hote: String,
    pub port: u16,
    pub demarrage_windows: bool,
}

/// Octets du Setup : `lanceur` suivi du Paquet poste et de sa signature.
pub fn assembler(lanceur: &[u8], zip: &[u8], signature: &str) -> Vec<u8> {
    let mut setup = Vec::with_capacity(lanceur.len() + zip.len() + signature.len() + FIN as usize);
    setup.extend_from_slice(lanceur);
    setup.extend_from_slice(zip);
    setup.extend_from_slice(signature.as_bytes());
    setup.extend_from_slice(&(zip.len() as u64).to_le_bytes());
    setup.extend_from_slice(&(signature.len() as u64).to_le_bytes());
    setup.extend_from_slice(MAGIE);
    setup
}

/// `None` : `exe` est un Lanceur installé, sans paquet derrière lui. Ne lit que la fin du fichier sinon.
pub fn lire_paquet_embarque(exe: &Path) -> io::Result<Option<PaquetEmbarque>> {
    let mut fichier = File::open(exe)?;
    let taille = fichier.metadata()?.len();
    if taille < FIN {
        return Ok(None);
    }
    let mut fin = [0u8; FIN as usize];
    fichier.seek(SeekFrom::Start(taille - FIN))?;
    fichier.read_exact(&mut fin)?;
    if &fin[16..] != MAGIE {
        return Ok(None);
    }
    let taille_zip = u64::from_le_bytes(fin[..8].try_into().expect("8 octets"));
    let taille_signature = u64::from_le_bytes(fin[8..16].try_into().expect("8 octets"));
    let debut = taille_zip
        .checked_add(taille_signature)
        .and_then(|charge| (taille - FIN).checked_sub(charge))
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "paquet embarqué tronqué"))?;
    fichier.seek(SeekFrom::Start(debut))?;
    let mut zip = vec![0u8; taille_zip as usize];
    fichier.read_exact(&mut zip)?;
    let mut signature = vec![0u8; taille_signature as usize];
    fichier.read_exact(&mut signature)?;
    let signature = String::from_utf8(signature).map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "signature non UTF-8"))?;
    Ok(Some(PaquetEmbarque { zip, signature }))
}

/// Installe `paquet` (version `version`) dans `racine` (`%LOCALAPPDATA%\BBASS`) et écrit la
/// configuration ; rend le `BBASS.exe` installé. Rien n'est posé si la signature est invalide.
/// `Err` : message en français pour l'assistant.
pub fn installer(
    racine: &Path,
    version: Version,
    paquet: &PaquetEmbarque,
    cle: &ClePublique,
    choix: &Choix,
) -> Result<PathBuf, String> {
    cle.verifier(&paquet.zip, &paquet.signature)
        .map_err(|e| format!("Ce Setup ne peut pas être installé : {e}. Téléchargez-le de nouveau."))?;
    let installation = Installation::new(racine.to_path_buf());
    installation.installer(version, &paquet.zip).map_err(|e| format!("Copie des fichiers impossible : {e}."))?;
    let exe = installation
        .poser_le_lanceur(version)
        .map_err(|e| format!("Copie de BBASS.exe impossible ({e}). Fermez BBASS s'il est ouvert, puis réessayez."))?;
    ecrire_la_configuration(racine, choix)
        .map_err(|e| format!("Écriture de la configuration impossible ({e})."))?;
    Ok(exe)
}

fn ecrire_la_configuration(racine: &Path, choix: &Choix) -> io::Result<()> {
    let fichier = racine.join(configuration::FICHIER);
    let existant = fs::read_to_string(&fichier).ok();
    let texte = configuration::avec_les_choix(existant.as_deref(), choix.hote.trim(), choix.port, choix.demarrage_windows);
    let provisoire = fichier.with_extension("json.tmp");
    fs::write(&provisoire, texte)?;
    fs::rename(&provisoire, &fichier)
}

/// Désinstallation (spec 1.6.2, point 12) : retire programme, versions et état de la mise à jour
/// de `racine` ; garde `configuration.json` et `journaux\`. Les Lanceurs doivent être arrêtés :
/// un fichier encore ouvert rend `Err`, à réessayer.
pub fn desinstaller(racine: &Path) -> io::Result<()> {
    Installation::new(racine.to_path_buf()).retirer()?;
    match fs::remove_file(racine.join(ETAT_MISE_A_JOUR)) {
        Err(erreur) if erreur.kind() != io::ErrorKind::NotFound => Err(erreur),
        _ => Ok(()),
    }
}
