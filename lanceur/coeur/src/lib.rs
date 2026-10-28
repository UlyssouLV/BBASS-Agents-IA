//! Cœur du Lanceur BBASS (ADR-0022) : logique pure, sans Tauri ni réseau distant, testée par `cargo test`.

pub mod attente;
pub mod configuration;
mod installation;
pub mod journal;
pub mod lancement;
pub mod mise_a_jour;
pub mod signature;
pub mod version;
