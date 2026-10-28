//! Adresse du Serveur BBASS dans `%LOCALAPPDATA%\BBASS\configuration.json`, partagé
//! avec le backend (`poste/config.py`) : même format, même adresse prod par défaut.
//!
//! ```json
//! { "serveur_bbass": { "hote": "10.0.0.5", "port": 8000 } }
//! ```

/// Adresse prod par défaut (spec 1.6.2, point 10), comme `ADRESSE_PROD` du backend.
/// Vide tant qu'elle n'est pas connue : sans fichier de configuration, le Serveur BBASS
/// est injoignable et le poste ouvre la Configuration.
const ADRESSE_PROD: &str = "";

fn adresse(contenu: &str) -> Option<String> {
    let configuration: serde_json::Value = serde_json::from_str(contenu).ok()?;
    let serveur = configuration.get("serveur_bbass")?;
    let hote = serveur.get("hote")?.as_str()?.trim();
    let port = match serveur.get("port")? {
        serde_json::Value::String(port) => port.trim().parse::<u16>().ok()?,
        port => u16::try_from(port.as_u64()?).ok()?,
    };
    (!hote.is_empty()).then(|| format!("http://{hote}:{port}"))
}

/// `contenu` : texte du fichier de configuration, `None` s'il n'existe pas.
/// `None` sans adresse connue (ni fichier ni adresse prod).
pub fn url_de_la_sante(contenu: Option<&str>) -> Option<String> {
    let adresse = contenu.and_then(adresse).or_else(|| (!ADRESSE_PROD.is_empty()).then(|| ADRESSE_PROD.to_string()))?;
    Some(format!("{adresse}/sante"))
}
