from collections.abc import Callable, Iterable
from typing import Any

from vm_centrale.moduleo.client import ErreurModuleo, LecteurModuleo, RequeteInterdite
from vm_centrale.moduleo.droits import DroitManquant
from vm_centrale.moduleo.resolution import (
    activites,
    resoudre_codes_activite,
    resoudre_communes,
    resoudre_contacts,
    resoudre_equipements,
    resoudre_participants,
    resoudre_utilisateurs,
)

# Lignes de la Carte de confirmation (spec 1.5.2, #204) : chaque champ du
# corps et chaque paramètre de la route, en noms. Un id est nommé par les
# résolveurs existants d'après le nom de son champ ; un id qu'aucun ne sait
# nommer (champ inconnu, élément introuvable, lecture refusée ou en panne)
# s'affiche brut, avec « non résolu ».

NON_RESOLU = "non résolu"

# Champs que la carte ne montre pas : Moduléo les remplit lui-même.
_IGNORES = {"ProprietesModifiees"}


def _affaires(lecteur: LecteurModuleo, ids: Iterable[int]) -> dict[int, str]:
    uniques = sorted(set(ids))
    if not uniques:
        return {}
    lues = lecteur.lire("cogeo/affaire/multi?ids={ids}", {"ids": ",".join(map(str, uniques))})
    return {a["IdAffaire"]: f"affaire {a.get('Numero') or a['IdAffaire']}" for a in lues}


def _utilisateurs(lecteur: LecteurModuleo, ids: Iterable[int]) -> dict[int, str]:
    return {i: u.nom for i, u in resoudre_utilisateurs(lecteur, ids).items() if u.nom}


def _activites(lecteur: LecteurModuleo, ids: Iterable[int]) -> dict[int, str]:
    return activites(lecteur) if any(True for _ in ids) else {}


Resolveur = Callable[[LecteurModuleo, Iterable[int]], dict[int, str]]

# Nom du champ (casse indifférente) → résolveur de son id ou de ses ids.
_RESOLVEURS: dict[str, Resolveur] = {
    **dict.fromkeys(("idaffaire", "idsaffaires"), _affaires),
    **dict.fromkeys(
        ("idcontact", "idclient", "idrepresentant", "idscontacts", "idcontactlie", "iddestinataire"),
        resoudre_contacts,
    ),
    **dict.fromkeys(
        (
            "idutilisateur",
            "idresponsable",
            "idcollaborateur",
            "idredacteur",
            "idgeometreexpert",
            "idchefequipe",
            "idacteurencharge",
            "idsdestinataires",
            "idsutilisateurs",
        ),
        _utilisateurs,
    ),
    "idcommune": resoudre_communes,
    "idcodeactivite": resoudre_codes_activite,
    "idactivite": _activites,
    "participants": resoudre_participants,
    "equipements": resoudre_equipements,
}


def _est_un_id(champ: str) -> bool:
    cle = champ.casefold()
    return cle.startswith("id") or cle in _RESOLVEURS


def _libelle(champ: str) -> str:
    # « IdAffaire » → « Affaire », « IdsContacts » → « Contacts »,
    # « idAffaire » (paramètre) → « Affaire ».
    for prefixe in ("Ids", "Id", "ids", "id"):
        reste = champ.removeprefix(prefixe)
        if reste != champ and reste[:1].isupper():
            return reste
    return champ[:1].upper() + champ[1:]


def _ids(valeur: Any) -> list[int]:
    valeurs = valeur if isinstance(valeur, list) else str(valeur).split(",") if isinstance(valeur, str) else [valeur]
    ids = []
    for element in valeurs:
        try:
            ids.append(int(str(element).strip()))
        except ValueError:
            continue
    return ids


def _a_montrer(champ: str, valeur: Any) -> bool:
    # Un champ vide n'a pas de ligne ; un id à 0 est un id non renseigné.
    if champ in _IGNORES or valeur is None or valeur == "" or valeur == []:
        return False
    return not (_est_un_id(champ) and _ids(valeur) == [0])


def _texte(valeur: Any) -> str:
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, list):
        return ", ".join(_texte(element) for element in valeur)
    return str(valeur)


def _aplatir(valeurs: dict[str, Any], prefixe: str = "") -> list[tuple[str, Any]]:
    # Un objet imbriqué : « Adresse › Rue ».
    champs = []
    for champ, valeur in valeurs.items():
        if isinstance(valeur, dict):
            champs += _aplatir(valeur, f"{prefixe}{_libelle(champ)} › ")
        elif _a_montrer(champ, valeur):
            champs.append((f"{prefixe}{champ}", valeur))
    return champs


def _resoudre(lecteur: LecteurModuleo, champs: list[tuple[str, Any]]) -> dict[str, dict[int, str]]:
    # Par résolveur, tous les ids de la carte en une fois. Une lecture
    # refusée ou en panne laisse ses ids non résolus.
    a_resoudre: dict[str, list[int]] = {}
    for champ, valeur in champs:
        cle = champ.rsplit(" › ", 1)[-1].casefold()
        if cle in _RESOLVEURS:
            a_resoudre.setdefault(cle, []).extend(_ids(valeur))
    noms: dict[str, dict[int, str]] = {}
    for cle, ids in a_resoudre.items():
        try:
            noms[cle] = _RESOLVEURS[cle](lecteur, ids)
        except (DroitManquant, ErreurModuleo, RequeteInterdite, KeyError, TypeError, ValueError):
            noms[cle] = {}
    return noms


def lignes_en_noms(lecteur: LecteurModuleo, parametres: dict[str, Any], corps: Any) -> list[dict[str, str]]:
    # Paramètres de la route d'abord, puis le corps, dans l'ordre reçu.
    champs = _aplatir(parametres)
    if isinstance(corps, dict):
        champs += _aplatir(corps)
    elif isinstance(corps, list):
        champs += [(f"Élément {n}", element) for n, element in enumerate(corps, start=1)]
    noms = _resoudre(lecteur, champs)
    lignes = []
    for champ, valeur in champs:
        dernier = champ.rsplit(" › ", 1)
        libelle = " › ".join([*dernier[:-1], _libelle(dernier[-1])])
        if _est_un_id(dernier[-1]):
            connus = noms.get(dernier[-1].casefold(), {})
            ids = _ids(valeur) or [valeur]
            texte = ", ".join(connus[i] if i in connus else f"{i} ({NON_RESOLU})" for i in ids)
        else:
            texte = _texte(valeur)
        lignes.append({"champ": libelle, "valeur": texte})
    return lignes
