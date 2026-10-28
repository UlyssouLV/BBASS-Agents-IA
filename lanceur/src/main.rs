// Pas de console sous la fenêtre BBASS en release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;

use std::net::{Ipv4Addr, SocketAddr};
use std::path::PathBuf;
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use bbass_lanceur_coeur::attente::attendre_reponse;
use sidecar::Sidecar;
use tauri::{Manager, RunEvent, Url, WebviewWindow};

/// Port local du backend poste, inchangé depuis la V1 (`POSTE_PORT`).
const PORT_POSTE: u16 = 8100;
/// Premier démarrage d'un backend PyInstaller : antivirus et disque froid compris.
const DELAI_DEMARRAGE: Duration = Duration::from_secs(90);

struct Backend(Mutex<Option<Sidecar>>);

/// `poste-backend\poste-backend.exe` à côté de `BBASS.exe` (forme du Paquet poste).
fn chemin_du_backend() -> std::io::Result<PathBuf> {
    let exe = std::env::current_exe()?;
    let dossier = exe.parent().map(PathBuf::from).unwrap_or_default();
    Ok(dossier.join("poste-backend").join("poste-backend.exe"))
}

fn afficher_erreur(fenetre: &WebviewWindow, message: &str) {
    let message = message.replace('\\', "\\\\").replace('"', "\\\"");
    let _ = fenetre.eval(format!("window.afficherErreur(\"{message}\")"));
}

fn demarrer_le_poste(fenetre: WebviewWindow) {
    let sidecar = match chemin_du_backend().and_then(|exe| Sidecar::demarrer(&exe)) {
        Ok(sidecar) => sidecar,
        Err(_) => {
            afficher_erreur(
                &fenetre,
                "BBASS n'a pas pu démarrer : l'installation semble incomplète. Réinstallez BBASS.",
            );
            return;
        }
    };
    *fenetre.state::<Backend>().0.lock().unwrap() = Some(sidecar);

    let adresse = SocketAddr::from((Ipv4Addr::LOCALHOST, PORT_POSTE));
    if attendre_reponse(adresse, DELAI_DEMARRAGE) {
        let url = Url::parse(&format!("http://127.0.0.1:{PORT_POSTE}/")).expect("URL locale valide");
        let _ = fenetre.navigate(url);
    } else {
        afficher_erreur(&fenetre, "BBASS ne répond pas. Fermez la fenêtre puis relancez BBASS.");
    }
}

fn main() {
    let app = tauri::Builder::default()
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            let fenetre = app
                .get_webview_window("principale")
                .expect("fenêtre déclarée dans tauri.conf.json");
            thread::spawn(move || demarrer_le_poste(fenetre));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("construction de l'application Tauri");

    app.run(|handle, evenement| {
        if let RunEvent::Exit = evenement {
            if let Some(mut sidecar) = handle.state::<Backend>().0.lock().unwrap().take() {
                sidecar.arreter();
            }
        }
    });
}
