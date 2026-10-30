//! Setup du Poste (spec 1.6.2, point 8) : `BBASS-Setup-vX.Y.Z.exe` est le Lanceur suivi du Paquet
//! poste signé (`bbass_lanceur_coeur::setup`). Lancé sur un poste où rien n'est installé, il ouvre
//! l'assistant (`ecran/installateur/`, construit depuis `poste/frontend`) : Bienvenue, Serveur BBASS,
//! Options, Installation.

use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use bbass_lanceur_coeur::configuration::{self, serveur_configure};
use bbass_lanceur_coeur::lancement::Lancement;
use bbass_lanceur_coeur::mise_a_jour::version_annoncee;
use bbass_lanceur_coeur::setup::{self as coeur, Choix, PaquetEmbarque};
use bbass_lanceur_coeur::signature::ClePublique;
use serde::{Deserialize, Serialize};
use tauri::ipc::Channel;
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};

use crate::systeme;

const FENETRE: &str = "installation";

struct Setup {
    paquet: PaquetEmbarque,
    /// Une installation à la fois ; « Réessayer » en relance une après un échec.
    en_cours: AtomicBool,
    installe: Mutex<Option<PathBuf>>,
}

#[derive(Serialize)]
struct Informations {
    version: String,
    emplacement: String,
    hote: String,
    port: u16,
}

#[derive(Serialize)]
struct EtatServeur {
    joignable: bool,
    version: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Options {
    hote: String,
    port: u16,
    demarrage_windows: bool,
    raccourci_bureau: bool,
}

#[derive(Clone, Serialize)]
struct Progression {
    etape: &'static str,
    fraction: f64,
}

#[tauri::command]
fn informations(app: AppHandle) -> Informations {
    let racine = crate::dossier_bbass();
    let existante = fs::read_to_string(racine.join(configuration::FICHIER)).ok();
    let (hote, port) = serveur_configure(existante.as_deref());
    Informations { version: app.package_info().version.to_string(), emplacement: racine.display().to_string(), hote, port }
}

/// Pastille de l'étape Serveur BBASS : vert seulement sur 200, comme `/serveur-bbass/etat` du backend.
#[tauri::command]
async fn tester_serveur(hote: String, port: u16) -> EtatServeur {
    let url = format!("http://{}:{port}/sante", hote.trim());
    let version = tauri::async_runtime::spawn_blocking(move || {
        let agent = ureq::AgentBuilder::new().timeout_connect(Duration::from_secs(3)).timeout(Duration::from_secs(5)).build();
        let corps = agent.get(&url).call().ok()?.into_string().ok()?;
        version_annoncee(&corps)
    })
    .await
    .ok()
    .flatten();
    EtatServeur { joignable: version.is_some(), version }
}

#[tauri::command]
async fn installer(app: AppHandle, options: Options, progression: Channel<Progression>) -> Result<(), String> {
    let setup = app.state::<Setup>();
    if setup.en_cours.swap(true, Ordering::SeqCst) {
        return Err("L'installation est déjà en cours.".into());
    }
    let paquet = setup.paquet.clone();
    let version = app.package_info().version.to_string();
    let journal = app.clone();
    let resultat = tauri::async_runtime::spawn_blocking(move || {
        let etape = |etape, fraction| {
            let _ = progression.send(Progression { etape, fraction });
        };
        let racine = crate::dossier_bbass();
        etape("Copie des fichiers…", 0.1);
        let cle = ClePublique::du_paquet_poste().map_err(|e| e.to_string())?;
        let choix = Choix { hote: options.hote.clone(), port: options.port, demarrage_windows: options.demarrage_windows };
        let exe = coeur::installer(&racine, version.parse().map_err(|_| "version du Setup illisible")?, &paquet, &cle, &choix)?;
        etape("Raccourcis et démarrage avec Windows…", 0.8);
        let options = systeme::Options { demarrage_windows: options.demarrage_windows, raccourci_bureau: options.raccourci_bureau };
        systeme::inscrire(&exe, &version, &options)
            .map_err(|e| format!("Inscription dans Windows impossible ({e}). Relancez le Setup."))?;
        etape("BBASS est installé.", 1.0);
        Ok::<_, String>(exe)
    })
    .await
    .map_err(|e| e.to_string());
    journal.state::<Setup>().en_cours.store(false, Ordering::SeqCst);
    match resultat.and_then(|resultat| resultat) {
        Ok(exe) => {
            crate::journaliser(&journal, &format!("BBASS installé dans {}", exe.display()));
            *journal.state::<Setup>().installe.lock().unwrap() = Some(exe);
            Ok(())
        }
        Err(erreur) => {
            crate::journaliser(&journal, &format!("Installation impossible : {erreur}"));
            Err(erreur)
        }
    }
}

/// Dernière étape : le BBASS installé démarre (et se met à la version du Serveur BBASS) ; le Setup quitte.
#[tauri::command]
fn lancer_bbass(app: AppHandle) -> Result<(), String> {
    let exe = app.state::<Setup>().installe.lock().unwrap().clone().ok_or("BBASS n'est pas encore installé.")?;
    crate::redemarrage::lancer(&exe, Lancement::AvecFenetre).map_err(|e| format!("BBASS n'a pas pu démarrer ({e})."))?;
    app.exit(0);
    Ok(())
}

fn montrer(app: &AppHandle) {
    if let Some(fenetre) = app.get_webview_window(FENETRE) {
        let _ = fenetre.unminimize();
        let _ = fenetre.set_focus();
    }
}

pub fn executer(contexte: tauri::Context, paquet: PaquetEmbarque) {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _arguments, _dossier| montrer(app)))
        .manage(Setup { paquet, en_cours: AtomicBool::new(false), installe: Mutex::new(None) })
        .manage(crate::journal())
        .invoke_handler(tauri::generate_handler![informations, tester_serveur, installer, lancer_bbass])
        .setup(|app| {
            crate::journaliser(app.handle(), &format!("Setup BBASS {} ouvert", app.package_info().version));
            // La fenêtre du Lanceur (écran de démarrage) ne sert pas au Setup.
            if let Some(principale) = app.get_webview_window("principale") {
                principale.destroy()?;
            }
            WebviewWindowBuilder::new(app, FENETRE, WebviewUrl::App("installateur/installateur.html".into()))
                .title("Installer BBASS")
                .inner_size(760.0, 540.0)
                .resizable(false)
                .center()
                .build()?;
            Ok(())
        })
        .on_window_event(|fenetre, evenement| {
            if fenetre.label() == FENETRE && matches!(evenement, WindowEvent::Destroyed) {
                fenetre.app_handle().exit(0);
            }
        })
        .run(contexte)
        .expect("assistant d'installation");
}
