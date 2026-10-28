//! Adresse du Serveur BBASS dans `%LOCALAPPDATA%\BBASS\configuration.json`, partagé
//! avec le backend (`poste/config.py`) : même format, même adresse prod par défaut.
//!
//! ```json
//! { "serveur_bbass": { "hote": "10.0.0.5", "port": 8000 } }
//! ```

/// Dans `%LOCALAPPDATA%\BBASS`.
pub const FICHIER: &str = "configuration.json";

/// Adresse prod par défaut (spec 1.6.2, point 10), comme `ADRESSE_PROD` du backend.
/// Vide tant qu'elle n'est pas connue : sans fichier de configuration, le Serveur BBASS
/// est injoignable et le poste ouvre la Configuration.
const ADRESSE_PROD: &str = "";

/// Port du Serveur BBASS proposé par l'assistant (`PORT_PAR_DEFAUT` du backend).
pub const PORT_PAR_DEFAUT: u16 = 8000;

fn serveur(contenu: &str) -> Option<(String, u16)> {
    let configuration: serde_json::Value = serde_json::from_str(contenu).ok()?;
    let serveur = configuration.get("serveur_bbass")?;
    let hote = serveur.get("hote")?.as_str()?.trim();
    let port = match serveur.get("port")? {
        serde_json::Value::String(port) => port.trim().parse::<u16>().ok()?,
        port => u16::try_from(port.as_u64()?).ok()?,
    };
    (!hote.is_empty()).then(|| (hote.to_string(), port))
}

fn adresse(contenu: &str) -> Option<String> {
    serveur(contenu).map(|(hote, port)| format!("http://{hote}:{port}"))
}

/// Hôte et port qui pré-remplissent l'assistant d'installation : ceux de la configuration
/// (gardée par la désinstallation), sinon ceux de l'adresse prod, sinon `("", 8000)`.
pub fn serveur_configure(contenu: Option<&str>) -> (String, u16) {
    contenu.and_then(serveur).unwrap_or_else(|| {
        let prod = ADRESSE_PROD.trim_start_matches("http://");
        match prod.rsplit_once(':') {
            Some((hote, port)) => (hote.to_string(), port.parse().unwrap_or(PORT_PAR_DEFAUT)),
            None => (prod.to_string(), PORT_PAR_DEFAUT),
        }
    })
}

/// `contenu` : texte du fichier de configuration, `None` s'il n'existe pas.
/// `None` sans adresse connue (ni fichier ni adresse prod).
pub fn url_de_la_sante(contenu: Option<&str>) -> Option<String> {
    let adresse = contenu.and_then(adresse).or_else(|| (!ADRESSE_PROD.is_empty()).then(|| ADRESSE_PROD.to_string()))?;
    Some(format!("{adresse}/sante"))
}

/// `contenu` réécrit avec l'adresse et le démarrage avec Windows choisis ; les autres réglages
/// sont gardés, comme le fait `PUT /configuration` du backend.
pub(crate) fn avec_les_choix(contenu: Option<&str>, hote: &str, port: u16, demarrage_windows: bool) -> String {
    let mut configuration = contenu
        .and_then(|texte| serde_json::from_str::<serde_json::Value>(texte).ok())
        .filter(serde_json::Value::is_object)
        .unwrap_or_else(|| serde_json::json!({}));
    configuration["serveur_bbass"] = serde_json::json!({ "hote": hote, "port": port });
    configuration["demarrage_windows"] = serde_json::Value::Bool(demarrage_windows);
    serde_json::to_string_pretty(&configuration).expect("JSON sérialisable")
}
