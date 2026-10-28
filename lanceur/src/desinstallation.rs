//! Désinstallation depuis « Applications installées » (`BBASS.exe --desinstaller`, spec 1.6.2 point 12),
//! sans fenêtre Tauri : boîtes de dialogue Windows seulement.
//!
//! Windows n'efface pas un exe en cours d'exécution : le `BBASS.exe` installé se copie dans le
//! dossier temporaire et relance la copie, qui arrête le BBASS en cours, retire le programme,
//! puis s'efface elle-même.

use std::path::Path;
use std::process::Command;
use std::thread;
use std::time::{Duration, Instant};

use bbass_lanceur_coeur::journal::Journal;
use bbass_lanceur_coeur::lancement::{ARGUMENT_ARRET, ARGUMENT_ATTENDRE_FIN, ARGUMENT_DESINSTALLATION};
use bbass_lanceur_coeur::setup;

use crate::systeme;

/// Le Lanceur arrêté, son backend suit (Job Object) ; un antivirus peut retenir un fichier un moment.
const ATTENTE_MAX: Duration = Duration::from_secs(30);
const NOUVEL_ESSAI: Duration = Duration::from_millis(500);

const CONFIRMATION: &str = "Désinstaller BBASS ?\n\n\
    Le programme, ses versions, le démarrage avec Windows et votre Session sont retirés. \
    La configuration (adresse du Serveur BBASS) est gardée ; vos conversations restent sur le Serveur BBASS.";

/// `racine` : `%LOCALAPPDATA%\BBASS`.
pub fn executer(racine: &Path, journal: &Journal) {
    let Ok(exe) = std::env::current_exe() else {
        return systeme::informer("BBASS n'a pas pu être désinstallé : programme introuvable.", true);
    };
    if exe.parent() == Some(racine) {
        if systeme::confirmer(CONFIRMATION) {
            relancer_depuis_une_copie(&exe, journal);
        }
        return;
    }
    retirer(racine, journal);
    effacer_plus_tard(&exe);
}

fn relancer_depuis_une_copie(exe: &Path, journal: &Journal) {
    let copie = std::env::temp_dir().join(format!("BBASS-desinstallation-{}.exe", std::process::id()));
    let relance = std::fs::copy(exe, &copie).and_then(|_| {
        Command::new(&copie)
            .arg(ARGUMENT_DESINSTALLATION)
            .arg(ARGUMENT_ATTENDRE_FIN)
            .arg(std::process::id().to_string())
            .spawn()
    });
    if let Err(erreur) = relance {
        crate::ecrire_au_journal(journal, &format!("Désinstallation : copie dans {} impossible : {erreur}", copie.display()));
        systeme::informer("BBASS n'a pas pu être désinstallé. Réessayez après avoir redémarré Windows.", true);
    }
}

fn retirer(racine: &Path, journal: &Journal) {
    crate::ecrire_au_journal(journal, "Désinstallation demandée");
    // Transmis par l'instance unique au BBASS en cours, qui quitte ; sans BBASS en cours, quitte aussitôt.
    let installe = racine.join("BBASS.exe");
    if installe.is_file() {
        let _ = Command::new(&installe).arg(ARGUMENT_ARRET).status();
    }
    systeme::retirer();

    let debut = Instant::now();
    let resultat = loop {
        match setup::desinstaller(racine) {
            Err(_) if debut.elapsed() < ATTENTE_MAX => thread::sleep(NOUVEL_ESSAI),
            resultat => break resultat,
        }
    };
    match resultat {
        Ok(()) => {
            crate::ecrire_au_journal(journal, "BBASS désinstallé ; configuration et journaux gardés");
            systeme::informer(
                &format!(
                    "BBASS a été désinstallé.\n\nLa configuration et les journaux restent dans {}.",
                    racine.display()
                ),
                false,
            );
        }
        Err(erreur) => {
            crate::ecrire_au_journal(journal, &format!("Désinstallation incomplète : {erreur}"));
            systeme::informer(
                &format!(
                    "BBASS est désinstallé, mais certains fichiers sont encore utilisés. \
                     Redémarrez Windows puis supprimez {}\\versions et {}\\BBASS.exe.",
                    racine.display(),
                    racine.display()
                ),
                true,
            );
        }
    }
}

/// La copie temporaire ne peut pas s'effacer pendant qu'elle tourne : `cmd` le fait juste après.
#[cfg(windows)]
fn effacer_plus_tard(exe: &Path) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    // Ligne passée telle quelle : `cmd /C` retirerait les guillemets d'un argument cité par Rust.
    let _ = Command::new("cmd")
        .raw_arg(format!("/C ping -n 3 127.0.0.1 >NUL & del /F /Q \"{}\"", exe.display()))
        .creation_flags(CREATE_NO_WINDOW)
        .spawn();
}

#[cfg(not(windows))]
fn effacer_plus_tard(exe: &Path) {
    let _ = std::fs::remove_file(exe);
}
