//! Mise à jour au lancement sur la version du Serveur BBASS, avec retour arrière (ADR-0022).
//!
//! Sans réseau : `/sante` et les téléchargements passent par [`Reseau`], fourni
//! par le Lanceur. Ici : décision de version, signature, installation, bascule,
//! retour arrière, nettoyage et fichier d'état lu par le backend.

use std::fs;
use std::io;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::installation::{Bascule, Installation};
use crate::signature::ClePublique;
use crate::version::Version;

/// Releases publiques du dépôt : le Paquet poste y est joint (`publier-paquet-poste.yml`).
const RELEASES: &str = "https://github.com/UlyssouLV/BBASS-Agents-IA/releases/download";

pub trait Reseau {
    /// Corps de `GET /sante` sur le Serveur BBASS, quel que soit le statut ; `None` s'il est injoignable.
    fn sante(&self) -> Option<String>;
    /// `progression(reçus, total)` à mesure que les octets arrivent.
    fn telecharger(&self, url: &str, progression: &mut dyn FnMut(u64, Option<u64>)) -> Result<Vec<u8>, String>;
}

/// Ce qu'affiche l'écran de démarrage.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Etape {
    Verification,
    MiseAJour { version: Version, recus: u64, total: Option<u64> },
    Demarrage,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Suite {
    /// Démarrer le backend installé. `essai` : premier lancement après une bascule,
    /// à confirmer ([`MiseAJour::confirmer`]) ou défaire ([`MiseAJour::revenir`]) selon sa réponse.
    Demarrer { essai: bool },
    /// Nouveau Lanceur posé en `BBASS.exe` : redémarrer dessus.
    Redemarrer,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Resultat {
    AJour,
    MiseAJour,
    Echec,
    /// Le Serveur BBASS annonce une version sans Release (`dev` hors image).
    VersionNonPubliee,
}

/// Contenu du fichier d'état `%LOCALAPPDATA%\BBASS\mise-a-jour.json`, lu par le backend.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DerniereVerification {
    pub date: String,
    pub version_poste: Version,
    pub version_serveur: Option<String>,
    pub resultat: Resultat,
    /// En français, sans détail technique (le journal les garde).
    pub detail: String,
    /// Texte du bandeau de l'application ; `None` : pas de bandeau.
    pub bandeau: Option<String>,
}

/// Bandeau de l'application quand la mise à jour n'a pas abouti ; sans numéro si la VM est injoignable.
pub fn bandeau(version: Option<Version>) -> String {
    let vers = version.map(|v| format!(" vers v{v}")).unwrap_or_default();
    format!(
        "Mise à jour{vers} impossible : certaines fonctionnalités peuvent ne pas fonctionner \
         tant qu'elle n'a pas réussi. Nouvel essai au prochain lancement."
    )
}

pub fn url_du_paquet(version: Version) -> String {
    format!("{RELEASES}/v{version}/bbass-poste-v{version}-windows-x64.zip")
}

fn version_annoncee(sante: &str) -> Option<String> {
    let corps: serde_json::Value = serde_json::from_str(sante).ok()?;
    corps.get("version")?.as_str().map(str::to_string)
}

pub struct MiseAJour<'a> {
    installation: Installation,
    version_poste: Version,
    fichier_etat: PathBuf,
    cle: ClePublique,
    horodatage: String,
    journal: &'a dyn Fn(&str),
}

impl<'a> MiseAJour<'a> {
    /// `racine` : dossier de `BBASS.exe` ; `version_poste` : celle de ce Lanceur ;
    /// `horodatage` : date de cette vérification, écrite dans `fichier_etat`.
    pub fn new(
        racine: PathBuf,
        version_poste: Version,
        fichier_etat: PathBuf,
        cle: ClePublique,
        horodatage: String,
        journal: &'a dyn Fn(&str),
    ) -> Self {
        Self { installation: Installation::new(racine), version_poste, fichier_etat, cle, horodatage, journal }
    }

    pub fn backend(&self) -> PathBuf {
        self.installation.backend(self.version_poste)
    }

    pub fn au_lancement(&self, reseau: &dyn Reseau, ecran: &mut dyn FnMut(Etape)) -> Suite {
        let suite = self.suite_au_lancement(reseau, ecran);
        if let Suite::Demarrer { .. } = suite {
            ecran(Etape::Demarrage);
        }
        suite
    }

    fn suite_au_lancement(&self, reseau: &dyn Reseau, ecran: &mut dyn FnMut(Etape)) -> Suite {
        if let Some(bascule) = self.installation.bascule() {
            if bascule.vers == self.version_poste {
                (self.journal)(&format!("Essai de v{} après la bascule depuis v{}", bascule.vers, bascule.de));
                return Suite::Demarrer { essai: true };
            }
            let _ = self.installation.oublier_la_bascule();
            if bascule.de == self.version_poste {
                // Lanceur rétabli par `revenir` : pas de nouvel essai avant le prochain lancement.
                self.installation.nettoyer(self.version_poste);
                let detail = format!(
                    "La version v{} n'a pas répondu : retour à la version v{}.",
                    bascule.vers, bascule.de
                );
                (self.journal)(&detail);
                self.ecrire(Some(bascule.vers.to_string()), Resultat::Echec, detail, Some(bandeau(Some(bascule.vers))));
                return Suite::Demarrer { essai: false };
            }
        }
        self.installation.nettoyer(self.version_poste);
        ecran(Etape::Verification);
        self.verifier(reseau, ecran)
    }

