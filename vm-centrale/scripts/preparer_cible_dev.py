"""Prepare une cible de dev (test ou cabinet) : python scripts/preparer_cible_dev.py <cible>

Appele par lancer-vm / lancer-logiciel avant le seed, depuis vm-centrale/,
sans BBASS_CIBLE_DEV (la cible n'existe peut-etre pas encore). La premiere
fois, separe le .env actuel en .env (commun), .env.test et .env.cabinet
(cibles_dev.separer_env, ancien .env garde en .env.avant-cibles). Puis cree
la base PostgreSQL de la cible si elle n'existe pas.
"""

import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from vm_centrale.cibles_dev import separer_env

DOSSIER = Path(__file__).resolve().parents[1]


def creer_base(url: str) -> None:
    # Meme serveur, base `postgres` pour la creer ; rien pour SQLite ni sans
    # URL (la VM garde sa base par defaut).
    if not url:
        return
    adresse = make_url(url)
    if not adresse.drivername.startswith("postgresql"):
        return
    connexion = psycopg.connect(
        host=adresse.host, port=adresse.port or 5432, user=adresse.username,
        password=adresse.password, dbname="postgres", autocommit=True,
    )
    with connexion:
        existe = connexion.execute("SELECT 1 FROM pg_database WHERE datname = %s", (adresse.database,)).fetchone()
        if existe is None:
            connexion.execute(f'CREATE DATABASE "{adresse.database}"')
            print(f"      Base {adresse.database} creee.")


def main() -> None:
    cible = (sys.argv[1] if len(sys.argv) > 1 else "test").strip().lower()
    if cible not in ("test", "cabinet"):
        sys.exit(f"[ERREUR] Cible de dev inconnue : {cible} (test ou cabinet).")
    if separer_env(DOSSIER):
        print("      .env separe en .env (commun), .env.test et .env.cabinet ; ancien .env garde en .env.avant-cibles.")
    valeurs = dotenv_values(DOSSIER / f".env.{cible}")
    creer_base(valeurs.get("VM_CENTRALE_DATABASE_URL") or "")
    if not valeurs.get("MODULEO_API_KEY_CHIFFREE"):
        print(
            f"      Cible {cible} sans cle Moduleo : `python scripts/chiffrer_secret.py MODULEO_API_KEY_CHIFFREE` "
            f"(et MODULEO_SECURITY_CODE_CHIFFRE), lignes a coller dans vm-centrale/.env.{cible}."
        )
    print(f"      Cible de dev : {cible} (port {valeurs.get('VM_CENTRALE_PORT')}, Moduleo {valeurs.get('MODULEO_URL')}).")


if __name__ == "__main__":
    main()
