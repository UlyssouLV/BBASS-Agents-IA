"""Chiffre un secret Moduléo pour le .env de la VM centrale.

La clé d'API Moduléo et le SecurityCode sont chiffrés (Fernet) dans .env
(spec 1.5.0, ADR-0017) ; la clé maître est un fichier hors du dépôt, dont le
chemin est VM_CLE_MAITRE_FICHIER. Le script crée la clé maître si le fichier
n'existe pas (jamais il ne l'écrase : les secrets déjà chiffrés deviendraient
illisibles), demande le secret sans l'afficher, puis imprime la ligne à coller
dans .env.

Lancement, depuis vm-centrale/ :
    python scripts/chiffrer_secret.py MODULEO_API_KEY_CHIFFREE
    python scripts/chiffrer_secret.py MODULEO_SECURITY_CODE_CHIFFRE
Le chemin de la clé maître ne vient que de .env : pas d'option en ligne de
commande, pour qu'un argument ne puisse pas viser un autre fichier.
"""

import argparse
import os
from getpass import getpass
from pathlib import Path

from cryptography.fernet import Fernet

# Charge .env (load_dotenv) pour VM_CLE_MAITRE_FICHIER.
import vm_centrale.config  # noqa: F401
from vm_centrale.secrets_chiffres import lire_cle_maitre


def creer_cle_maitre_si_absente(chemin: Path) -> bool:
    # True si la clé vient d'être créée. Mode 0o600 sous Linux (ignoré sous
    # Windows) ; O_EXCL : ne remplace jamais une clé existante.
    if chemin.exists():
        return False
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descripteur, "wb") as fichier:
        fichier.write(Fernet.generate_key())
    return True


def chiffrer(secret: str, chemin_cle_maitre: Path) -> str:
    creer_cle_maitre_si_absente(chemin_cle_maitre)
    return Fernet(lire_cle_maitre(str(chemin_cle_maitre))).encrypt(secret.encode()).decode()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Chiffre un secret Moduléo pour .env.")
    parser.add_argument("variable", help="Nom de la variable .env, ex. MODULEO_API_KEY_CHIFFREE")
    arguments = parser.parse_args(argv)
    chemin = os.environ.get("VM_CLE_MAITRE_FICHIER")
    if not chemin:
        parser.error("VM_CLE_MAITRE_FICHIER absent de .env.")
    chemin_cle_maitre = Path(chemin)
    if creer_cle_maitre_si_absente(chemin_cle_maitre):
        print(f"Clé maître créée : {chemin_cle_maitre} (hors du dépôt, à sauvegarder à part).")
    secret = getpass(f"Valeur en clair de {arguments.variable} (non affichée) : ")
    print(f"{arguments.variable}={chiffrer(secret, chemin_cle_maitre)}")


if __name__ == "__main__":
    main()
