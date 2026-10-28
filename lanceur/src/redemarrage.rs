//! Redémarrage sur un autre `BBASS.exe` après une bascule ou un retour arrière (ADR-0022),
//! ou sur le même pour « Vérifier les mises à jour maintenant ».

use std::io;
use std::path::Path;
use std::process::Command;
use std::time::Duration;

use bbass_lanceur_coeur::lancement::{Lancement, ARGUMENT_ATTENDRE_FIN, ARGUMENT_DEMARRAGE_WINDOWS, ARGUMENT_VERIFICATION};

/// Au-delà, le Lanceur partant est bloqué : l'instance unique dira s'il tourne encore.
const ATTENTE_MAX: Duration = Duration::from_secs(30);

/// Lance `exe`, qui attendra la fin de ce processus (instance unique) ; à l'appelant de quitter ensuite.
pub fn lancer(exe: &Path, lancement: Lancement) -> io::Result<()> {
    let mut commande = Command::new(exe);
    match lancement {
        Lancement::EnFond => {
            commande.arg(ARGUMENT_DEMARRAGE_WINDOWS);
        }
        Lancement::Verification => {
            commande.arg(ARGUMENT_VERIFICATION);
        }
        Lancement::AvecFenetre => {}
    }
    commande.arg(ARGUMENT_ATTENDRE_FIN).arg(std::process::id().to_string());
    commande.spawn().map(|_| ())
}

#[cfg(windows)]
pub fn attendre_la_fin(pid: u32) {
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::Threading::{OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE};

    // SAFETY : handle ouvert ici, attendu puis fermé une seule fois ; nul si le processus est déjà fini.
    unsafe {
        let processus = OpenProcess(PROCESS_SYNCHRONIZE, 0, pid);
        if processus.is_null() {
            return;
        }
        WaitForSingleObject(processus, ATTENTE_MAX.as_millis() as u32);
        CloseHandle(processus);
    }
}

#[cfg(not(windows))]
pub fn attendre_la_fin(_pid: u32) {
    std::thread::sleep(Duration::from_secs(2).min(ATTENTE_MAX));
}
