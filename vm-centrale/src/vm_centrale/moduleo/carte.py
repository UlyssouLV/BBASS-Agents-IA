from collections.abc import Callable, Iterable
from typing import Any

from vm_centrale.moduleo.client import ErreurModuleo, LecteurModuleo, RequeteInterdite
from vm_centrale.moduleo.droits import DroitManquant, DroitsModuleo
from vm_centrale.moduleo.fiches import NomsPlanning, NomsTempsPasses, fiche_tache, fiche_temps_passe
from vm_centrale.moduleo.ids import retirer_ids_moduleo
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
#
# PUT (#205) : les seuls champs du corps qui changent l'élément relu,
# ancien (`avant`) → nouveau, un champ vide valant « (vide) », sous la
# fiche de l'élément visé (#253). DELETE : la fiche de lecture de l'élément
# quand elle existe (temps passé, tâche du planning), sinon ses champs en
# noms. `identites` : les champs qui portent l'id de l'élément lui-même,
# jamais montrés.

NON_RESOLU = "non résolu"
VIDE = "(vide)"

# Champs que la carte ne montre pas : Moduléo les remplit lui-même.
_IGNORES = {"ProprietesModifiees"}
# Erreurs d'un résolveur : l'id reste non résolu.
_ILLISIBLE = (DroitManquant, ErreurModuleo, RequeteInterdite, KeyError, TypeError, ValueError)


def _multi(lecteur: LecteurModuleo, route: str, ids: Iterable[int]) -> list[dict]:
    uniques = sorted(set(ids))
    return lecteur.lire(route, {"ids": ",".join(map(str, uniques))}) if uniques else []


def _affaires(lecteur: LecteurModuleo, ids: Iterable[int]) -> dict[int, str]:
    lues = _multi(lecteur, "cogeo/affaire/multi?ids={ids}", ids)
    return {a["IdAffaire"]: f"affaire {a.get('Numero') or a['IdAffaire']}" for a in lues}


def _devis(lecteur: LecteurModuleo, ids: Iterable[int]) -> dict[int, str]:
    lus = _multi(lecteur, "cogeo/devis/multi?ids={ids}", ids)
    return {d["IdDevis"]: f"devis {d.get('Numero') or d['IdDevis']}" for d in lus}


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
    "iddevis": _devis,
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


def _vide(champ: str, valeur: Any) -> bool:
    # Un id à 0 est un id non renseigné.
    return valeur is None or valeur == "" or valeur == [] or (_est_un_id(champ) and _ids(valeur) == [0])


def _texte(valeur: Any) -> str:
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, list):
        return ", ".join(_texte(element) for element in valeur)
    return str(valeur)


def _aplatir(valeurs: dict[str, Any], prefixe: str = "", vides: bool = False) -> list[tuple[str, Any]]:
    # Un objet imbriqué : « Adresse › Rue ». Un champ vide n'a pas de ligne,
    # sauf pour comparer (`vides`).
    champs = []
    for champ, valeur in valeurs.items():
        if isinstance(valeur, dict):
            champs += _aplatir(valeur, f"{prefixe}{_libelle(champ)} › ", vides)
        elif champ not in _IGNORES and (vides or not _vide(champ, valeur)):
            champs.append((f"{prefixe}{champ}", valeur))
    return champs


def _feuille(champ: str) -> str:
    # « Adresse › IdCommune » → « IdCommune ».
    return champ.rsplit(" › ", 1)[-1]


def _resoudre(lecteur: LecteurModuleo, champs: list[tuple[str, Any]]) -> dict[str, dict[int, str]]:
    # Par résolveur, tous les ids de la carte en une fois. Une lecture
    # refusée ou en panne laisse ses ids non résolus.
    a_resoudre: dict[str, list[int]] = {}
    for champ, valeur in champs:
        cle = _feuille(champ).casefold()
        if cle in _RESOLVEURS:
            a_resoudre.setdefault(cle, []).extend(_ids(valeur))
    noms: dict[str, dict[int, str]] = {}
    for cle, ids in a_resoudre.items():
        try:
            noms[cle] = _RESOLVEURS[cle](lecteur, ids)
        except _ILLISIBLE:
            noms[cle] = {}
    return noms


def _libelle_complet(champ: str) -> str:
    dernier = champ.rsplit(" › ", 1)
    return " › ".join([*dernier[:-1], _libelle(dernier[-1])])


def _en_noms(champ: str, valeur: Any, noms: dict[str, dict[int, str]]) -> str:
    feuille = _feuille(champ)
    if _vide(feuille, valeur):
        return VIDE
    if _est_un_id(feuille):
        connus = noms.get(feuille.casefold(), {})
        ids = _ids(valeur) or [valeur]
        return ", ".join(connus[i] if i in connus else f"{i} ({NON_RESOLU})" for i in ids)
    return _texte(valeur)


def _lignes(lecteur: LecteurModuleo, champs: list[tuple[str, Any]]) -> list[dict[str, str]]:
    noms = _resoudre(lecteur, champs)
    return [{"champ": _libelle_complet(champ), "valeur": _en_noms(champ, valeur, noms)} for champ, valeur in champs]


def lignes_en_noms(lecteur: LecteurModuleo, parametres: dict[str, Any], corps: Any) -> list[dict[str, str]]:
    # Paramètres de la route d'abord, puis le corps, dans l'ordre reçu.
    champs = _aplatir(parametres)
    if isinstance(corps, dict):
        champs += _aplatir(corps)
    elif isinstance(corps, list):
        champs += [(f"Élément {n}", element) for n, element in enumerate(corps, start=1)]
    return _lignes(lecteur, champs)


