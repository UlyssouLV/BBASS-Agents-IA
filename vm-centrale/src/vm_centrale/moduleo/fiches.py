from dataclasses import dataclass
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


# TypeContact : entier dans le JSON, nom de l'énumération dans le XML du
# WADL (Personne = 1 ; ordre des autres supposé, à confirmer à l'essai
# réel, #178). NonDefini ou 0 : pas de ligne.
_TYPES_CONTACT = {
    1: "Personne",
    2: "Société",
    3: "Collectivité",
    4: "Groupe de contacts",
    "Personne": "Personne",
    "Societe": "Société",
    "Collectivite": "Collectivité",
    "GroupeContacts": "Groupe de contacts",
}
_TYPES_SANS_LIGNE = (None, 0, "NonDefini", "")
# Numéros d'affaires listés au plus par rôle ; au-delà, « et N autres ».
_AFFAIRES_MAX = 20


@dataclass(frozen=True)
class DetailsContact:
    # Ce que les lectures par contact rapportent : fiches de téléphone,
    # d'email et d'adresse telles que Moduléo les renvoie, numéros des
    # affaires dont le contact est client ou intervenant.
    telephones: list[dict]
    emails: list[dict]
    adresses: list[dict]
    affaires_client: list[str]
    affaires_intervenant: list[str]


def reference_contact(contact: dict) -> str:
    # « Moduléo, contact Étude Dupont ».
    return f"contact {_texte(contact.get('Nom'))}"


def fiche_contact(contact: dict, details: DetailsContact, communes: dict[int, str]) -> str:
    lignes = [f"Contact {_texte(contact.get('Nom'))}"]
    type_contact = contact.get("TypeContact")
    if type_contact not in _TYPES_SANS_LIGNE:
        _ajouter(lignes, "Type", _TYPES_CONTACT.get(type_contact, _texte(type_contact)))
    _ajouter_liste(
        lignes, "Téléphones", [_avec_lieu(_texte(t.get("Numero")), t.get("Lieu")) for t in details.telephones]
    )
    _ajouter_liste(lignes, "Emails", [_avec_lieu(_texte(e.get("Adresse")), e.get("Lieu")) for e in details.emails])
    _ajouter_liste(lignes, "Adresses", [_adresse(a, communes) for a in details.adresses])
    _ajouter(lignes, "Client des affaires", _numeros(details.affaires_client))
    _ajouter(lignes, "Intervenant dans les affaires", _numeros(details.affaires_intervenant))
    return "\n".join(lignes)


def _ajouter_liste(lignes: list[str], libelle: str, valeurs: list[str]) -> None:
    valeurs = [valeur for valeur in valeurs if valeur]
    if valeurs:
        lignes.append(f"{libelle} :")
        lignes.extend(f"- {valeur}" for valeur in valeurs)


def _avec_lieu(valeur: str, lieu: object) -> str:
    # « 04 67 98 76 54 (Bureau) ».
    lieu = _texte(lieu)
    return f"{valeur} ({lieu})" if valeur and lieu else valeur


def _adresse(adresse: dict, communes: dict[int, str]) -> str:
    # « 3 rue de la Mairie, Castries (34160) (Siège) ».
    parties = [_texte(adresse.get("Rue")), communes.get(_id(adresse.get("IdCommune")), "")]
    return _avec_lieu(", ".join(partie for partie in parties if partie), adresse.get("Lieu"))


def _numeros(numeros: list[str]) -> str:
    numeros = [numero for numero in dict.fromkeys(_texte(n) for n in numeros) if numero]
    autres = f" et {len(numeros) - _AFFAIRES_MAX} autres" if len(numeros) > _AFFAIRES_MAX else ""
    return ", ".join(numeros[:_AFFAIRES_MAX]) + autres


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
