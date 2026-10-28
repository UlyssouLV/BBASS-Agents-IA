import hashlib
import subprocess
from pathlib import Path

import pytest

from vm_centrale.exploitation import main

# `mettre-a-jour <env>` et `restaurer <env> <fichier>` (spec 1.6.1,
# ADR-0021, #233), lancés sur l'hôte par `docker run … mettre-a-jour <env>`
# (aussi par bbass-vm-<env>.service au démarrage). L'Environnement est
# installé par `installer` sous une racine temporaire ; Docker, GHCR,
# Postgres et GET /sante sont simulés par FauxHote.

DEPOT_VM = "ghcr.io/ulyssoulv/bbass-vm-centrale"
DEPOT_SEARXNG = "ghcr.io/ulyssoulv/bbass-vm-searxng"
DEPLOIEMENT = Path(__file__).resolve().parents[1] / "deploiement"


def _id(image: str, version: str) -> str:
    # Au format de `docker image inspect` (sha256:<64 hex>).
    return "sha256:" + hashlib.sha256(f"{image}-{version}".encode()).hexdigest()


class FauxHote:
    """Docker de l'hôte (images locales, GHCR, stack Compose, Postgres) et
    GET /sante de la VM en service."""

    def __init__(self, etiquette: str) -> None:
        self.etiquette = etiquette
        self.registre: dict[str, str] = {}
        self.locales: dict[str, str] = {}
        self.fichiers: dict[str, dict[str, str]] = {}
        self.versions: dict[str, str] = {}
        self.saines: set[str] = set()
        self.internet = True
        # Paquet GHCR privé ou absent : GHCR répond `denied`.
        self.ghcr_refuse = False
        self.en_service: str | None = None
        self.base = "base initiale"
        self.commandes: list[list[str]] = []
        self.journal: list[str] = []

    def publier(self, version: str, *, saine: bool = True, taches: str | None = None) -> None:
        # Release vX.Y.Z, étiquette de l'Environnement posée dessus ; `taches`
        # remplace le taches-planifiees.conf livré dans l'image.
        vm, searxng = _id("vm", version), _id("searxng", version)
        self.registre[f"{DEPOT_VM}:{self.etiquette}"] = vm
        self.registre[f"{DEPOT_SEARXNG}:{self.etiquette}"] = searxng
        self.fichiers[vm] = {
            "/app/deploiement/compose.yml": f"# compose.yml de {version}\n",
            **{
                f"/app/deploiement/{nom}": (DEPLOIEMENT / nom).read_text(encoding="utf-8")
                for nom in ("bbass-vm.service", "taches-planifiees.conf", "bbass-tache.service", "bbass-tache.timer")
            },
        }
        if taches is not None:
            self.fichiers[vm]["/app/deploiement/taches-planifiees.conf"] = taches
        self.versions[vm] = version
        if saine:
            self.saines.add(vm)

    def sante(self, _url: str) -> str | None:
        if self.en_service in self.saines:
            return self.versions[self.en_service]
        return None

    def __call__(self, commande: list[str], *, entree=None, sortie=None) -> subprocess.CompletedProcess:
        self.commandes.append(commande)
        code, texte, erreur = 0, "", ""
        match commande:
            case ["docker", "pull", reference]:
                # Messages d'erreur tels que `docker pull` les donne.
                if not self.internet:
                    code, erreur = 1, "dial tcp: lookup ghcr.io: network is unreachable"
                elif self.ghcr_refuse:
                    code, erreur = 1, "Error response from daemon: error from registry: denied\ndenied"
                elif reference in self.registre:
                    self.locales[reference] = self.registre[reference]
                else:
                    code, erreur = 1, f"Error response from daemon: manifest for {reference} not found: manifest unknown"
            case ["docker", "image", "inspect", "--format", "{{.Id}}", reference]:
                if reference in self.locales:
                    texte = self.locales[reference] + "\n"
                else:
                    code = 1
            case ["docker", "tag", image, reference]:
                self.locales[reference] = image
            case ["docker", "run", "--rm", "--entrypoint", "cat", image, chemin]:
                texte = self.fichiers[image][chemin]
            case ["docker", "compose", "--project-directory", _, *reste]:
                if reste == ["up", "-d"]:
                    self.en_service = self.locales[f"{DEPOT_VM}:{self.etiquette}"]
                elif reste == ["stop", "vm-centrale"]:
                    self.en_service = None
                elif reste[:3] == ["exec", "-T", "postgres"] and "pg_dump" in reste[-1] and sortie:
                    sortie.write(self.base.encode())
                elif reste[:3] == ["exec", "-T", "postgres"] and "psql" in reste[-1] and entree:
                    self.base = entree.read().decode()
            case ["logger", "-t", _, message]:
                self.journal.append(message)
        return subprocess.CompletedProcess(commande, code, texte, erreur)

    def a_lance(self, *debut: str) -> bool:
        return any(commande[: len(debut)] == list(debut) for commande in self.commandes)