def _normal(champ: str, valeur: Any) -> Any:
    # Ce que compare la différence : vide, nombre, texte sans espaces autour.
    if _vide(champ, valeur):
        return None
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, (int, float)):
        return float(valeur)
    if isinstance(valeur, list):
        return [_normal("", element) for element in valeur]
    return str(valeur).strip()


def _changements(
    existant: dict[str, Any], corps: dict[str, Any], identites: set[str]
) -> list[tuple[str, str, Any, Any]]:
    # (clé du corps, champ aplati, avant, valeur) de chaque champ du corps,
    # dans son ordre, dont la valeur change l'élément relu.
    avant = dict(_aplatir(existant, vides=True))
    return [
        (cle, champ, avant.get(champ), valeur)
        for cle in corps
        for champ, valeur in _aplatir({cle: corps[cle]}, vides=True)
        if _feuille(champ).casefold() not in identites
        and _normal(_feuille(champ), avant.get(champ)) != _normal(_feuille(champ), valeur)
    ]


def champs_modifies(existant: dict[str, Any], corps: dict[str, Any], identites: set[str]) -> list[str]:
    # Clés du corps que la carte annonce : `ProprietesModifiees` d'un PUT
    # (#251).
    return list(dict.fromkeys(cle for cle, *_ in _changements(existant, corps, identites)))


def differences_en_noms(
    lecteur: LecteurModuleo, existant: dict[str, Any], corps: dict[str, Any], identites: set[str]
) -> list[dict[str, str]]:
    # Champs du corps, dans son ordre, dont la valeur change l'élément relu.
    changes = [(champ, ancien, nouveau) for _, champ, ancien, nouveau in _changements(existant, corps, identites)]
    noms = _resoudre(lecteur, [(champ, v) for champ, ancien, nouveau in changes for v in (ancien, nouveau)])
    return [
        {
            "champ": _libelle_complet(champ),
            "avant": _en_noms(champ, ancien, noms),
            "valeur": _en_noms(champ, nouveau, noms),
        }
        for champ, ancien, nouveau in changes
    ]


def _lisible(resoudre: Callable[[], dict]) -> dict:
    # Un nom illisible (droit, panne) laisse sa ligne de la fiche vide.
    try:
        return resoudre()
    except _ILLISIBLE:
        return {}


def _numeros_affaires(lecteur: LecteurModuleo, id_affaire: Any) -> dict[int, str]:
    lues = _multi(lecteur, "cogeo/affaire/multi?ids={ids}", [id_affaire] if id_affaire else [])
    return {a["IdAffaire"]: str(a.get("Numero") or "") for a in lues}


def _fiche_temps_passe(lecteur: LecteurModuleo, temps: dict, droits: DroitsModuleo) -> str:
    noms = NomsTempsPasses(
        utilisateurs=_lisible(lambda: resoudre_utilisateurs(lecteur, [temps.get("IdUtilisateur")])),
        affaires=_lisible(lambda: _numeros_affaires(lecteur, temps.get("IdAffaire"))),
        codes_activite=_lisible(lambda: resoudre_codes_activite(lecteur, [temps.get("IdCodeActivite")])),
    )
    return fiche_temps_passe(temps, noms, droits).texte


def _fiche_tache(lecteur: LecteurModuleo, tache: dict, droits: DroitsModuleo) -> str:
    noms = NomsPlanning(
        participants=_lisible(lambda: resoudre_participants(lecteur, tache.get("Participants") or [])),
        activites=_lisible(lambda: activites(lecteur)) if tache.get("IdActivite") else {},
        equipements=_lisible(lambda: resoudre_equipements(lecteur, tache.get("Equipements") or [])),
        affaires=_lisible(lambda: _numeros_affaires(lecteur, tache.get("IdAffaire"))),
    )
    return fiche_tache(tache, noms).texte


# Route de relecture → fiche de lecture de l'élément (moduleo/fiches.py).
_FICHES: dict[str, Callable[[LecteurModuleo, dict, DroitsModuleo], str]] = {
    "cogeo/tempspasse/multi?ids={ids}": _fiche_temps_passe,
    "planning/tacheplanning/multi?ids={ids}": _fiche_tache,
}


def element_en_noms(
    lecteur: LecteurModuleo, route_lue: str, element: dict[str, Any], droits: DroitsModuleo, identites: set[str]
) -> tuple[str | None, list[dict[str, str]]]:
    # (fiche, lignes) de l'élément entier : sa fiche de lecture sans l'id
    # Moduléo, sinon ses champs en noms.
    if route_lue in _FICHES:
        return retirer_ids_moduleo(_FICHES[route_lue](lecteur, element, droits)), []
    champs = [(champ, valeur) for champ, valeur in _aplatir(element) if _feuille(champ).casefold() not in identites]
    return None, _lignes(lecteur, champs)


def fiche_en_noms(
    lecteur: LecteurModuleo, route_lue: str, element: dict[str, Any], droits: DroitsModuleo, identites: set[str]
) -> str:
    # L'élément visé par un PUT (#253), en texte : sa fiche de lecture, sinon
    # une ligne « Champ : valeur » par champ en noms.
    fiche, lignes = element_en_noms(lecteur, route_lue, element, droits, identites)
    return fiche if fiche is not None else "\n".join(f"{ligne['champ']} : {ligne['valeur']}" for ligne in lignes)
