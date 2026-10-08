from datetime import date

from vm_centrale.moduleo.resolution import Noms, Utilisateur

# Fiche Moduléo (spec 1.5.0) : le texte dense d'un élément lu dans Moduléo,
# en noms, jamais la réponse brute ni un id. C'est ce que reçoit le modèle et
# ce qu'enregistre `lectures_outils`. Un champ vide n'a pas de ligne.

_DATES_AFFAIRE = (
    ("DateCreation", "Date de création"),
    ("DateOuverture", "Date d'ouverture"),
    ("DateLivraison", "Date de livraison"),
    ("DateCloture", "Date de clôture"),
)


def reference_affaire(affaire: dict) -> str:
    # Citée par la ligne « Sources : » : « Moduléo, affaire 2024-123 ».
    return f"affaire {_texte(affaire.get('Numero'))}"


def fiche_affaire(affaire: dict, intervenants: list[dict], noms: Noms) -> str:
    lignes = [f"Affaire {_texte(affaire.get('Numero'))}"]
    _ajouter(lignes, "Objet", _texte(affaire.get("Objet")))
    _ajouter(lignes, "État", _texte(affaire.get("Etat")))
    for champ, libelle in _DATES_AFFAIRE:
        _ajouter(lignes, libelle, _date(affaire.get(champ)))
    _ajouter(lignes, "Adresse", _texte(affaire.get("Adresse")))
    _ajouter(lignes, "Commune", noms.communes.get(_id(affaire.get("IdCommune")), ""))
    _ajouter(lignes, "Client", _contact(noms, affaire.get("IdClient"), affaire.get("QualiteClient")))
    _ajouter(
        lignes, "Représentant", _contact(noms, affaire.get("IdRepresentant"), affaire.get("QualiteRepresentant"))
    )
    _ajouter(lignes, "Responsable", _utilisateur(noms.utilisateurs.get(_id(affaire.get("IdResponsable")))))
    _ajouter(lignes, "Chargé d'affaire", _utilisateur(noms.utilisateurs.get(_id(affaire.get("IdActeurEnCharge")))))
    lignes_intervenants = [ligne for intervenant in intervenants if (ligne := _intervenant(noms, intervenant))]
    if lignes_intervenants:
        lignes.append("Intervenants :")
        lignes.extend(f"- {ligne}" for ligne in lignes_intervenants)
    return "\n".join(lignes)


def _id(valeur: object) -> int:
    # 0 : jamais un id Moduléo, donc jamais un nom.
    return valeur if isinstance(valeur, int) else 0


def _texte(valeur: object) -> str:
    return "" if valeur is None else str(valeur).strip()


def _ajouter(lignes: list[str], libelle: str, valeur: str) -> None:
    if valeur:
        lignes.append(f"{libelle} : {valeur}")


def _date(valeur: object) -> str:
    # « 2024-03-11T00:00:00+01:00 » → « 11/03/2024 ». L'an 1 est la date
    # par défaut d'un champ vide côté Moduléo (.NET) : pas de ligne.
    texte = _texte(valeur)
    try:
        jour = date.fromisoformat(texte[:10])
    except ValueError:
        return texte
    return "" if jour.year == 1 else jour.strftime("%d/%m/%Y")


def _contact(noms: Noms, id_contact: object, qualite: object) -> str:
    nom = noms.contacts.get(_id(id_contact), "")
    qualite = _texte(qualite)
    return f"{nom} ({qualite})" if nom and qualite else nom


def _utilisateur(utilisateur: Utilisateur | None) -> str:
    if utilisateur is None or not utilisateur.nom:
        return ""
    coordonnees = [
        coordonnee
        for coordonnee in (
            f"tél. {utilisateur.tel_fixe}" if utilisateur.tel_fixe else "",
            f"portable {utilisateur.tel_portable}" if utilisateur.tel_portable else "",
            f"email {utilisateur.email}" if utilisateur.email else "",
        )
        if coordonnee
    ]
    return f"{utilisateur.nom} ({', '.join(coordonnees)})" if coordonnees else utilisateur.nom


def _intervenant(noms: Noms, intervenant: dict) -> str:
    # « Office notarial Rives (Notaire), représenté par Claire Rives (Clerc) ».
    ligne = _contact(noms, intervenant.get("IdContact"), intervenant.get("QualiteIntervenant"))
    if not ligne:
        return ""
    representant = _contact(noms, intervenant.get("IdRepresentant"), intervenant.get("QualiteRepresentant"))
    return f"{ligne}, représenté par {representant}" if representant else ligne
