import re
from collections.abc import Callable

from vm_centrale.installation import Chemins

# Timers des tâches planifiées d'un Environnement (spec 1.6.1, ADR-0021,
# #234), tirés de taches-planifiees.conf par `installer` et `mettre-a-jour` :
# un couple bbass-<env>-<nom>.timer / .service par ligne, retiré quand la
# ligne disparaît. Les modèles et le .conf viennent de l'image déployée.

FICHIERS = ("taches-planifiees.conf", "bbass-tache.service", "bbass-tache.timer")
_DOSSIER_UNITES = "/etc/systemd/system"
# Seuls ces caractères entrent dans les unités systemd : aucune directive
# glissée par une ligne du .conf.
_NOM = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_CALENDRIER = re.compile(r"[A-Za-z0-9*:/,.~ -]+")


class ConfInvalide(ValueError):
    pass


def lire_conf(contenu: str) -> dict[str, str]:
    # `<nom> <OnCalendar>` par ligne ; vides et commentaires (#) ignorés.
    taches: dict[str, str] = {}
    for ligne in contenu.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        nom, _, calendrier = ligne.partition(" ")
        calendrier = calendrier.strip()
        if not _NOM.fullmatch(nom) or not _CALENDRIER.fullmatch(calendrier) or nom in taches:
            raise ConfInvalide(f"taches-planifiees.conf : ligne invalide « {ligne} ».")
        taches[nom] = calendrier
    return taches


def planifier_taches(chemins: Chemins, lire: Callable[[str], str], executer: Callable[[list[str]], object]) -> None:
    # `lire` donne un fichier de FICHIERS (deploiement/ de l'image),
    # `executer` passe une commande à l'hôte.
    taches = lire_conf(lire("taches-planifiees.conf"))
    modeles = {extension: lire(f"bbass-tache.{extension}") for extension in ("service", "timer")}
    environnement = chemins.environnement
    dossier = chemins.ici(_DOSSIER_UNITES)
    dossier.mkdir(parents=True, exist_ok=True)
    prefixe = f"bbass-{environnement}-"
    modifie = False
    for nom, calendrier in taches.items():
        for extension, modele in modeles.items():
            fichier = dossier / f"{prefixe}{nom}.{extension}"
            contenu = (
                modele.replace("{environnement}", environnement).replace("{nom}", nom).replace("{calendrier}", calendrier)
            )
            if not fichier.is_file() or fichier.read_text(encoding="utf-8") != contenu:
                fichier.write_text(contenu, encoding="utf-8")
                modifie = True
    for timer in sorted(dossier.glob(f"{prefixe}*.timer")):
        if timer.stem.removeprefix(prefixe) not in taches:
            executer(["systemctl", "disable", "--now", timer.name])
            timer.unlink()
            timer.with_suffix(".service").unlink(missing_ok=True)
            modifie = True
    if modifie:
        executer(["systemctl", "daemon-reload"])
    for nom in taches:
        executer(["systemctl", "enable", "--now", f"{prefixe}{nom}.timer"])
