// Pas de console sous la fenêtre BBASS en release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod desinstallation;
mod installateur;
mod redemarrage;
mod reseau;
mod sidecar;
mod systeme;

use std::fs;
use std::net::{Ipv4Addr, SocketAddr};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use bbass_lanceur_coeur::attente::attendre_reponse;
use bbass_lanceur_coeur::configuration::url_de_la_sante;
use bbass_lanceur_coeur::journal::Journal;
use bbass_lanceur_coeur::lancement::{demande_d_arret, demande_de_verification, processus_a_attendre, Lancement};
use bbass_lanceur_coeur::mise_a_jour::{Etape, MiseAJour, Suite};
use bbass_lanceur_coeur::setup::lire_paquet_embarque;
use bbass_lanceur_coeur::signature::ClePublique;
use reseau::ReseauHttp;
use sidecar::Sidecar;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, RunEvent, Runtime, Url, WebviewWindow, WindowEvent};
use tauri_plugin_opener::OpenerExt;

/// Port local du backend poste, inchangé depuis la V1 (`POSTE_PORT`).
const PORT_POSTE: u16 = 8100;
const URL_POSTE: &str = "http://127.0.0.1:8100/";
/// Après « Vérifier les mises à jour maintenant » : le front ouvre À propos sur le résultat.
const URL_A_PROPOS: &str = "http://127.0.0.1:8100/?a-propos";
/// Premier démarrage d'un backend PyInstaller : antivirus et disque froid compris.
const DELAI_DEMARRAGE: Duration = Duration::from_secs(90);
/// 3 fichiers de 1 Mo au plus, comme le journal du backend.
const TAILLE_MAX_JOURNAL: u64 = 1_000_000;
const ARCHIVES_JOURNAL: u32 = 2;

struct Backend(Mutex<Option<Sidecar>>);

/// `%LOCALAPPDATA%\BBASS` : configuration, fichier d'état de la mise à jour et journaux, partagés avec le backend.
fn dossier_bbass() -> PathBuf {
    std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_default().join("BBASS")
}

/// `%LOCALAPPDATA%\BBASS\journaux\lanceur.log`, à côté de celui du backend.
fn journal() -> Journal {
    let chemin = dossier_bbass().join("journaux").join("lanceur.log");
    Journal::new(chemin, TAILLE_MAX_JOURNAL, ARCHIVES_JOURNAL)
}

/// Jamais de secret ni de jeton ici : le journal peut être envoyé à l'admin.
fn ecrire_au_journal(journal: &Journal, message: &str) {
    let horodatage = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
    journal.ecrire(&format!("{horodatage} {message}"));
}

fn journaliser<R: Runtime>(app: &impl Manager<R>, message: &str) {
    ecrire_au_journal(&app.state::<Journal>(), message);
}

fn afficher_erreur(fenetre: &WebviewWindow, message: &str) {
    let message = message.replace('\\', "\\\\").replace('"', "\\\"");
    let _ = fenetre.eval(format!("window.afficherErreur(\"{message}\")"));
}

fn montrer_la_fenetre(app: &AppHandle) {
    if let Some(fenetre) = app.get_webview_window("principale") {
        let _ = fenetre.show();
        let _ = fenetre.unminimize();
        let _ = fenetre.set_focus();
    }
}

/// « Vérifier les mises à jour maintenant » (À propos) : redémarrer sur ce `BBASS.exe` en mode
/// vérification, même parcours qu'au lancement (écran de démarrage, mise à jour, retour arrière).
fn verifier_maintenant(app: &AppHandle) {
    journaliser(app, "Vérification des mises à jour demandée depuis À propos");
    let relance = std::env::current_exe().and_then(|exe| redemarrage::lancer(&exe, Lancement::Verification));
    match relance {
        Ok(()) => app.exit(0),
        Err(erreur) => {
            journaliser(app, &format!("Redémarrage pour vérifier les mises à jour impossible : {erreur}"));
            montrer_la_fenetre(app);
        }
    }
}

fn installer_la_zone_de_notification(app: &AppHandle) -> tauri::Result<()> {
    let ouvrir = MenuItem::with_id(app, "ouvrir", "Ouvrir BBASS", true, None::<&str>)?;
    let navigateur = MenuItem::with_id(app, "navigateur", "Ouvrir dans le navigateur", true, None::<&str>)?;
    let separateur = PredefinedMenuItem::separator(app)?;
    let quitter = MenuItem::with_id(app, "quitter", "Quitter", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&ouvrir, &navigateur, &separateur, &quitter])?;

    let mut icone = TrayIconBuilder::with_id("bbass")
        .tooltip("BBASS")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, evenement| match evenement.id().as_ref() {
            "ouvrir" => montrer_la_fenetre(app),
            "navigateur" => {
                let _ = app.opener().open_url(URL_POSTE, None::<&str>);
            }
            "quitter" => {
                journaliser(app, "Quitter demandé depuis la zone de notification");
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|icone, evenement| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = evenement {
                montrer_la_fenetre(icone.app_handle());
            }
        });
    if let Some(image) = app.default_window_icon() {
        icone = icone.icon(image.clone());
    }
    icone.build(app)?;
    Ok(())
}

