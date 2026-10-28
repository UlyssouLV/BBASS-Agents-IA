//! Adresse du Serveur BBASS dans `%LOCALAPPDATA%\BBASS\configuration.json`, partagé
//! avec le backend (`poste/config.py`) : même format, même adresse par défaut.
//!
//! ```json
//! { "serveur_bbass": { "hote": "10.0.0.5", "port": 8000 } }
//! ```

const ADRESSE_PAR_DEFAUT: &str = "http://localhost:8000";

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
pub fn url_de_la_sante(contenu: Option<&str>) -> String {
    let adresse = contenu.and_then(adresse).unwrap_or_else(|| ADRESSE_PAR_DEFAUT.to_string());
    format!("{adresse}/sante")
}
