import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import NoReturn

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from vm_centrale.models import Compte, ComptePole
from vm_centrale.secrets_chiffres import lire_cle_maitre
from vm_centrale.security import generer_mot_de_passe_aleatoire, hash_password

# Gestes d'installation d'un Environnement (spec 1.6.1, ADR-0021, #232),
# appelés par les sous-commandes de vm_centrale.exploitation. Lancés par
#   docker run --rm -it --user root --privileged --pid=host -v /:/hote \
#     ghcr.io/ulyssoulv/bbass-vm-centrale:<tag> installer <env>
# Les fichiers sont écrits sous la racine de l'hôte montée (/hote) ; Docker
# et systemd sont ceux de l'hôte, atteints par nsenter (executer_sur_hote).


@dataclass(frozen=True)
class Environnement:
    port_hote: int
    moduleo_url: str


# Staging lit le serveur de test Kipaware, prod le serveur du cabinet.
ENVIRONNEMENTS = {
    "staging": Environnement(port_hote=8001, moduleo_url="https://mwa-kpw-api.kipaware.fr/api"),
    "prod": Environnement(port_hote=8000, moduleo_url="https://mwa-bbass.kipaware.fr/api"),
}
# Saisis en clair, écrits chiffrés (Fernet, ADR-0017/0018). Seule la clé
# Mistral est obligatoire : sans elle la VM refuse de démarrer ; Moduléo
# vide, la VM démarre sans ses outils.
SECRETS = {
    "MISTRAL_API_KEY_CHIFFREE": ("Clé API Mistral", True),
    "MODULEO_API_KEY_CHIFFREE": ("Clé API Moduléo (vide : sans Moduléo)", False),
    "MODULEO_SECURITY_CODE_CHIFFRE": ("SecurityCode Moduléo (vide : sans Moduléo)", False),
}
# Utilisateur de l'image (Dockerfile) : lit la clé maître et écrit les
# pièces jointes.
_UID_IMAGE = "10001"
_POSTGRES_USER_DB = "vm_centrale"


def _racine_hote() -> Path:
    return Path(os.environ.get("BBASS_RACINE_HOTE", "/hote"))


def dossier_deploiement() -> Path:
    # Posé par le Dockerfile dans l'image ; hors image, celui du dépôt.
    return Path(os.environ.get("VM_CENTRALE_DEPLOIEMENT_DIR") or Path(__file__).resolve().parents[2] / "deploiement")


# Dans les espaces de noms du PID 1 de l'hôte (--pid=host, --privileged) :
# le docker et le systemctl de l'hôte, chemins de l'hôte.
NSENTER_HOTE = ["nsenter", "--target", "1", "--mount", "--uts", "--ipc", "--net", "--pid", "--"]


def executer_sur_hote(commande: list[str]) -> None:
    # Entrée et sortie restent celles du terminal (creer-admin est
    # interactif).
    try:
        subprocess.run([*NSENTER_HOTE, *commande], check=True)
    except subprocess.CalledProcessError:
        refuser(f"Échec sur l'hôte : {' '.join(commande)}")


@dataclass(frozen=True)
class Chemins:
    # `hote` : chemin vu par l'hôte (écrit dans .env et l'unité systemd) ;
    # `ici` : le même vu depuis ce conteneur (sous la racine montée).
    environnement: str

    @property
    def dossier_hote(self) -> str:
        return f"/opt/bbass/{self.environnement}"

    @property
    def cle_maitre_hote(self) -> str:
        return f"/etc/bbass/{self.environnement}/cle-maitre"

    @property
    def service(self) -> str:
        return f"bbass-vm-{self.environnement}.service"

    @property
    def unite_hote(self) -> str:
        return f"/etc/systemd/system/{self.service}"

    def ici(self, chemin_hote: str) -> Path:
        return _racine_hote() / chemin_hote.lstrip("/")

    @property
    def dossier(self) -> Path:
        return self.ici(self.dossier_hote)

    @property
    def env(self) -> Path:
        return self.dossier / ".env"

    @property
    def cle_maitre(self) -> Path:
        return self.ici(self.cle_maitre_hote)