/// Écran de démarrage (`ecran/index.html`) ; la barre ne bouge qu'au pour cent près.
struct Ecran<'a> {
    fenetre: &'a WebviewWindow,
    pourcent: Option<u64>,
}

impl Ecran<'_> {
    fn afficher(&mut self, etape: Etape) {
        let (texte, progression) = match etape {
            Etape::Verification => ("Vérification…".to_string(), "undefined".to_string()),
            Etape::Demarrage => ("Démarrage…".to_string(), "undefined".to_string()),
            Etape::MiseAJour { version, recus, total } => {
                let pourcent = total.filter(|t| *t > 0).map(|t| (recus * 100 / t).min(100));
                if pourcent.is_some() && pourcent == self.pourcent {
                    return;
                }
                self.pourcent = pourcent;
                let progression = pourcent.map(|p| format!("{}", p as f64 / 100.0)).unwrap_or("null".into());
                (format!("Mise à jour vers v{version}…"), progression)
            }
        };
        let _ = self.fenetre.eval(format!("window.afficherEtape(\"{texte}\", {progression})"));
    }
}

/// `Err` : message pour l'utilisateur, la cause est au journal.
fn demarrer_le_backend(fenetre: &WebviewWindow, exe: &Path, lanceur: &Path) -> Result<(), &'static str> {
    let version = fenetre.package_info().version.to_string();
    let sidecar = Sidecar::demarrer(exe, &version, lanceur).map_err(|erreur| {
        journaliser(fenetre, &format!("Backend {} introuvable ou impossible à démarrer : {erreur}", exe.display()));
        "BBASS n'a pas pu démarrer : l'installation semble incomplète. Réinstallez BBASS."
    })?;
    *fenetre.state::<Backend>().0.lock().unwrap() = Some(sidecar);
    journaliser(fenetre, "Backend démarré");

    let adresse = SocketAddr::from((Ipv4Addr::LOCALHOST, PORT_POSTE));
    if !attendre_reponse(adresse, DELAI_DEMARRAGE) {
        journaliser(fenetre, &format!("Backend muet après {} s", DELAI_DEMARRAGE.as_secs()));
        return Err("BBASS ne répond pas. Quittez BBASS depuis la zone de notification puis relancez-le.");
    }
    journaliser(fenetre, &format!("Backend prêt sur {URL_POSTE}"));
    Ok(())
}

fn arreter_le_backend(fenetre: &WebviewWindow) {
    if let Some(mut sidecar) = fenetre.state::<Backend>().0.lock().unwrap().take() {
        sidecar.arreter();
    }
}

/// Redémarre sur `BBASS.exe` du dossier d'installation, posé par la bascule ou le retour arrière.
fn redemarrer(fenetre: &WebviewWindow, exe: &Path, lancement: Lancement) {
    match redemarrage::lancer(exe, lancement) {
        Ok(()) => {
            journaliser(fenetre, &format!("Redémarrage sur {}", exe.display()));
            fenetre.app_handle().exit(0);
        }
        Err(erreur) => {
            journaliser(fenetre, &format!("Redémarrage sur {} impossible : {erreur}", exe.display()));
            afficher_erreur(fenetre, "BBASS n'a pas pu redémarrer après sa mise à jour. Relancez BBASS.");
        }
    }
}

