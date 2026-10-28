//! Version X.Y.Z du Poste et du Serveur BBASS (tag de Release vX.Y.Z, `GET /sante`).

use std::fmt;
use std::str::FromStr;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct Version {
    majeur: u32,
    mineur: u32,
    correctif: u32,
}

impl FromStr for Version {
    type Err = String;

    /// `1.6.2` ou `v1.6.2` ; tout le reste (`dev` d'une VM hors image) est refusé.
    fn from_str(texte: &str) -> Result<Self, Self::Err> {
        let refus = || format!("version « {texte} » : attendu X.Y.Z");
        let chiffres = texte.trim().strip_prefix('v').unwrap_or(texte.trim());
        let mut parties = chiffres.split('.').map(|p| {
            if p.is_empty() || !p.bytes().all(|b| b.is_ascii_digit()) {
                return None;
            }
            p.parse::<u32>().ok()
        });
        match (parties.next(), parties.next(), parties.next(), parties.next()) {
            (Some(Some(majeur)), Some(Some(mineur)), Some(Some(correctif)), None) => {
                Ok(Self { majeur, mineur, correctif })
            }
            _ => Err(refus()),
        }
    }
}

impl TryFrom<String> for Version {
    type Error = String;

    fn try_from(texte: String) -> Result<Self, Self::Error> {
        texte.parse()
    }
}

impl From<Version> for String {
    fn from(version: Version) -> Self {
        version.to_string()
    }
}

impl fmt::Display for Version {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}.{}", self.majeur, self.mineur, self.correctif)
    }
}
