//! Journal du Lanceur dans `%LOCALAPPDATA%\BBASS\journaux\`, avec rotation.
//!
//! Même forme que celui du backend (`RotatingFileHandler`) : `lanceur.log`,
//! puis `lanceur.log.1`… jusqu'à `archives`. Le Lanceur n'y écrit jamais de
//! secret ni de jeton.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

pub struct Journal {
    chemin: PathBuf,
    taille_max: u64,
    archives: u32,
    verrou: Mutex<()>,
}

impl Journal {
    pub fn new(chemin: PathBuf, taille_max: u64, archives: u32) -> Self {
        Self { chemin, taille_max, archives, verrou: Mutex::new(()) }
    }

    /// Ajoute `ligne`. Un journal impossible à écrire ne doit jamais empêcher BBASS de démarrer : l'erreur est ignorée.
    pub fn ecrire(&self, ligne: &str) {
        let _verrou = self.verrou.lock().unwrap_or_else(|e| e.into_inner());
        let _ = self.ajouter(ligne);
    }

    fn ajouter(&self, ligne: &str) -> std::io::Result<()> {
        if let Some(dossier) = self.chemin.parent() {
            fs::create_dir_all(dossier)?;
        }
        let ajout = ligne.len() as u64 + 1;
        let taille = fs::metadata(&self.chemin).map(|m| m.len()).unwrap_or(0);
        if taille > 0 && taille + ajout > self.taille_max {
            self.tourner();
        }
        let mut fichier = OpenOptions::new().create(true).append(true).open(&self.chemin)?;
        writeln!(fichier, "{ligne}")
    }

    fn tourner(&self) {
        if self.archives == 0 {
            let _ = fs::remove_file(&self.chemin);
            return;
        }
        let _ = fs::remove_file(self.archive(self.archives));
        for i in (1..self.archives).rev() {
            let _ = fs::rename(self.archive(i), self.archive(i + 1));
        }
        let _ = fs::rename(&self.chemin, self.archive(1));
    }

    fn archive(&self, numero: u32) -> PathBuf {
        let mut nom = self.chemin.file_name().unwrap_or_default().to_os_string();
        nom.push(format!(".{numero}"));
        self.chemin.parent().unwrap_or(Path::new(".")).join(nom)
    }
}
