"""Journaux du backend poste en mode paquet (ADR-0022).

Écrits dans `%LOCALAPPDATA%\\BBASS\\journaux\\` avec rotation : quelques Mo au
plus. Ils ne reprennent jamais un corps, un en-tête ni une chaîne de requête,
pour n'y laisser ni mot de passe ni jeton.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOM_DU_FICHIER = "poste-backend.log"
# 3 fichiers de 1 Mo au plus.
TAILLE_MAX = 1_000_000
ARCHIVES = 2

journal_des_requetes = logging.getLogger("poste.requetes")


def configurer_journaux(dossier: Path, taille_max: int = TAILLE_MAX, archives: int = ARCHIVES) -> logging.Handler:
    dossier.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        dossier / NOM_DU_FICHIER, maxBytes=taille_max, backupCount=archives, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    racine = logging.getLogger()
    racine.addHandler(handler)
    racine.setLevel(logging.INFO)
    # httpx journalise chaque URL appelée sur la VM au niveau INFO : bruit inutile.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return handler
