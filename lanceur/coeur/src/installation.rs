//! Dossier d'installation du Poste (`%LOCALAPPDATA%\BBASS`, ADR-0022) :
//!
//! ```text
//! BBASS.exe                Lanceur de la version courante
//! BBASS.old.exe            Lanceur précédent, pendant l'essai d'une bascule
//! versions\vX.Y.Z\         Paquet poste décompressé (BBASS.exe, poste-backend\)
//! versions\installation.json   version précédente gardée, bascule en cours
//! ```

use std::fs::{self, File};
use std::io::{self, Cursor};
use std::path::{Component, Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::version::Version;

const EXE: &str = "BBASS.exe";
/// Windows renomme un exe en cours d'exécution mais ne l'écrase pas.
const EXE_PRECEDENT: &str = "BBASS.old.exe";
/// Lanceur d'une version qui n'a pas répondu, mis de côté par le retour arrière.
const EXE_EN_ECHEC: &str = "BBASS.echec.exe";
const VERSIONS: &str = "versions";
const ETAT: &str = "installation.json";

/// Bascule de `de` vers `vers` faite, pas encore confirmée par la réponse du nouveau backend.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Bascule {
    pub de: Version,
    pub vers: Version,
}

#[derive(Debug, Default, Serialize, Deserialize)]
struct Etat {
    precedente: Option<Version>,
    bascule: Option<Bascule>,
}

pub struct Installation {
    racine: PathBuf,
}

impl Installation {
    pub fn new(racine: PathBuf) -> Self {
        Self { racine }
    }

    fn exe(&self) -> PathBuf {
        self.racine.join(EXE)
    }

    fn versions(&self) -> PathBuf {
        self.racine.join(VERSIONS)
    }

    fn dossier(&self, version: Version) -> PathBuf {
        self.versions().join(format!("v{version}"))
    }

    /// Backend de `version` ; à défaut, celui posé à côté de `BBASS.exe` (paquet construit en local).
    pub fn backend(&self, version: Version) -> PathBuf {
        let backend = |dossier: PathBuf| dossier.join("poste-backend").join("poste-backend.exe");
        let installe = backend(self.dossier(version));
        if installe.exists() {
            installe
        } else {
            backend(self.racine.clone())
        }
    }

    fn lire_etat(&self) -> Etat {
        fs::read_to_string(self.versions().join(ETAT))
            .ok()
            .and_then(|texte| serde_json::from_str(&texte).ok())
            .unwrap_or_default()
    }

    fn ecrire_etat(&self, etat: &Etat) -> io::Result<()> {
        fs::create_dir_all(self.versions())?;
        let texte = serde_json::to_string_pretty(etat).map_err(io::Error::other)?;
        fs::write(self.versions().join(ETAT), texte)
    }

    pub fn bascule(&self) -> Option<Bascule> {
        self.lire_etat().bascule
    }

    pub fn oublier_la_bascule(&self) -> io::Result<()> {
        let etat = Etat { bascule: None, ..self.lire_etat() };
        self.ecrire_etat(&etat)
    }

    /// Supprime les Lanceurs mis de côté et toute version autre que `courante` et la précédente gardée.
    /// Au mieux : un fichier encore ouvert sera supprimé au lancement suivant.
    pub fn nettoyer(&self, courante: Version) {
        let _ = fs::remove_file(self.racine.join(EXE_PRECEDENT));
        let _ = fs::remove_file(self.racine.join(EXE_EN_ECHEC));
        let gardees = [Some(courante), self.lire_etat().precedente];
        let gardees: Vec<String> = gardees.iter().flatten().map(|v| format!("v{v}")).collect();
        let Ok(entrees) = fs::read_dir(self.versions()) else {
            return;
        };
        for entree in entrees.flatten() {
            let nom = entree.file_name().to_string_lossy().into_owned();
            if entree.path().is_dir() && !gardees.contains(&nom) {
                let _ = fs::remove_dir_all(entree.path());
            }
        }
    }

