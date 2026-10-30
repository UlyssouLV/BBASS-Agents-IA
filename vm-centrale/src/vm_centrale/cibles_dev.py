import os
import shutil
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

# Cibles de dev (troisième passage de #206) : sur le poste de dev, un seul
# .env ne tenait pas à la fois le serveur Moduléo du cabinet et celui de
# test, et passer de l'un à l'autre écrasait les clés. `.env` garde le
# commun ; `.env.<cible>` (Moduléo, base, port, écriture) est lu par-dessus
# quand BBASS_CIBLE_DEV le nomme (lancer-vm, lancer-logiciel). Même partage
# que staging / prod sur la VM (ADR-0021) : test en 8001, cabinet en 8000.
# Sans BBASS_CIBLE_DEV (Docker, tests), rien n'est lu en plus.

URL_TEST = "https://mwa-kpw-api.kipaware.fr/api"
URL_CABINET = "https://mwa-bbass.kipaware.fr/api"

_CIBLES = {
    "test": {"MODULEO_URL": URL_TEST, "MODULEO_ECRITURE": "1", "VM_CENTRALE_PORT": "8001"},
    "cabinet": {"MODULEO_URL": URL_CABINET, "MODULEO_ECRITURE": "0", "VM_CENTRALE_PORT": "8000"},
}
_PAR_CIBLE = ("MODULEO_URL", "MODULEO_API_KEY_CHIFFREE", "MODULEO_SECURITY_CODE_CHIFFRE", "MODULEO_ECRITURE")
_BASE = "VM_CENTRALE_DATABASE_URL"
_BASE_PAR_DEFAUT = "postgresql+psycopg://vm_centrale:vm_centrale@localhost:5432/vm_centrale"
_SAUVEGARDE = ".env.avant-cibles"


def charger_cible_dev(dossier: Path) -> str | None:
    # Après load_dotenv() de config.py : la cible écrase le commun.
    cible = (os.environ.get("BBASS_CIBLE_DEV") or "").strip().lower()
    if not cible:
        return None
    if cible not in _CIBLES:
        raise RuntimeError(f"Cible de dev inconnue : « {cible} » (test ou cabinet).")
    fichier = dossier / f".env.{cible}"
    if not fichier.is_file():
        raise RuntimeError(
            f"{fichier} absent : lancer `python scripts/preparer_cible_dev.py {cible}` depuis vm-centrale/."
        )
    load_dotenv(fichier, override=True)
    return cible


def separer_env(dossier: Path) -> bool:
    # Une seule fois : le Moduléo du .env actuel va à sa cible (d'après son
    # URL), avec la base actuelle ; l'autre cible part sans clé, sur une base
    # à elle. L'ancien .env est gardé. False si déjà séparé.
    env = dossier / ".env"
    if any((dossier / f".env.{cible}").exists() for cible in _CIBLES):
        return False
    valeurs = {nom: valeur or "" for nom, valeur in dotenv_values(env).items()} if env.is_file() else {}
    actuelle = "cabinet" if valeurs.get("MODULEO_URL", URL_CABINET).rstrip("/") == URL_CABINET else "test"
    base = valeurs.get(_BASE) or _BASE_PAR_DEFAUT
    for cible, reglages in _CIBLES.items():
        lignes = {**reglages, "MODULEO_API_KEY_CHIFFREE": "", "MODULEO_SECURITY_CODE_CHIFFRE": ""}
        if cible == actuelle:
            lignes.update({nom: valeurs[nom] for nom in _PAR_CIBLE if valeurs.get(nom)})
            lignes["MODULEO_ECRITURE"] = reglages["MODULEO_ECRITURE"]
        lignes[_BASE] = base if cible == actuelle else f"{base.rsplit('/', 1)[0]}/vm_centrale_{cible}"
        _ecrire(dossier / f".env.{cible}", f"Cible de dev « {cible} » (cibles_dev.py), lue par-dessus .env.", lignes)
    if env.is_file():
        shutil.copyfile(env, dossier / _SAUVEGARDE)
        commun = {nom: valeur for nom, valeur in valeurs.items() if nom not in (*_PAR_CIBLE, _BASE, "VM_CENTRALE_PORT")}
        _ecrire(env, "Réglages communs aux cibles de dev ; Moduléo, base et port : .env.test, .env.cabinet.", commun)
    return True


def _ecrire(chemin: Path, entete: str, lignes: dict[str, str]) -> None:
    contenu = "".join(f"{nom}={valeur}\n" for nom, valeur in lignes.items())
    chemin.write_text(f"# {entete}\n{contenu}", encoding="utf-8")