@pytest.fixture
def racine(monkeypatch, tmp_path) -> Path:
    monkeypatch.setenv("BBASS_RACINE_HOTE", str(tmp_path))
    return tmp_path


@pytest.fixture
def staging(racine, monkeypatch) -> FauxHote:
    # Environnement staging installé, v1.6.1 en service.
    monkeypatch.setattr("vm_centrale.installation.executer_sur_hote", lambda _commande: None)
    saisies = iter(["cle-mistral", "", ""])
    monkeypatch.setattr("vm_centrale.installation.getpass", lambda _invite="": next(saisies))
    main(["installer", "staging"])
    hote = FauxHote("staging")
    monkeypatch.setattr("vm_centrale.mise_a_jour.interroger_hote", hote)
    monkeypatch.setattr("vm_centrale.mise_a_jour.lire_sante", hote.sante)
    monkeypatch.setattr("vm_centrale.mise_a_jour.INTERVALLE_SANTE_SECONDES", 0)
    hote.publier("1.6.1")
    main(["mettre-a-jour", "staging"])
    hote.commandes.clear()
    hote.journal.clear()
    return hote


def _dossier(racine: Path) -> Path:
    return racine / "opt" / "bbass" / "staging"


def _sauvegardes(racine: Path) -> list[str]:
    return sorted(fichier.name for fichier in (_dossier(racine) / "sauvegardes").iterdir())


def test_version_inchangee_redemarre_sans_sauvegarde(racine, staging, capsys):
    main(["mettre-a-jour", "staging"])

    assert _sauvegardes(racine) == []
    assert not staging.a_lance("docker", "compose", "--project-directory", "/opt/bbass/staging", "exec")
    assert staging.en_service == _id("vm", "1.6.1")
    assert "1.6.1" in capsys.readouterr().out


def test_version_changee_sauvegarde_la_base_puis_demarre_la_nouvelle(racine, staging):
    staging.publier("1.6.2")

    main(["mettre-a-jour", "staging"])

    (sauvegarde,) = _sauvegardes(racine)
    assert (_dossier(racine) / "sauvegardes" / sauvegarde).read_text() == "base initiale"
    assert staging.en_service == _id("vm", "1.6.2")
    assert (_dossier(racine) / "compose.yml").read_text() == "# compose.yml de 1.6.2\n"


def test_cinq_sauvegardes_sont_gardees_la_plus_ancienne_est_supprimee(racine, staging):
    anciennes = [f"staging-2026010{jour}T000000Z.sql" for jour in range(1, 6)]
    for nom in anciennes:
        (_dossier(racine) / "sauvegardes" / nom).write_text("ancienne")
    staging.publier("1.6.2")

    main(["mettre-a-jour", "staging"])

    restantes = _sauvegardes(racine)
    assert len(restantes) == 5
    assert anciennes[0] not in restantes
    assert set(anciennes[1:]) < set(restantes)


