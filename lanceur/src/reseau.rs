//! Réseau de la mise à jour : `GET /sante` sur le Serveur BBASS (LAN) et Paquet poste
//! depuis la GitHub Release (Internet). La logique est dans `bbass_lanceur_coeur::mise_a_jour`.

use std::io::Read;
use std::time::Duration;

use bbass_lanceur_coeur::mise_a_jour::Reseau;

/// Un Paquet poste pèse quelques dizaines de Mo ; au-delà, ce n'en est pas un.
const TAILLE_MAX: u64 = 1_000_000_000;
const MORCEAU: usize = 64 * 1024;

pub struct ReseauHttp {
    url_sante: String,
    serveur_bbass: ureq::Agent,
    releases: ureq::Agent,
}

impl ReseauHttp {
    pub fn new(url_sante: String) -> Self {
        // VM injoignable : démarrer vite sur la version installée.
        let serveur_bbass = ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_secs(3))
            .timeout(Duration::from_secs(5))
            .build();
        // Délai par lecture, pas global : une connexion lente finit son téléchargement.
        let releases = ureq::AgentBuilder::new()
            .timeout_connect(Duration::from_secs(10))
            .timeout_read(Duration::from_secs(30))
            .build();
        Self { url_sante, serveur_bbass, releases }
    }
}

impl Reseau for ReseauHttp {
    fn sante(&self) -> Option<String> {
        // 503 « base injoignable » annonce aussi la version.
        match self.serveur_bbass.get(&self.url_sante).call() {
            Ok(reponse) | Err(ureq::Error::Status(_, reponse)) => reponse.into_string().ok(),
            Err(_) => None,
        }
    }

    fn telecharger(&self, url: &str, progression: &mut dyn FnMut(u64, Option<u64>)) -> Result<Vec<u8>, String> {
        // L'erreur de ureq nomme déjà l'URL.
        let reponse = self.releases.get(url).call().map_err(|e| e.to_string())?;
        let total = reponse.header("Content-Length").and_then(|t| t.parse().ok());
        let mut lecteur = reponse.into_reader().take(TAILLE_MAX);
        let mut octets = Vec::with_capacity(total.unwrap_or(0).min(TAILLE_MAX) as usize);
        let mut morceau = vec![0u8; MORCEAU];
        loop {
            let lus = lecteur.read(&mut morceau).map_err(|e| format!("{url} : {e}"))?;
            if lus == 0 {
                return Ok(octets);
            }
            octets.extend_from_slice(&morceau[..lus]);
            progression(octets.len() as u64, total);
        }
    }
}
