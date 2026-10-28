//! Inscription du Poste dans Windows par le Setup et retrait à la désinstallation (spec 1.6.2,
//! points 8 et 12) : raccourcis, démarrage avec Windows, entrée d'« Applications installées »
//! et Session du gestionnaire d'identifiants. Tout est par utilisateur (`HKCU`), sans droits administrateur.

use std::io;
use std::path::{Path, PathBuf};

use bbass_lanceur_coeur::lancement::{ARGUMENT_DEMARRAGE_WINDOWS, ARGUMENT_DESINSTALLATION};

const NOM: &str = "BBASS";
const CLE_DEMARRAGE: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";
const CLE_DESINSTALLATION: &str = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\BBASS";
/// Session du backend (`poste/session.py`, keyring) : keyring écrit sous le nom du service
/// et, quand un autre utilisateur l'occupait, sous `utilisateur@service`.
const SESSIONS: [&str; 2] = ["bbass-agents-ia-poste", "session@bbass-agents-ia-poste"];
/// Processus console (backend, `cmd`) lancé sans fenêtre de terminal.
#[cfg(windows)]
pub const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Ce que l'assistant a coché à l'étape Options.
pub struct Options {
    pub demarrage_windows: bool,
    pub raccourci_bureau: bool,
}

fn raccourci_menu_demarrer() -> Option<PathBuf> {
    Some(dirs::data_dir()?.join(r"Microsoft\Windows\Start Menu\Programs").join(format!("{NOM}.lnk")))
}

fn raccourci_bureau() -> Option<PathBuf> {
    Some(dirs::desktop_dir()?.join(format!("{NOM}.lnk")))
}

fn ligne_de_commande(exe: &Path, argument: &str) -> String {
    format!("\"{}\" {argument}", exe.display())
}

#[cfg(windows)]
fn creer_raccourci(exe: &Path, raccourci: &Path) -> io::Result<()> {
    let mut lien = mslnk::ShellLink::new(exe).map_err(io::Error::other)?;
    lien.set_working_dir(exe.parent().map(|dossier| dossier.display().to_string()));
    lien.set_icon_location(Some(exe.display().to_string()));
    lien.set_name(Some(NOM.to_string()));
    if let Some(dossier) = raccourci.parent() {
        std::fs::create_dir_all(dossier)?;
    }
    lien.create_lnk(raccourci).map_err(io::Error::other)
}

fn supprimer(raccourci: Option<PathBuf>) {
    if let Some(raccourci) = raccourci {
        let _ = std::fs::remove_file(raccourci);
    }
}

/// Raccourcis, démarrage avec Windows (`--demarrage-windows`) et entrée de désinstallation pour `exe`.
#[cfg(windows)]
pub fn inscrire(exe: &Path, version: &str, options: &Options) -> io::Result<()> {
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    let introuvable = || io::Error::new(io::ErrorKind::NotFound, "dossier de l'utilisateur introuvable");
    creer_raccourci(exe, &raccourci_menu_demarrer().ok_or_else(introuvable)?)?;
    if options.raccourci_bureau {
        creer_raccourci(exe, &raccourci_bureau().ok_or_else(introuvable)?)?;
    } else {
        supprimer(raccourci_bureau());
    }

    let utilisateur = RegKey::predef(HKEY_CURRENT_USER);
    let (demarrage, _) = utilisateur.create_subkey(CLE_DEMARRAGE)?;
    if options.demarrage_windows {
        demarrage.set_value(NOM, &ligne_de_commande(exe, ARGUMENT_DEMARRAGE_WINDOWS))?;
    } else {
        let _ = demarrage.delete_value(NOM);
    }

    let (entree, _) = utilisateur.create_subkey(CLE_DESINSTALLATION)?;
    entree.set_value("DisplayName", &NOM)?;
    entree.set_value("DisplayVersion", &version)?;
    entree.set_value("Publisher", &NOM)?;
    entree.set_value("DisplayIcon", &exe.display().to_string())?;
    if let Some(dossier) = exe.parent() {
        entree.set_value("InstallLocation", &dossier.display().to_string())?;
    }
    entree.set_value("UninstallString", &ligne_de_commande(exe, ARGUMENT_DESINSTALLATION))?;
    entree.set_value("NoModify", &1u32)?;
    entree.set_value("NoRepair", &1u32)?;
    Ok(())
}

