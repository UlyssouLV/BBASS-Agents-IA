//! Mode de lancement du Lanceur, d'après sa ligne de commande.

/// Argument du lancement au démarrage de Windows (inscrit par l'installateur).
pub const ARGUMENT_DEMARRAGE_WINDOWS: &str = "--demarrage-windows";
/// `--attendre-fin <pid>` : posé par le Lanceur qui redémarre sur un autre `BBASS.exe`
/// (bascule, retour arrière). Sans attente, l'instance unique rendrait la main au partant.
pub const ARGUMENT_ATTENDRE_FIN: &str = "--attendre-fin";
/// « Vérifier les mises à jour maintenant » (menu « … », À propos) : le backend lance
/// `BBASS.exe --verifier-mise-a-jour`, que l'instance unique transmet au Lanceur en cours ;
/// celui-ci redémarre avec cet argument (même parcours qu'au lancement, puis À propos).
pub const ARGUMENT_VERIFICATION: &str = "--verifier-mise-a-jour";
/// Entrée « Désinstaller » d'« Applications installées » (`HKCU\…\Uninstall`, posée par le Setup).
pub const ARGUMENT_DESINSTALLATION: &str = "--desinstaller";
/// Lancé par la désinstallation : l'instance unique le transmet au BBASS en cours, qui quitte.
pub const ARGUMENT_ARRET: &str = "--quitter";

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
    /// Relancé pour vérifier les mises à jour : la fenêtre s'ouvre ensuite sur À propos.
    Verification,
    /// Désinstallation, sans fenêtre Tauri (voir `ARGUMENT_DESINSTALLATION`).
    Desinstallation,
    /// Aucun BBASS en cours à arrêter : quitter tout de suite.
    Arret,
}

/// Arguments reçus par l'instance unique (le premier est l'exe) : le backend demande une vérification.
pub fn demande_de_verification(arguments: impl IntoIterator<Item = String>) -> bool {
    arguments.into_iter().skip(1).any(|a| a == ARGUMENT_VERIFICATION)
}

/// Arguments reçus par l'instance unique : la désinstallation demande l'arrêt.
pub fn demande_d_arret(arguments: impl IntoIterator<Item = String>) -> bool {
    arguments.into_iter().skip(1).any(|a| a == ARGUMENT_ARRET)
}

impl Lancement {
    /// `arguments` comme `std::env::args()` : le premier est l'exe.
    pub fn depuis_arguments(arguments: impl IntoIterator<Item = String>) -> Self {
        let arguments: Vec<String> = arguments.into_iter().skip(1).collect();
        if arguments.iter().any(|a| a == ARGUMENT_DESINSTALLATION) {
            Self::Desinstallation
        } else if arguments.iter().any(|a| a == ARGUMENT_ARRET) {
            Self::Arret
        } else if arguments.iter().any(|a| a == ARGUMENT_VERIFICATION) {
            Self::Verification
        } else if arguments.iter().any(|a| a == ARGUMENT_DEMARRAGE_WINDOWS) {
            Self::EnFond
        } else {
            Self::AvecFenetre
        }
    }
}
