import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, NoReturn

import httpx
from dotenv import dotenv_values

from vm_centrale.installation import ENVIRONNEMENTS, NSENTER_HOTE, Chemins, refuser
from vm_centrale.taches_planifiees import FICHIERS, ConfInvalide, lire_conf, planifier_taches

# Mise à jour d'un Environnement (spec 1.6.1, ADR-0021, #233), appelée par
# la sous-commande `mettre-a-jour <env>` de vm_centrale.exploitation et par
# bbass-vm-<env>.service au démarrage de la VM, lancées par
#   docker run --rm --user root --privileged --pid=host --network host \
#     -v /:/hote ghcr.io/ulyssoulv/bbass-vm-centrale:<env> mettre-a-jour <env>
# Même racine montée et même nsenter qu'`installer` ; --network host pour
# lire GET /sante sur le port publié.

IMAGES = {
    "vm-centrale": "ghcr.io/ulyssoulv/bbass-vm-centrale",
    "searxng": "ghcr.io/ulyssoulv/bbass-vm-searxng",
}
# GET /sante lu toutes les 2 s, 3 min au plus (démarrage de Postgres et
# création des tables compris).
INTERVALLE_SANTE_SECONDES = 2.0
_TENTATIVES_SANTE = 90
# Par Environnement, sous /opt/bbass/<env>/sauvegardes/ : une par
# changement de version.
SAUVEGARDES_GARDEES = 5
# Identifiant d'image tel que `docker image inspect` le donne.
_ID_IMAGE = re.compile(r"sha256:([0-9a-f]{64})")