    fn verifier(&self, reseau: &dyn Reseau, ecran: &mut dyn FnMut(Etape)) -> Suite {
        let Some(annoncee) = reseau.sante().as_deref().and_then(version_annoncee) else {
            (self.journal)("Serveur BBASS injoignable : démarrage sur la version installée");
            self.ecrire(None, Resultat::Echec, "Serveur BBASS injoignable.".into(), Some(bandeau(None)));
            return Suite::Demarrer { essai: false };
        };
        let Ok(cible) = annoncee.parse::<Version>() else {
            let detail = format!("Le Serveur BBASS annonce la version « {annoncee} », sans Paquet poste publié.");
            (self.journal)(&detail);
            self.ecrire(Some(annoncee), Resultat::VersionNonPubliee, detail, None);
            return Suite::Demarrer { essai: false };
        };
        if cible == self.version_poste {
            self.ecrire(Some(annoncee), Resultat::AJour, format!("Poste à jour en v{cible}."), None);
            return Suite::Demarrer { essai: false };
        }
        (self.journal)(&format!("Mise à jour de v{} vers v{cible}", self.version_poste));
        match self.mettre_a_jour(cible, reseau, ecran) {
            Ok(()) => {
                (self.journal)(&format!("Lanceur v{cible} posé : redémarrage"));
                Suite::Redemarrer
            }
            Err(detail) => {
                self.ecrire(Some(annoncee), Resultat::Echec, detail, Some(bandeau(Some(cible))));
                Suite::Demarrer { essai: false }
            }
        }
    }

    /// `Err` : détail en français pour le fichier d'état ; la cause technique va au journal.
    fn mettre_a_jour(&self, cible: Version, reseau: &dyn Reseau, ecran: &mut dyn FnMut(Etape)) -> Result<(), String> {
        let echec = |detail: String, cause: &dyn std::fmt::Display| {
            (self.journal)(&format!("{detail} ({cause})"));
            detail
        };
        let telechargement = || format!("Téléchargement du Paquet poste v{cible} impossible.");
        let url = url_du_paquet(cible);
        ecran(Etape::MiseAJour { version: cible, recus: 0, total: None });
        let paquet = reseau
            .telecharger(&url, &mut |recus, total| ecran(Etape::MiseAJour { version: cible, recus, total }))
            .map_err(|e| echec(telechargement(), &e))?;
        let signature = reseau.telecharger(&format!("{url}.sig"), &mut |_, _| {}).map_err(|e| echec(telechargement(), &e))?;
        self.cle
            .verifier(&paquet, &String::from_utf8_lossy(&signature))
            .map_err(|e| echec(format!("Paquet poste v{cible} refusé : signature invalide."), &e))?;
        self.installation
            .installer(cible, &paquet)
            .map_err(|e| echec(format!("Installation de la version v{cible} impossible."), &e))?;
        self.installation
            .basculer(self.version_poste, cible)
            .map_err(|e| echec(format!("Remplacement du Lanceur par la version v{cible} impossible."), &e))
    }

    /// Le backend de l'essai a répondu : la version devient courante, la précédente est gardée.
    pub fn confirmer(&self) {
        if let Some(bascule) = self.installation.bascule() {
            if let Err(erreur) = self.installation.confirmer(bascule) {
                (self.journal)(&format!("Confirmation de la bascule impossible ({erreur})"));
            }
            (self.journal)(&format!("Mise à jour vers v{} réussie", bascule.vers));
        }
        let version = self.version_poste;
        self.ecrire(Some(version.to_string()), Resultat::MiseAJour, format!("Mise à jour vers v{version} réussie."), None);
    }

    /// Le backend de l'essai n'a pas répondu : remet l'ancien Lanceur, à relancer ensuite.
    pub fn revenir(&self) -> io::Result<()> {
        let bascule = self.installation.bascule();
        (self.journal)(&format!("La version v{} n'a pas répondu : retour arrière", self.version_poste));
        let resultat = self.installation.revenir();
        if let Err(erreur) = &resultat {
            (self.journal)(&format!("Retour arrière impossible ({erreur})"));
            let _ = self.installation.oublier_la_bascule();
            let detail = format!(
                "La version v{} n'a pas répondu et l'ancienne version n'a pas pu être remise.",
                self.version_poste
            );
            let bandeau = bandeau(bascule.map(|b: Bascule| b.vers));
            self.ecrire(Some(self.version_poste.to_string()), Resultat::Echec, detail, Some(bandeau));
        }
        resultat
    }

    /// Écrit le résultat de la vérification ; un fichier impossible à écrire n'empêche pas BBASS de démarrer.
    fn ecrire(&self, version_serveur: Option<String>, resultat: Resultat, detail: String, bandeau: Option<String>) {
        let verification = DerniereVerification {
            date: self.horodatage.clone(),
            version_poste: self.version_poste,
            version_serveur,
            resultat,
            detail,
            bandeau,
        };
        let ecriture = serde_json::to_string_pretty(&verification).map_err(io::Error::other).and_then(|texte| {
            if let Some(dossier) = self.fichier_etat.parent() {
                fs::create_dir_all(dossier)?;
            }
            fs::write(&self.fichier_etat, texte)
        });
        if let Err(erreur) = ecriture {
            (self.journal)(&format!("Fichier d'état {} impossible à écrire ({erreur})", self.fichier_etat.display()));
        }
    }
}
