//! Attente de la réponse locale du backend poste (sidecar) avant d'ouvrir l'application.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::thread;
use std::time::{Duration, Instant};

const INTERVALLE: Duration = Duration::from_millis(250);

/// Vrai dès que `GET /` sur `adresse` répond 200 ; faux si `delai` s'écoule avant.
pub fn attendre_reponse(adresse: SocketAddr, delai: Duration) -> bool {
    let fin = Instant::now() + delai;
    loop {
        if repond_200(adresse) {
            return true;
        }
        if Instant::now() >= fin {
            return false;
        }
        thread::sleep(INTERVALLE);
    }
}

fn repond_200(adresse: SocketAddr) -> bool {
    let Ok(mut flux) = TcpStream::connect_timeout(&adresse, Duration::from_secs(1)) else {
        return false;
    };
    let _ = flux.set_read_timeout(Some(Duration::from_secs(2)));
    let requete = format!("GET / HTTP/1.1\r\nHost: {adresse}\r\nConnection: close\r\n\r\n");
    if flux.write_all(requete.as_bytes()).is_err() {
        return false;
    }
    let mut debut = [0u8; 12];
    flux.read_exact(&mut debut).is_ok() && debut.starts_with(b"HTTP/1.") && &debut[8..] == b" 200"
}