/// Séquence de l'ADR-0022 : se mettre à la version du Serveur BBASS, puis démarrer le backend.
fn demarrer_le_poste(fenetre: WebviewWindow, lancement: Lancement) {
    let racine = std::env::current_exe().ok().and_then(|exe| exe.parent().map(PathBuf::from)).unwrap_or_default();
    let version_poste = fenetre.package_info().version.to_string().parse().expect("version X.Y.Z du Lanceur");
    let cle = ClePublique::du_paquet_poste().expect("clé publique du Paquet poste compilée");
    let ecrire = |ligne: &str| journaliser(&fenetre, ligne);
    let horodatage = chrono::Local::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, false);
    let mise_a_jour =
        MiseAJour::new(racine.clone(), version_poste, dossier_bbass().join("mise-a-jour.json"), cle, horodatage, &ecrire);
    let configuration = fs::read_to_string(dossier_bbass().join("configuration.json")).ok();
    let reseau = ReseauHttp::new(url_de_la_sante(configuration.as_deref()));

    let mut ecran = Ecran { fenetre: &fenetre, pourcent: None };
    let essai = match mise_a_jour.au_lancement(&reseau, &mut |etape| ecran.afficher(etape)) {
        Suite::Redemarrer => return redemarrer(&fenetre, &racine.join("BBASS.exe"), lancement),
        Suite::Demarrer { essai } => essai,
    };
    match demarrer_le_backend(&fenetre, &mise_a_jour.backend(), &racine.join("BBASS.exe")) {
        Ok(()) => {
            if essai {
                mise_a_jour.confirmer();
            }
            let url = if lancement == Lancement::Verification { URL_A_PROPOS } else { URL_POSTE };
            let _ = fenetre.navigate(Url::parse(url).expect("URL locale valide"));
        }
        Err(_) if essai => {
            arreter_le_backend(&fenetre);
            match mise_a_jour.revenir() {
                Ok(()) => redemarrer(&fenetre, &racine.join("BBASS.exe"), lancement),
                Err(_) => afficher_erreur(&fenetre, "BBASS n'a pas pu démarrer sa nouvelle version. Réinstallez BBASS."),
            }
        }
        Err(message) => afficher_erreur(&fenetre, message),
    }
}

fn main() {
    let lancement = Lancement::depuis_arguments(std::env::args());
    // Avant l'instance unique : le Lanceur qui a redémarré sur nous doit avoir quitté.
    if let Some(pid) = processus_a_attendre(std::env::args()) {
        redemarrage::attendre_la_fin(pid);
    }
    if lancement == Lancement::Desinstallation {
        return desinstallation::executer(&dossier_bbass(), &journal());
    }
    let contexte = tauri::generate_context!();
    // Setup (paquet embarqué derrière l'exe) : l'assistant si rien n'est installé, sinon le BBASS installé.
    let setup = std::env::current_exe().ok().and_then(|exe| lire_paquet_embarque(&exe).ok().flatten());
    if let Some(paquet) = setup {
        let installe = dossier_bbass().join("BBASS.exe");
        if !installe.is_file() {
            return installateur::executer(contexte, paquet);
        }
        if let Err(erreur) = redemarrage::lancer(&installe, Lancement::AvecFenetre) {
            ecrire_au_journal(&journal(), &format!("Setup : BBASS installé impossible à lancer : {erreur}"));
        }
        return;
    }
    let app = tauri::Builder::default()
        // En premier : un second BBASS.exe rouvre la fenêtre du premier puis s'arrête,
        // sans démarrer de second backend ; lancé par le backend, il demande une vérification.
        .plugin(tauri_plugin_single_instance::init(|app, arguments, _dossier| {
            if demande_d_arret(arguments.clone()) {
                journaliser(app, "Arrêt demandé par la désinstallation");
                app.exit(0);
            } else if demande_de_verification(arguments) {
                verifier_maintenant(app);
            } else {
                montrer_la_fenetre(app);
            }
        }))
        .plugin(tauri_plugin_opener::init())
        .manage(Backend(Mutex::new(None)))
        .manage(journal())
        .setup(move |app| {
            if lancement == Lancement::Arret {
                // Désinstallation sans BBASS en cours : rien à arrêter.
                app.handle().exit(0);
                return Ok(());
            }
            journaliser(app.handle(), &format!("BBASS {} démarre ({lancement:?})", app.package_info().version));
            installer_la_zone_de_notification(app.handle())?;
            let fenetre = app
                .get_webview_window("principale")
                .expect("fenêtre déclarée dans tauri.conf.json");
            if lancement != Lancement::EnFond {
                fenetre.show()?;
            }
            // Seul moment de mise à jour : jamais pendant que BBASS tourne en fond.
            thread::spawn(move || demarrer_le_poste(fenetre, lancement));
            Ok(())
        })
        .on_window_event(|fenetre, evenement| {
            // Fermer la fenêtre la cache : BBASS et le backend restent dans la zone de notification.
            if let WindowEvent::CloseRequested { api, .. } = evenement {
                api.prevent_close();
                let _ = fenetre.hide();
            }
        })
        .build(contexte)
        .expect("construction de l'application Tauri");

    app.run(|handle, evenement| {
        if let RunEvent::Exit = evenement {
            if let Some(mut sidecar) = handle.state::<Backend>().0.lock().unwrap().take() {
                sidecar.arreter();
                journaliser(handle, "Backend arrêté");
            }
        }
    });
}
