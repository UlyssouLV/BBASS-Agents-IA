import re
import unicodedata
from dataclasses import dataclass

# Énumérations Moduléo (#180) : le JSON donne un entier, les filtres de
# recherche attendent le nom de l'énumération, l'interface affiche un
# libellé. Correspondance relevée le 2026-10-08 sur le serveur du cabinet,
# en lecture seule (scripts/relever_enumerations_moduleo.py) : l'ordre ne
# suit ni l'interface ni le WADL (Acceptée = 7), et un nom inconnu en
# filtre est ignoré sans erreur, donc refusé ici avant la recherche.


@dataclass(frozen=True)
class Valeur:
    # `json` : l'entier du JSON ; `api` : le nom en filtre ; `affiche` : le
    # libellé de l'interface Moduléo, celui de la fiche ; `autres` : autres
    # façons de le dire, acceptées en filtre.
    json: int
    api: str
    affiche: str
    autres: tuple[str, ...] = ()


ETATS_AFFAIRE = (
    Valeur(4, "Creee", "Créée"),
    Valeur(8, "EnAttente", "En attente"),
    Valeur(7, "Acceptee", "Acceptée"),
    Valeur(1, "Production", "Production"),
    Valeur(9, "Suspendue", "Suspendue"),
    Valeur(5, "Terminee", "Prod. terminée", ("Production terminée",)),
    Valeur(2, "Cloturee", "Clôturée"),
    Valeur(6, "Annulee", "Annulée"),
)
# 2 : jamais rencontré au relevé, affiché en chiffre.
TYPES_CONTACT = (
    Valeur(1, "Personne", "Personne"),
    Valeur(3, "Societe", "Société"),
    Valeur(4, "Collectivite", "Collectivité"),
    Valeur(5, "GroupeContacts", "Groupe de contacts"),
)

# `Etat` d'un devis (#189) : pas encore relevé sur le serveur du cabinet
# (à l'essai réel, #178) ; 0, valeur par défaut, n'a pas de ligne, toute
# autre valeur est affichée en chiffre. Pas de filtre `etat` d'ici là :
# Moduléo ignorerait un nom inconnu.
ETATS_DEVIS: tuple[Valeur, ...] = ()


def libelle(valeurs: tuple[Valeur, ...], brute: object) -> str:
    # Entier du JSON (ou nom de l'énumération, forme du XML) → libellé ;
    # une valeur inconnue reste telle quelle, en chiffre.
    for valeur in valeurs:
        if brute in (valeur.json, valeur.api):
            return valeur.affiche
    return "" if brute is None else str(brute).strip()


def nom_api(valeurs: tuple[Valeur, ...], dit: str) -> str | None:
    # Libellé ou nom de l'énumération, tel que le modèle l'écrit (casse,
    # accents, ponctuation, accord) → nom en filtre ; None si inconnu.
    cle = _cle(dit)
    for valeur in valeurs:
        if cle in {_cle(nom) for nom in (valeur.api, valeur.affiche, *valeur.autres)}:
            return valeur.api
    return None


def libelles(valeurs: tuple[Valeur, ...]) -> str:
    return ", ".join(valeur.affiche for valeur in valeurs)


def _cle(texte: str) -> str:
    # « Prod. terminée » → « prodtermin » ; « Accepté » et « Acceptée » →
    # « accept ».
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", texte.casefold()) if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]", "", sans_accents).rstrip("e")
