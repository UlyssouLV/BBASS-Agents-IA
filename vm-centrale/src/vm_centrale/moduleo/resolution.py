from collections.abc import Iterable
from dataclasses import dataclass

from vm_centrale.moduleo.client import LecteurModuleo, ModuleoIntrouvable

# Ids Moduléo → noms (spec 1.5.0) : le modèle ne voit jamais un id. Chaque
# fonction reçoit les ids de tous les éléments d'un appel d'outil, les
# dédoublonne et ne lit chacun qu'une fois. Un id absent de Moduléo n'a
# simplement pas de nom.


@dataclass(frozen=True)
class Utilisateur:
    nom: str
    tel_fixe: str
    tel_portable: str
    email: str


@dataclass(frozen=True)
class Noms:
    utilisateurs: dict[int, Utilisateur]
    contacts: dict[int, str]
    communes: dict[int, str]


def _uniques(ids: Iterable[int | None]) -> list[int]:
    # 0 : valeur par défaut d'un id non renseigné côté Moduléo.
    return sorted({i for i in ids if i})


def _texte(valeur: object) -> str:
    return str(valeur or "").strip()


def resoudre_utilisateurs(lecteur: LecteurModuleo, ids: Iterable[int | None]) -> dict[int, Utilisateur]:
    # Pas de route `multi` pour les utilisateurs : une lecture par id.
    utilisateurs = {}
    for id_utilisateur in _uniques(ids):
        try:
            fiche = lecteur.lire("moduleo/utilisateur/{idUtilisateur}", {"idUtilisateur": id_utilisateur})
        except ModuleoIntrouvable:
            continue
        nom = " ".join(part for part in (_texte(fiche.get("Prenom")), _texte(fiche.get("Nom"))) if part)
        utilisateurs[id_utilisateur] = Utilisateur(
            nom=nom,
            tel_fixe=_texte(fiche.get("TelFixe")),
            tel_portable=_texte(fiche.get("TelPortable")),
            email=_texte(fiche.get("Email")),
        )
    return utilisateurs


def resoudre_contacts(lecteur: LecteurModuleo, ids: Iterable[int | None]) -> dict[int, str]:
    uniques = _uniques(ids)
    if not uniques:
        return {}
    contacts = lecteur.lire("cogeo/contact/multi?ids={ids}", {"ids": ",".join(map(str, uniques))})
    return {contact["IdContact"]: _texte(contact.get("Nom")) for contact in contacts}


def resoudre_communes(lecteur: LecteurModuleo, ids: Iterable[int | None]) -> dict[int, str]:
    # « Castries (34160) ».
    uniques = _uniques(ids)
    if not uniques:
        return {}
    communes = lecteur.lire("moduleo/commune/multi?ids={ids}", {"ids": ",".join(map(str, uniques))})
    resultat = {}
    for commune in communes:
        nom, code_postal = _texte(commune.get("Nom")), _texte(commune.get("CodePostal"))
        resultat[commune["IdCommune"]] = f"{nom} ({code_postal})" if code_postal else nom
    return resultat