/// Après une mise à jour confirmée : « Applications installées » affiche la version qui tourne.
/// Sans entrée (poste non installé par le Setup), rien n'est créé.
#[cfg(windows)]
pub fn noter_la_version(version: &str) -> io::Result<()> {
    use winreg::enums::{HKEY_CURRENT_USER, KEY_SET_VALUE};
    use winreg::RegKey;

    let entree = match RegKey::predef(HKEY_CURRENT_USER).open_subkey_with_flags(CLE_DESINSTALLATION, KEY_SET_VALUE) {
        Err(erreur) if erreur.kind() == io::ErrorKind::NotFound => return Ok(()),
        entree => entree?,
    };
    entree.set_value("DisplayVersion", &version)
}

/// Désinstallation : retire raccourcis, démarrage avec Windows, entrée de désinstallation et Session.
/// Au mieux : ce qui est déjà absent est déjà retiré.
#[cfg(windows)]
pub fn retirer() {
    use windows_sys::Win32::Security::Credentials::{CredDeleteW, CRED_TYPE_GENERIC};
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    supprimer(raccourci_menu_demarrer());
    supprimer(raccourci_bureau());
    let utilisateur = RegKey::predef(HKEY_CURRENT_USER);
    if let Ok(demarrage) = utilisateur.open_subkey_with_flags(CLE_DEMARRAGE, winreg::enums::KEY_SET_VALUE) {
        let _ = demarrage.delete_value(NOM);
    }
    let _ = utilisateur.delete_subkey_all(CLE_DESINSTALLATION);
    for session in SESSIONS {
        let nom: Vec<u16> = session.encode_utf16().chain([0]).collect();
        // SAFETY : chaîne UTF-16 terminée par un zéro, vivante pendant l'appel.
        unsafe {
            CredDeleteW(nom.as_ptr(), CRED_TYPE_GENERIC, 0);
        }
    }
}

#[cfg(windows)]
fn boite(message: &str, style: u32) -> i32 {
    use windows_sys::Win32::UI::WindowsAndMessaging::MessageBoxW;

    let texte: Vec<u16> = message.encode_utf16().chain([0]).collect();
    let titre: Vec<u16> = NOM.encode_utf16().chain([0]).collect();
    // SAFETY : chaînes UTF-16 terminées par un zéro, vivantes pendant l'appel ; pas de fenêtre parente.
    unsafe { MessageBoxW(std::ptr::null_mut(), texte.as_ptr(), titre.as_ptr(), style) }
}

/// Oui / Non ; `true` sur Oui.
#[cfg(windows)]
pub fn confirmer(message: &str) -> bool {
    use windows_sys::Win32::UI::WindowsAndMessaging::{IDYES, MB_ICONQUESTION, MB_YESNO};
    boite(message, MB_YESNO | MB_ICONQUESTION) == IDYES
}

#[cfg(windows)]
pub fn informer(message: &str, erreur: bool) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{MB_ICONINFORMATION, MB_ICONWARNING, MB_OK};
    boite(message, MB_OK | if erreur { MB_ICONWARNING } else { MB_ICONINFORMATION });
}

#[cfg(not(windows))]
pub fn inscrire(_exe: &Path, _version: &str, _options: &Options) -> io::Result<()> {
    Err(io::Error::new(io::ErrorKind::Unsupported, "installation prévue pour Windows"))
}

#[cfg(not(windows))]
pub fn noter_la_version(_version: &str) -> io::Result<()> {
    Ok(())
}

#[cfg(not(windows))]
pub fn retirer() {}

#[cfg(not(windows))]
pub fn confirmer(_message: &str) -> bool {
    false
}

#[cfg(not(windows))]
pub fn informer(message: &str, _erreur: bool) {
    eprintln!("{message}");
}