def refuser(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


def _demander(invite: str) -> str:
    # Redemandé tant que vide : aucun de ces champs n'est facultatif.
    while not (valeur := input(invite).strip()):
        pass
    return valeur


def _demander_secret(variable: str) -> str:
    libelle, obligatoire = SECRETS[variable]
    while True:
        valeur = getpass(f"{libelle} (non affichée) : ").strip()
        if valeur or not obligatoire:
            return valeur


def _chiffrer(valeur: str, cle_maitre: bytes) -> str:
    # Vide reste vide : la VM le lit comme « non configuré ».
    return Fernet(cle_maitre).encrypt(valeur.encode()).decode() if valeur else ""


def _ecrire_prive(chemin: Path, contenu: str, mode: int) -> None:
    # Créé avec son mode : jamais lisible par d'autres, même un instant.
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
        fichier.write(contenu)


def installer(environnement: str) -> None:
    chemins = Chemins(environnement)
    config = ENVIRONNEMENTS[environnement]
    if chemins.dossier.exists() or chemins.cle_maitre.parent.exists():
        refuser(
            f"L'Environnement {environnement} est déjà installé ({chemins.dossier_hote}, "
            f"{chemins.cle_maitre_hote.rsplit('/', 1)[0]}) : rien n'est modifié. Après une installation "
            "interrompue, supprimer ces deux dossiers puis relancer."
        )
    # Saisies d'abord : interrompre ici ne laisse rien sur le disque.
    saisis = {variable: _demander_secret(variable) for variable in SECRETS}

    cle_maitre = Fernet.generate_key()
    mot_de_passe_postgres = secrets.token_hex(24)
    vm_admin_key = secrets.token_urlsafe(32)
    for dossier in ("donnees/pieces_jointes", "donnees/postgres", "sauvegardes"):
        (chemins.dossier / dossier).mkdir(parents=True)
    chemins.cle_maitre.parent.mkdir(parents=True, mode=0o700)
    _ecrire_prive(chemins.cle_maitre, cle_maitre.decode(), 0o400)
    lignes = {
        "BBASS_ENVIRONNEMENT": environnement,
        "BBASS_ETIQUETTE": environnement,
        "VM_PORT_HOTE": str(config.port_hote),
        "VM_CLE_MAITRE_FICHIER": chemins.cle_maitre_hote,
        "POSTGRES_USER": _POSTGRES_USER_DB,
        "POSTGRES_PASSWORD": mot_de_passe_postgres,
        "POSTGRES_DB": _POSTGRES_USER_DB,
        "VM_ADMIN_KEY": vm_admin_key,
        "MODULEO_URL": config.moduleo_url,
        **{variable: _chiffrer(valeur, cle_maitre) for variable, valeur in saisis.items()},
    }
    _ecrire_prive(chemins.env, "".join(f"{nom}={valeur}\n" for nom, valeur in lignes.items()), 0o600)
    deploiement = dossier_deploiement()
    shutil.copyfile(deploiement / "compose.yml", chemins.dossier / "compose.yml")
    unite = (deploiement / "bbass-vm.service").read_text(encoding="utf-8")
    unite_ici = chemins.ici(chemins.unite_hote)
    unite_ici.parent.mkdir(parents=True, exist_ok=True)
    unite_ici.write_text(unite.replace("{environnement}", environnement), encoding="utf-8")

    executer_sur_hote(["chown", _UID_IMAGE, chemins.cle_maitre_hote, f"{chemins.dossier_hote}/donnees/pieces_jointes"])
    executer_sur_hote(
        ["docker", "compose", "--project-directory", chemins.dossier_hote, "run", "--rm", "vm-centrale", "creer-admin"]
    )
    executer_sur_hote(["systemctl", "daemon-reload"])
    executer_sur_hote(["systemctl", "enable", "--now", chemins.service])

    print()
    print(f"Environnement {environnement} installé et démarré (port {config.port_hote}).")
    print("Valeurs générées, affichées une seule fois : à ranger dans le gestionnaire de mots de passe du cabinet.")
    print(f"  Mot de passe Postgres : {mot_de_passe_postgres}")
    print(f"  Clé maître ({chemins.cle_maitre_hote}) : {cle_maitre.decode()}")
    print(f"  VM_ADMIN_KEY : {vm_admin_key}")


def configurer_secret(environnement: str, variable: str) -> None:
    chemins = Chemins(environnement)
    if not chemins.env.is_file():
        refuser(f"L'Environnement {environnement} n'est pas installé ({chemins.dossier_hote}/.env absent).")
    valeur = _chiffrer(_demander_secret(variable), lire_cle_maitre(str(chemins.cle_maitre)))
    lignes = chemins.env.read_text(encoding="utf-8").splitlines()
    autres = [ligne for ligne in lignes if not ligne.startswith(f"{variable}=")]
    # Réécrit en place : le fichier garde son mode (root seul).
    chemins.env.write_text("".join(f"{ligne}\n" for ligne in [*autres, f"{variable}={valeur}"]), encoding="utf-8")
    executer_sur_hote(["systemctl", "restart", chemins.service])
    print(f"{variable} remplacée ; {chemins.service} redémarré.")


def creer_admin(db: Session) -> None:
    # Premier compte administrateur de la production (remplace
    # seed_compte_test.py, réservé au dev). Mot de passe généré et affiché
    # une fois, comme à la création d'un compte par l'API (spec V1.1).
    if db.query(Compte).filter(Compte.est_admin.is_(True)).first() is not None:
        refuser("Un compte administrateur existe déjà : rien n'est créé.")
    identifiant = _demander("Identifiant de l'administrateur : ")
    prenom = _demander("Prénom : ")
    nom = _demander("Nom : ")
    agence = _demander("Agence : ")
    mot_de_passe = generer_mot_de_passe_aleatoire()
    db.add(
        Compte(
            identifiant=identifiant,
            mot_de_passe_hash=hash_password(mot_de_passe),
            prenom=prenom,
            nom=nom,
            agence=agence,
            est_admin=True,
            doit_changer_mot_de_passe=True,
            poles=[ComptePole(pole="Administration")],
        )
    )
    db.commit()
    print()
    print(f"Compte administrateur créé : {identifiant}")
    print(f"Mot de passe : {mot_de_passe}")
    print("Affiché une seule fois ; à changer à la première connexion.")