    /// Décompresse le Paquet poste `zip` (signature déjà vérifiée) dans `versions\vX.Y.Z\`.
    pub fn installer(&self, version: Version, zip: &[u8]) -> Result<(), String> {
        let partiel = self.versions().join(format!(".v{version}.partiel"));
        let _ = fs::remove_dir_all(&partiel);
        let resultat = extraire(zip, &partiel).and_then(|()| {
            let backend = partiel.join("poste-backend").join("poste-backend.exe");
            if !partiel.join(EXE).is_file() || !backend.is_file() {
                return Err("le paquet ne contient pas BBASS.exe et poste-backend\\poste-backend.exe".to_string());
            }
            let dossier = self.dossier(version);
            let _ = fs::remove_dir_all(&dossier);
            fs::rename(&partiel, &dossier).map_err(|e| format!("impossible de poser {} ({e})", dossier.display()))
        });
        if resultat.is_err() {
            let _ = fs::remove_dir_all(&partiel);
        }
        resultat
    }

    /// Met le Lanceur de `vers` à la place de celui de `de`, gardé en `BBASS.old.exe`.
    pub fn basculer(&self, de: Version, vers: Version) -> io::Result<()> {
        let precedent = self.racine.join(EXE_PRECEDENT);
        let _ = fs::remove_file(&precedent);
        fs::rename(self.exe(), &precedent)?;
        let pose = fs::copy(self.dossier(vers).join(EXE), self.exe())
            .and_then(|_| self.ecrire_etat(&Etat { bascule: Some(Bascule { de, vers }), ..self.lire_etat() }));
        if let Err(erreur) = pose {
            let _ = fs::remove_file(self.exe());
            let _ = fs::rename(&precedent, self.exe());
            return Err(erreur);
        }
        Ok(())
    }

    /// Le nouveau backend a répondu : la version de départ devient la précédente gardée.
    pub fn confirmer(&self, bascule: Bascule) -> io::Result<()> {
        self.ecrire_etat(&Etat { precedente: Some(bascule.de), bascule: None })
    }

    /// Remet `BBASS.old.exe` en `BBASS.exe` ; la bascule reste notée pour le Lanceur rétabli.
    pub fn revenir(&self) -> io::Result<()> {
        let en_echec = self.racine.join(EXE_EN_ECHEC);
        let _ = fs::remove_file(&en_echec);
        fs::rename(self.exe(), &en_echec)?;
        if let Err(erreur) = fs::rename(self.racine.join(EXE_PRECEDENT), self.exe()) {
            let _ = fs::rename(&en_echec, self.exe());
            return Err(erreur);
        }
        Ok(())
    }
}

fn extraire(zip: &[u8], dossier: &Path) -> Result<(), String> {
    let illisible = |e: zip::result::ZipError| format!("archive illisible ({e})");
    let mut archive = zip::ZipArchive::new(Cursor::new(zip)).map_err(illisible)?;
    for i in 0..archive.len() {
        let mut entree = archive.by_index(i).map_err(illisible)?;
        // Compress-Archive de Windows PowerShell écrit des « \ ».
        let nom = entree.name().replace('\\', "/");
        let relatif = chemin_relatif(&nom).ok_or_else(|| format!("chemin refusé dans l'archive : {nom}"))?;
        let cible = dossier.join(relatif);
        let mut ecrire = || -> io::Result<()> {
            if nom.ends_with('/') {
                return fs::create_dir_all(&cible);
            }
            if let Some(parent) = cible.parent() {
                fs::create_dir_all(parent)?;
            }
            io::copy(&mut entree, &mut File::create(&cible)?).map(|_| ())
        };
        ecrire().map_err(|e| format!("décompression impossible ({e})"))?;
    }
    Ok(())
}

/// Chemin d'une entrée, refusé s'il sort du dossier de version (`..`, absolu, lecteur).
fn chemin_relatif(nom: &str) -> Option<PathBuf> {
    let chemin = PathBuf::from(nom.trim_end_matches('/'));
    let sur = chemin.components().all(|c| matches!(c, Component::Normal(_) | Component::CurDir));
    (sur && chemin.components().next().is_some() && !nom.contains(':')).then_some(chemin)
}
