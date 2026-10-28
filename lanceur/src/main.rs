// Pas de console sous la fenêtre BBASS en release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;

use std::net::{Ipv4Addr, SocketAddr};
use std::path::PathBuf;
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use bbass_lanceur_coeur::attente::attendre_reponse;
use bbass_lanceur_coeur::journal::Journal;
use bbass_lanceur_coeur::lancement::Lancement;
use sidecar::Sidecar;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, RunEvent, Runtime, Url, WebviewWindow, WindowEvent};
use tauri_plugin_opener::OpenerExt;

/// Port local du backend poste, inchangé depuis la V1 (`POSTE_PORT`).
const PORT_POSTE: u16 = 8100;
const URL_POSTE: &str = "http://127.0.0.1:8100/";
/// Premier démarrage d'un backend PyInstaller : antivirus et disque froid compris.
const DELAI_DEMARRAGE: Duration = Duration::from_secs(90);
/// 3 fichiers de 1 Mo au plus, comme le journal du backend.
const TAILLE_MAX_JOURNAL: u64 = 1_000_000;
const ARCHIVES_JOURNAL: u32 = 2;

struct Backend(Mutex<Option<Sidecar>>);

/// `poste-backend\poste-backend.exe` à côté de `BBASS.exe` (forme du Paquet poste).
fn chemin_du_backend() -> std::io::Result<PathBuf> {
    let exe = std::env::current_exe()?;
    let dossier = exe.parent().map(PathBuf::from).unwrap_or_default();
    Ok(dossier.join("poste-backend").join("poste-backend.exe"))
}

/// `%LOCALAPPDATA%\BBASS\journaux\lanceur.log`, à côté de celui du backend.
fn journal() -> Journal {
    let local_app_data = std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_default();
    let chemin = local_app_data.join("BBASS").join("journaux").join("lanceur.log");
    Journal::new(chemin, TAILLE_MAX_JOURNAL, ARCHIVES_JOURNAL)
}

/// Jamais de secret ni de jeton ici : le journal peut être envoyé à l'admin.
fn journaliser<R: Runtime>(app: &impl Manager<R>, message: &str) {
    let horodatage = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
    app.state::<Journal>().ecrire(&format!("{horodatage} {message}"));
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

fn demarrer_le_poste(fenetre: WebviewWindow) {
    let sidecar = match chemin_du_backend().and_then(|exe| Sidecar::demarrer(&exe)) {
        Ok(sidecar) => sidecar,
        Err(erreur) => {
            journaliser(&fenetre, &format!("Backend introuvable ou impossible à démarrer : {erreur}"));
            afficher_erreur(
                &fenetre,
                "BBASS n'a pas pu démarrer : l'installation semble incomplète. Réinstallez BBASS.",
            );
            return;
        }
    };
    *fenetre.state::<Backend>().0.lock().unwrap() = Some(sidecar);
    journaliser(&fenetre, "Backend démarré");

    let adresse = SocketAddr::from((Ipv4Addr::LOCALHOST, PORT_POSTE));
    if attendre_reponse(adresse, DELAI_DEMARRAGE) {
        journaliser(&fenetre, &format!("Backend prêt sur {URL_POSTE}"));
        let url = Url::parse(URL_POSTE).expect("URL locale valide");
        let _ = fenetre.navigate(url);
    } else {
        journaliser(&fenetre, &format!("Backend muet après {} s", DELAI_DEMARRAGE.as_secs()));
        afficher_erreur(&fenetre, "BBASS ne répond pas. Quittez BBASS depuis la zone de notification puis relancez-le.");
    }
}

fn main() {
    let lancement = Lancement::depuis_arguments(std::env::args());
    let app = tauri::Builder::default()
        // En premier : un second BBASS.exe rouvre la fenêtre du premier puis s'arrête,
        // sans démarrer de second backend.
        .plugin(tauri_plugin_single_instance::init(|app, _arguments, _dossier| montrer_la_fenetre(app)))
        .plugin(tauri_plugin_opener::init())
        .manage(Backend(Mutex::new(None)))
        .manage(journal())
        .setup(move |app| {
            journaliser(app.handle(), &format!("BBASS {} démarre ({lancement:?})", app.package_info().version));
            installer_la_zone_de_notification(app.handle())?;
            let fenetre = app
                .get_webview_window("principale")
                .expect("fenêtre déclarée dans tauri.conf.json");
            if lancement == Lancement::AvecFenetre {
                fenetre.show()?;
            }
            thread::spawn(move || demarrer_le_poste(fenetre));
            Ok(())
        })
        .on_window_event(|fenetre, evenement| {
            // Fermer la fenêtre la cache : BBASS et le backend restent dans la zone de notification.
            if let WindowEvent::CloseRequested { api, .. } = evenement {
                api.prevent_close();
                let _ = fenetre.hide();
            }
        })
        .build(tauri::generate_context!())
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