def test_sante_ko_apres_mise_a_jour_remet_les_images_precedentes_et_le_dit(racine, staging, capsys):
    staging.publier("1.6.2", saine=False)

    with pytest.raises(SystemExit) as sortie:
        main(["mettre-a-jour", "staging"])

    assert sortie.value.code != 0
    assert staging.en_service == _id("vm", "1.6.1")
    assert staging.locales[f"{DEPOT_VM}:staging"] == _id("vm", "1.6.1")
    assert staging.locales[f"{DEPOT_SEARXNG}:staging"] == _id("searxng", "1.6.1")
    assert (_dossier(racine) / "compose.yml").read_text() == "# compose.yml de 1.6.1\n"
    message = capsys.readouterr().err
    assert "1.6.1" in message and "précédente" in message
    assert message.strip() in staging.journal


def test_apres_un_retour_arriere_la_version_remise_reste_en_service(racine, staging):
    staging.publier("1.6.2", saine=False)
    with pytest.raises(SystemExit):
        main(["mettre-a-jour", "staging"])
    staging.publier("1.6.3")

    main(["mettre-a-jour", "staging"])

    assert staging.en_service == _id("vm", "1.6.3")
    assert len(_sauvegardes(racine)) == 2


def test_sans_internet_demarre_les_images_presentes_et_le_journalise(racine, staging):
    staging.publier("1.6.2")
    staging.internet = False

    main(["mettre-a-jour", "staging"])

    assert staging.en_service == _id("vm", "1.6.1")
    assert _sauvegardes(racine) == []
    assert any("Internet" in message for message in staging.journal)
    assert not any("GHCR" in message for message in staging.journal)


def test_ghcr_refuse_le_dit_sans_parler_d_internet(racine, staging):
    # Paquet resté privé : l'admin doit chercher du côté de GHCR, pas du
    # réseau.
    staging.publier("1.6.2")
    staging.ghcr_refuse = True

    main(["mettre-a-jour", "staging"])

    assert staging.en_service == _id("vm", "1.6.1")
    refus = [message for message in staging.journal if "GHCR" in message]
    assert len(refus) == 2
    assert all("privé" in message and "Internet" not in message for message in refus)


@pytest.mark.parametrize("saine", [True, False])
def test_le_env_est_identique_avant_et_apres_une_mise_a_jour(racine, staging, saine):
    env = _dossier(racine) / ".env"
    avant = env.read_bytes()
    staging.publier("1.6.2", saine=saine)

    try:
        main(["mettre-a-jour", "staging"])
    except SystemExit:
        pass

    assert env.read_bytes() == avant


def test_images_en_service_illisibles_refuse_sans_rien_toucher(racine, staging, capsys):
    (_dossier(racine) / "images-en-service.json").write_text('{"vm-centrale": "--help", "searxng": "x"}')
    staging.publier("1.6.2")

    with pytest.raises(SystemExit) as sortie:
        main(["mettre-a-jour", "staging"])

    assert sortie.value.code != 0
    assert "images-en-service.json" in capsys.readouterr().err
    assert not staging.a_lance("docker", "tag")
    assert _sauvegardes(racine) == []


def _restaurer(monkeypatch, sauvegarde: str, confirmation: str = "restaurer") -> None:
    monkeypatch.setattr("builtins.input", lambda _invite="": confirmation)
    main(["restaurer", "staging", sauvegarde])


def test_restaurer_remet_la_base_dans_l_etat_de_la_sauvegarde(racine, staging, monkeypatch):
    staging.publier("1.6.2")
    main(["mettre-a-jour", "staging"])
    staging.base = "messages écrits après la mise à jour"

    _restaurer(monkeypatch, _sauvegardes(racine)[0])

    assert staging.base == "base initiale"
    assert staging.en_service == _id("vm", "1.6.2")


