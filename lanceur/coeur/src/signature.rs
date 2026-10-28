//! Signature ed25519 du Paquet poste (ADR-0022) : la CI signe avec la clé secrète
//! (secret GitHub `POSTE_CLE_SIGNATURE`), le Lanceur vérifie avec la clé publique
//! compilée. Clés et signatures circulent en base64.

use std::fmt;

use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};

/// Clé publique du Paquet poste, committée dans `lanceur/` (`cle-poste generer` la réécrit).
pub const CLE_PUBLIQUE_POSTE: &str = include_str!("../../cle-publique-poste.txt");

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ErreurSignature {
    CleInvalide,
    SignatureMalformee,
    SignatureInvalide,
}

impl fmt::Display for ErreurSignature {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::CleInvalide => "clé ed25519 invalide (attendu : 32 octets en base64)",
            Self::SignatureMalformee => "signature malformée (attendu : 64 octets en base64)",
            Self::SignatureInvalide => "signature invalide : paquet altéré ou signé par une autre clé",
        })
    }
}

impl std::error::Error for ErreurSignature {}

fn decoder<const N: usize>(texte: &str) -> Option<[u8; N]> {
    STANDARD.decode(texte.trim()).ok()?.try_into().ok()
}

pub struct ClePublique(VerifyingKey);

impl ClePublique {
    pub fn du_paquet_poste() -> Result<Self, ErreurSignature> {
        Self::depuis_texte(CLE_PUBLIQUE_POSTE)
    }

    pub fn depuis_texte(texte: &str) -> Result<Self, ErreurSignature> {
        let octets = decoder::<32>(texte).ok_or(ErreurSignature::CleInvalide)?;
        VerifyingKey::from_bytes(&octets).map(Self).map_err(|_| ErreurSignature::CleInvalide)
    }

    pub fn en_texte(&self) -> String {
        STANDARD.encode(self.0.as_bytes())
    }

    /// `signature` : contenu du fichier `.sig` publié à côté du paquet.
    pub fn verifier(&self, contenu: &[u8], signature: &str) -> Result<(), ErreurSignature> {
        let octets = decoder::<64>(signature).ok_or(ErreurSignature::SignatureMalformee)?;
        self.0
            .verify_strict(contenu, &Signature::from_bytes(&octets))
            .map_err(|_| ErreurSignature::SignatureInvalide)
    }
}

pub struct CleSecrete(SigningKey);

impl CleSecrete {
    pub fn generer() -> Self {
        let mut graine = [0u8; 32];
        getrandom::getrandom(&mut graine).expect("générateur aléatoire du système");
        Self(SigningKey::from_bytes(&graine))
    }

    pub fn depuis_texte(texte: &str) -> Result<Self, ErreurSignature> {
        decoder::<32>(texte).map(|graine| Self(SigningKey::from_bytes(&graine))).ok_or(ErreurSignature::CleInvalide)
    }

    pub fn en_texte(&self) -> String {
        STANDARD.encode(self.0.to_bytes())
    }

    pub fn cle_publique(&self) -> ClePublique {
        ClePublique(self.0.verifying_key())
    }

    pub fn signer(&self, contenu: &[u8]) -> String {
        STANDARD.encode(self.0.sign(contenu).to_bytes())
    }
}
