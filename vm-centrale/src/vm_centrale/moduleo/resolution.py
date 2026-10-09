import unicodedata
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


# Noms → ids (#175) : les filtres du modèle sont des noms ; un nom qui ne
# désigne rien, ou plusieurs personnes / dossiers, n'est jamais ignoré.

# Candidats nommés au plus, pour un nom ambigu.
_CANDIDATS_MAX = 10
_ROUTE_UTILISATEURS = "moduleo/utilisateur?nom={nom}&prenom={prenom}&actifSeulement={actifSeulement}"


class NomNonResolu(Exception):
    # Le message va tel quel au modèle ; aucune recherche n'est lancée sans
    # le filtre demandé.
    pass


def chercher_utilisateur(lecteur: LecteurModuleo, nom: str) -> int:
    # « Martin », « Sophie », « Jean Martin », « Martin Jean », « Le Gall » :
    # premier essai qui trouve quelqu'un.
    ids: list[int] = []
    for parametres in _essais_utilisateur(nom):
        ids = _uniques(lecteur.lire(_ROUTE_UTILISATEURS, parametres))
        if ids:
            break
    if not ids:
        raise NomNonResolu(f"Aucun utilisateur Moduléo ne correspond à « {nom} » : recherche non lancée.")
    if len(ids) > 1:
        noms = sorted(u.nom for u in resoudre_utilisateurs(lecteur, ids[:_CANDIDATS_MAX]).values())
        raise NomNonResolu(_ambigu("utilisateurs", nom, noms, len(ids)))
    return ids[0]


def chercher_sites(lecteur: LecteurModuleo, nom: str) -> str:
    return _ids_par_nom(lecteur, "moduleo/site?nom={nom}&actifSeulement={actifSeulement}", nom, "Aucun site")


def chercher_services(lecteur: LecteurModuleo, nom: str) -> str:
    return _ids_par_nom(lecteur, "moduleo/service?nom={nom}&actifSeulement={actifSeulement}", nom, "Aucun service")


def chercher_dossier_production(lecteur: LecteurModuleo, nom: str) -> int:
    # La recherche d'affaires ne prend qu'un dossier de production.
    ids = _uniques(lecteur.lire("fileo/dossierproduction?texteRecherche={texteRecherche}", {"texteRecherche": nom}))
    if not ids:
        raise NomNonResolu(f"Aucun dossier de production Moduléo ne correspond à « {nom} » : recherche non lancée.")
    if len(ids) > 1:
        noms = sorted(
            nom_dossier
            for i in ids[:_CANDIDATS_MAX]
            if (nom_dossier := _nom_dossier_production(lecteur, i)) is not None
        )
        raise NomNonResolu(_ambigu("dossiers de production", nom, noms, len(ids)))
    return ids[0]


def _nom_dossier_production(lecteur: LecteurModuleo, id_dossier: int) -> str | None:
    # Un candidat supprimé entre la recherche et sa lecture n'a pas de nom.
    try:
        fiche = lecteur.lire("fileo/dossierproduction/{idDossierProduction}", {"idDossierProduction": id_dossier})
    except ModuleoIntrouvable:
        return None
    return _texte(fiche.get("Nom"))


def chercher_qualifications(lecteur: LecteurModuleo, noms: list[str]) -> str:
    # Contacts (#176) : un id par nom, séparés par une virgule. Le libellé
    # exact l'emporte (« Notaire » plutôt que « Clerc de notaire ») ; sinon
    # le seul libellé qui contient le nom.
    toutes = {q["IdQualification"]: _texte(q.get("Libelle")) for q in lecteur.lire("cogeo/qualification/all")}
    ids = []
    for nom in noms:
        exactes = [i for i, libelle in toutes.items() if libelle.casefold() == nom.casefold()]
        proches = exactes or [i for i, libelle in toutes.items() if nom.casefold() in libelle.casefold()]
        if not proches:
            raise NomNonResolu(f"Aucune qualification Moduléo ne correspond à « {nom} » : recherche non lancée.")
        if len(proches) > 1:
            libelles = sorted(toutes[i] for i in proches[:_CANDIDATS_MAX])
            raise NomNonResolu(_ambigu("qualifications", nom, libelles, len(proches)))
        ids.append(proches[0])
    return ",".join(map(str, dict.fromkeys(ids)))


def resoudre_codes_activite(lecteur: LecteurModuleo, ids: Iterable[int | None]) -> dict[int, str]:
    # Temps passés (#191) : pas de route `multi`, une lecture par code.
    codes = {}
    for id_code in _uniques(ids):
        try:
            codes[id_code] = _nom_code_activite(lecteur.lire(_ROUTE_CODE_ACTIVITE, {"idCodeActivite": id_code}))
        except ModuleoIntrouvable:
            continue
    return codes


def chercher_code_activite(lecteur: LecteurModuleo, nom: str) -> int:
    # Codes lus dans Moduléo (#191) : un code créé dans Moduléo est reconnu
    # sans changer le code. Nom ou code exact (casse indifférente), sinon le
    # seul qui contient le nom.
    codes = {
        id_code: lecteur.lire(_ROUTE_CODE_ACTIVITE, {"idCodeActivite": id_code})
        for id_code in _uniques(lecteur.lire("cogeo/codeactivite"))
    }
    cherche = _cle(nom)
    exacts = [i for i, c in codes.items() if cherche in (_cle(c.get("Nom")), _cle(c.get("Code")))]
    proches = exacts or [i for i, c in codes.items() if cherche in f"{_cle(c.get('Nom'))} {_cle(c.get('Code'))}"]
    if not proches:
        raise NomNonResolu(f"Aucun code activité Moduléo ne correspond à « {nom} » : recherche non lancée.")
    if len(proches) > 1:
        noms = sorted(_nom_code_activite(codes[i]) for i in proches[:_CANDIDATS_MAX])
        raise NomNonResolu(_ambigu("codes activité", nom, noms, len(proches)))
    return proches[0]


_ROUTE_CODE_ACTIVITE = "cogeo/codeactivite/{idCodeActivite}"


def _cle(valeur: object) -> str:
    # Casse et accents indifférents : « releve » trouve « Relevé ».
    texte = unicodedata.normalize("NFD", _texte(valeur).casefold())
    return "".join(c for c in texte if not unicodedata.combining(c))


def _nom_code_activite(code: dict) -> str:
    return _texte(code.get("Nom")) or _texte(code.get("Code"))


def _essais_utilisateur(nom: str) -> list[dict[str, str]]:
    mots = nom.split()
    if len(mots) == 1:
        return [{"nom": nom}, {"prenom": nom}]
    return [
        {"prenom": mots[0], "nom": " ".join(mots[1:])},
        {"nom": " ".join(mots[:-1]), "prenom": mots[-1]},
        {"nom": nom},
    ]


def _ids_par_nom(lecteur: LecteurModuleo, route: str, nom: str, aucun: str) -> str:
    # Site et service sont des filtres à plusieurs ids : tous ceux qui
    # portent ce nom, séparés par une virgule.
    ids = _uniques(lecteur.lire(route, {"nom": nom}))
    if not ids:
        raise NomNonResolu(f"{aucun} Moduléo ne correspond à « {nom} » : recherche non lancée.")
    return ",".join(map(str, ids))


def _ambigu(genre: str, nom: str, noms: list[str], total: int) -> str:
    autres = f" et {total - len(noms)} autres" if total > len(noms) else ""
    return (
        f"Plusieurs {genre} Moduléo correspondent à « {nom} » : {', '.join(noms)}{autres}. "
        "Demande lequel, recherche non lancée."
    )
