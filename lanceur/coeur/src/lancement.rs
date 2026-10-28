//! Mode de lancement du Lanceur, d'après sa ligne de commande.

/// Argument du lancement au démarrage de Windows (inscrit par l'installateur).
pub const ARGUMENT_DEMARRAGE_WINDOWS: &str = "--demarrage-windows";
/// `--attendre-fin <pid>` : posé par le Lanceur qui redémarre sur un autre `BBASS.exe`
/// (bascule, retour arrière). Sans attente, l'instance unique rendrait la main au partant.
pub const ARGUMENT_ATTENDRE_FIN: &str = "--attendre-fin";

/// Processus dont attendre la fin avant de démarrer, d'après `std::env::args()`.
pub fn processus_a_attendre(arguments: impl IntoIterator<Item = String>) -> Option<u32> {
    let mut arguments = arguments.into_iter().skip(1);
    arguments.find(|a| a == ARGUMENT_ATTENDRE_FIN)?;
    arguments.next()?.parse().ok()
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Lancement {
    /// Lancé par l'utilisateur : la fenêtre s'ouvre.
    AvecFenetre,
    /// Lancé avec Windows : BBASS tourne en fond, sans fenêtre, dans la zone de notification.
    EnFond,
}

impl Lancement {
    /// `arguments` comme `std::env::args()` : le premier est l'exe.
    pub fn depuis_arguments(arguments: impl IntoIterator<Item = String>) -> Self {
        if arguments.into_iter().skip(1).any(|a| a == ARGUMENT_DEMARRAGE_WINDOWS) {
            Self::EnFond
        } else {
            Self::AvecFenetre
        }
    }
}