def interroger_hote(
    commande: list[str], *, entree: IO[bytes] | None = None, sortie: IO[bytes] | None = None
) -> subprocess.CompletedProcess:
    # Contrairement à executer_sur_hote, un échec est une réponse : la mise
    # à jour en décide (pas d'Internet, retour arrière…).
    return subprocess.run(
        [*NSENTER_HOTE, *commande],
        stdin=entree,
        stdout=sortie or subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def lire_sante(url: str) -> str | None:
    # Version servie si GET /sante répond 200, sinon None.
    try:
        reponse = httpx.get(url, timeout=3)
        return reponse.json().get("version") if reponse.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def _id_image_valide(valeur: object) -> str | None:
    # Reconstruit depuis l'entier lu : rien du fichier ne passe tel quel en
    # argument d'une commande de l'hôte (Sonar pythonsecurity:S6350).
    trouve = _ID_IMAGE.fullmatch(valeur) if isinstance(valeur, str) else None
    return f"sha256:{int(trouve[1], 16):064x}" if trouve else None


class _MiseAJour:
    def __init__(self, environnement: str) -> None:
        # Nom repris d'ENVIRONNEMENTS, jamais de l'argument : seul un nom
        # connu entre dans les chemins et les commandes de l'hôte.
        connu = next((nom for nom in ENVIRONNEMENTS if nom == environnement), None)
        if connu is None:
            refuser(f"Environnement inconnu : {environnement}.")
        self.chemins = Chemins(connu)
        if not self.chemins.env.is_file():
            refuser(f"L'Environnement {environnement} n'est pas installé ({self.chemins.dossier_hote}/.env absent).")
        # Lu, jamais réécrit : le .env reste celui de l'installation.
        env = dotenv_values(self.chemins.env)
        self.references = {nom: f"{depot}:{env['BBASS_ETIQUETTE']}" for nom, depot in IMAGES.items()}
        self.url_sante = f"http://localhost:{int(env['VM_PORT_HOTE'])}/sante"
        self.compose = ["docker", "compose", "--project-directory", self.chemins.dossier_hote]

    @property
    def _fichier_en_service(self):
        return self.chemins.dossier / "images-en-service.json"

    def dire(self, message: str) -> None:
        # Sortie de commande, et journal de l'hôte (journalctl -t
        # bbass-vm-<env>) même lancé à la main.
        print(message, flush=True)
        self._journaliser(message)

    def echouer(self, message: str) -> NoReturn:
        self._journaliser(message)
        refuser(message)

    def _journaliser(self, message: str) -> None:
        interroger_hote(["logger", "-t", f"bbass-vm-{self.chemins.environnement}", message])

    def executer(self) -> None:
        for reference in self.references.values():
            telechargement = interroger_hote(["docker", "pull", reference])
            if telechargement.returncode != 0:
                # Au démarrage de la VM, le réseau peut manquer : la VM
                # tourne quand même, sur ce qu'elle a.
                self.dire(
                    f"Téléchargement de {reference} impossible (pas d'Internet ?) : démarrage avec les images "
                    f"présentes. {telechargement.stderr.strip()}".strip()
                )
        identifiants = {nom: self._id_image(reference) for nom, reference in self.references.items()}
        presentes = {nom: image for nom, image in identifiants.items() if image is not None}
        if len(presentes) != len(IMAGES):
            self.echouer("Images absentes de l'hôte et téléchargement impossible : rien à démarrer.")
        en_service = self._lire_en_service()
        # Premier démarrage après `installer` : rien à protéger ni à remettre.
        if en_service is None or presentes == en_service:
            version = self._deployer(presentes)
            if version is None:
                self.echouer(f"La VM ne répond pas sur {self.url_sante}.")
        else:
            if not self._sauvegarder():
                self._revenir(en_service, "Sauvegarde de la base impossible : mise à jour annulée.")
            version = self._deployer(presentes)
            if version is None:
                self._revenir(en_service, f"La nouvelle version ne répond pas sur {self.url_sante}.")
        self._noter_en_service(presentes)
        self.dire(f"{self.chemins.environnement} : version {version} en service.")

    def _revenir(self, precedentes: dict[str, str], raison: str) -> NoReturn:
        # Les étiquettes locales repointent sur les images d'avant : le
        # compose.yml (BBASS_ETIQUETTE) les redémarre sans toucher au .env.
        # La base n'est jamais restaurée ici (`restaurer`, à la main).
        for nom, image in precedentes.items():
            if interroger_hote(["docker", "tag", image, self.references[nom]]).returncode != 0:
                self.echouer(f"{raison} Images précédentes absentes de l'hôte : aucun retour arrière possible.")
        version = self._deployer(precedentes)
        if version is None:
            self.echouer(f"{raison} La version précédente ne répond pas non plus sur {self.url_sante}.")
        self.echouer(f"{raison} Version précédente {version} remise en service.")

    def _id_image(self, reference: str) -> str | None:
        resultat = interroger_hote(["docker", "image", "inspect", "--format", "{{.Id}}", reference])
        return resultat.stdout.strip() if resultat.returncode == 0 else None

    def _lire_en_service(self) -> dict[str, str] | None:
        if not self._fichier_en_service.is_file():
            return None
        lues = json.loads(self._fichier_en_service.read_text(encoding="utf-8"))
        images = {nom: _id_image_valide(lues.get(nom)) for nom in IMAGES}
        if None in images.values():
            self.echouer(f"{self.chemins.dossier_hote}/images-en-service.json illisible : rien n'est modifié.")
        return images

    def _noter_en_service(self, images: dict[str, str]) -> None:
        self._fichier_en_service.write_text(json.dumps(images), encoding="utf-8")

    def _sauvegarder(self) -> bool:
        # Base de la version en service, avant que la nouvelle n'y touche.
        # SQL avec DROP : `restaurer` le rejoue tel quel.
        if interroger_hote([*self.compose, "up", "-d", "--wait", "postgres"]).returncode != 0:
            return False
        dossier = self.chemins.dossier / "sauvegardes"
        prefixe = f"{self.chemins.environnement}-"
        fichier = dossier / f"{prefixe}{datetime.now(UTC):%Y%m%dT%H%M%S.%fZ}.sql"
        with os.fdopen(os.open(fichier, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as sortie:
            resultat = interroger_hote(
                [*self.compose, "exec", "-T", "postgres", "sh", "-c",
                 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists'],
                sortie=sortie,
            )
        if resultat.returncode != 0:
            fichier.unlink()
            self.dire(f"pg_dump a échoué : {resultat.stderr.strip()}")
            return False
        for ancienne in sorted(dossier.glob(f"{prefixe}*.sql"))[:-SAUVEGARDES_GARDEES]:
            ancienne.unlink()
        self.dire(f"Base sauvegardée : {self.chemins.dossier_hote}/sauvegardes/{fichier.name}")
        return True

    def _deployer(self, images: dict[str, str]) -> str | None:
        # Fichiers de déploiement de l'image démarrée (jamais le .env), puis
        # la stack ; la version servie, ou None sans réponse saine.
        if not self._rafraichir_fichiers(images["vm-centrale"]):
            return None
        demarrage = interroger_hote([*self.compose, "up", "-d"])
        if demarrage.returncode != 0:
            self.dire(f"docker compose up a échoué : {demarrage.stderr.strip()}")
            return None
        return self._attendre_sante()

    def _rafraichir_fichiers(self, image: str) -> bool:
        environnement = self.chemins.environnement
        lus = {source: self._lire_dans_image(image, source) for source in ("compose.yml", "bbass-vm.service", *FICHIERS)}
        if None in lus.values():
            return False
        # Le .conf d'abord : invalide, rien n'est écrit (retour arrière).
        try:
            lire_conf(lus["taches-planifiees.conf"])
        except ConfInvalide as erreur:
            self.dire(f"{erreur} (image {image})")
            return False
        for source, destination in (
            ("compose.yml", f"{self.chemins.dossier_hote}/compose.yml"),
            ("bbass-vm.service", self.chemins.unite_hote),
        ):
            fichier = self.chemins.ici(destination)
            contenu = lus[source].replace("{environnement}", environnement)
            if not fichier.is_file() or fichier.read_text(encoding="utf-8") != contenu:
                fichier.write_text(contenu, encoding="utf-8")
                if destination == self.chemins.unite_hote:
                    interroger_hote(["systemctl", "daemon-reload"])
        planifier_taches(self.chemins, lus.__getitem__, interroger_hote)
        return True

    def _lire_dans_image(self, image: str, source: str) -> str | None:
        lu = interroger_hote(["docker", "run", "--rm", "--entrypoint", "cat", image, f"/app/deploiement/{source}"])
        if lu.returncode != 0:
            self.dire(f"{source} illisible dans l'image {image} : {lu.stderr.strip()}")
            return None
        return lu.stdout

    def _attendre_sante(self) -> str | None:
        for _ in range(_TENTATIVES_SANTE):
            if (version := lire_sante(self.url_sante)) is not None:
                return version
            time.sleep(INTERVALLE_SANTE_SECONDES)
        return None

    def restaurer(self, nom_fichier: str) -> None:
        # Jamais automatique : écrase ce qui a été écrit depuis la sauvegarde.
        sauvegarde = self.chemins.dossier / "sauvegardes" / Path(nom_fichier).name
        if not sauvegarde.is_file():
            refuser(f"Sauvegarde introuvable : {self.chemins.dossier_hote}/sauvegardes/{sauvegarde.name}.")
        confirmation = input(
            f"La base {self.chemins.environnement} sera remplacée par {sauvegarde.name} ; ce qui a été écrit "
            "depuis sera perdu. Taper « restaurer » pour confirmer : "
        )
        if confirmation.strip() != "restaurer":
            refuser("Restauration annulée : la base n'a pas été modifiée.")
        # VM arrêtée : personne n'écrit pendant que la sauvegarde est rejouée.
        interroger_hote([*self.compose, "stop", "vm-centrale"])
        if interroger_hote([*self.compose, "up", "-d", "--wait", "postgres"]).returncode != 0:
            self.echouer("Postgres ne démarre pas : la base n'a pas été modifiée.")
        with sauvegarde.open("rb") as entree:
            resultat = interroger_hote(
                [*self.compose, "exec", "-T", "postgres", "sh", "-c",
                 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" --single-transaction -v ON_ERROR_STOP=1'],
                entree=entree,
            )
        if resultat.returncode != 0:
            interroger_hote([*self.compose, "up", "-d"])
            self.echouer(f"Restauration échouée, base inchangée (transaction annulée) : {resultat.stderr.strip()}")
        interroger_hote([*self.compose, "up", "-d"])
        version = self._attendre_sante()
        if version is None:
            self.echouer(f"Base restaurée depuis {sauvegarde.name}, mais la VM ne répond pas sur {self.url_sante}.")
        self.dire(f"Base {self.chemins.environnement} restaurée depuis {sauvegarde.name} ; version {version} en service.")


def mettre_a_jour(environnement: str) -> None:
    _MiseAJour(environnement).executer()


def restaurer(environnement: str, fichier: str) -> None:
    _MiseAJour(environnement).restaurer(fichier)