def test_restaurer_sans_confirmation_ne_touche_pas_a_la_base(racine, staging, monkeypatch):
    staging.publier("1.6.2")
    main(["mettre-a-jour", "staging"])
    staging.base = "messages écrits après la mise à jour"

    with pytest.raises(SystemExit) as sortie:
        _restaurer(monkeypatch, _sauvegardes(racine)[0], confirmation="non")

    assert sortie.value.code != 0
    assert staging.base == "messages écrits après la mise à jour"
    assert staging.en_service == _id("vm", "1.6.2")


def test_restaurer_refuse_une_sauvegarde_absente(racine, staging, monkeypatch):
    with pytest.raises(SystemExit) as sortie:
        _restaurer(monkeypatch, "staging-inexistante.sql")

    assert sortie.value.code != 0
    assert staging.commandes == []


def test_le_service_de_l_environnement_lance_la_mise_a_jour_au_demarrage(racine, staging):
    unite = (racine / "etc" / "systemd" / "system" / "bbass-vm-staging.service").read_text()

    (execution,) = [ligne for ligne in unite.splitlines() if ligne.startswith("ExecStart=")]
    assert "ghcr.io/ulyssoulv/bbass-vm-centrale:staging mettre-a-jour staging" in execution
    assert "--network host" in execution and "-v /:/hote" in execution


def _timers(racine: Path) -> list[str]:
    return sorted(fichier.name for fichier in (racine / "etc" / "systemd" / "system").glob("bbass-staging-*.timer"))


def test_une_ligne_ajoutee_au_conf_cree_son_timer_a_la_mise_a_jour(racine, staging):
    staging.publier("1.6.2", taches="purger-cache-pages hourly\nrelancer-quelque-chose *-*-* 03:00:00\n")

    main(["mettre-a-jour", "staging"])

    assert _timers(racine) == ["bbass-staging-purger-cache-pages.timer", "bbass-staging-relancer-quelque-chose.timer"]
    systemd = racine / "etc" / "systemd" / "system"
    assert "OnCalendar=*-*-* 03:00:00" in (systemd / "bbass-staging-relancer-quelque-chose.timer").read_text()
    assert "tache relancer-quelque-chose" in (systemd / "bbass-staging-relancer-quelque-chose.service").read_text()
    assert staging.a_lance("systemctl", "daemon-reload")
    assert staging.a_lance("systemctl", "enable", "--now", "bbass-staging-relancer-quelque-chose.timer")


def test_une_ligne_retiree_du_conf_retire_son_timer_a_la_mise_a_jour(racine, staging):
    assert _timers(racine) == ["bbass-staging-purger-cache-pages.timer"]
    staging.publier("1.6.2", taches="# plus aucune tâche\n")

    main(["mettre-a-jour", "staging"])

    systemd = racine / "etc" / "systemd" / "system"
    assert _timers(racine) == []
    assert not (systemd / "bbass-staging-purger-cache-pages.service").exists()
    assert staging.a_lance("systemctl", "disable", "--now", "bbass-staging-purger-cache-pages.timer")
    assert (systemd / "bbass-vm-staging.service").is_file()


def test_un_conf_invalide_dans_la_nouvelle_image_remet_la_version_precedente(racine, staging, capsys):
    staging.publier("1.6.2", taches="purger-cache-pages hourly\nExecStart=/bin/sh\n")

    with pytest.raises(SystemExit):
        main(["mettre-a-jour", "staging"])

    assert staging.en_service == _id("vm", "1.6.1")
    assert _timers(racine) == ["bbass-staging-purger-cache-pages.timer"]
    assert "taches-planifiees.conf" in capsys.readouterr().out


def test_chaque_tache_du_conf_livre_est_une_sous_commande_de_l_image():
    for ligne in (DEPLOIEMENT / "taches-planifiees.conf").read_text(encoding="utf-8").splitlines():
        if ligne.strip() and not ligne.startswith("#"):
            with pytest.raises(SystemExit) as aide:
                main(["tache", ligne.split()[0], "--help"])
            assert aide.value.code == 0
