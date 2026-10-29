use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener};
use std::thread;
use std::time::{Duration, Instant};

use bbass_lanceur_coeur::attente::attendre_reponse;

fn servir(listener: TcpListener, reponse: &'static str) {
    thread::spawn(move || {
        for flux in listener.incoming() {
            let mut flux = flux.unwrap();
            let mut tampon = [0u8; 1024];
            let _ = flux.read(&mut tampon);
            let _ = flux.write_all(reponse.as_bytes());
        }
    });
}

#[test]
fn le_backend_qui_repond_200_est_pret() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let adresse = listener.local_addr().unwrap();
    servir(listener, "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok");

    assert!(attendre_reponse(adresse, Duration::from_secs(5)));
}

#[test]
fn un_backend_en_erreur_n_est_pas_pret() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let adresse = listener.local_addr().unwrap();
    servir(listener, "HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");

    assert!(!attendre_reponse(adresse, Duration::from_millis(600)));
}

#[test]
fn sans_backend_l_attente_s_arrete_au_bout_du_delai() {
    // Port libéré aussitôt réservé : rien n'y écoute.
    let adresse: SocketAddr = TcpListener::bind("127.0.0.1:0").unwrap().local_addr().unwrap();
    let debut = Instant::now();

    assert!(!attendre_reponse(adresse, Duration::from_millis(600)));
    assert!(debut.elapsed() < Duration::from_secs(5));
}

#[test]
fn le_backend_qui_demarre_pendant_l_attente_est_pret() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let adresse = listener.local_addr().unwrap();
    drop(listener);
    thread::spawn(move || {
        thread::sleep(Duration::from_millis(500));
        servir(TcpListener::bind(adresse).unwrap(), "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
    });

    assert!(attendre_reponse(adresse, Duration::from_secs(5)));
}
