import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from vm_centrale.lectures_outils import Fiche
from vm_centrale.moduleo import enumerations
from vm_centrale.moduleo.resolution import Noms, Utilisateur

# Fiche Moduléo (spec 1.5.0) : le texte dense d'un élément lu dans Moduléo,
# en noms, jamais la réponse brute ni un id. C'est ce que reçoit le modèle et
# ce qu'enregistre `lectures_outils`. Un champ vide n'a pas de ligne.
#
# Ses questions couvertes (#177) : écrites ici par gabarit, champ par
# champ, jamais par un appel Mistral. Un champ vide n'a pas de question.
#
# Un champ tient sur une ligne : ses retours à la ligne deviennent des
# espaces, sinon il coupe la ligne « • question → réponse » de la Mémoire
# (conversation 113, #180).

_DATES_AFFAIRE = (
    ("DateCreation", "Date de création"),
    ("DateOuverture", "Date d'ouverture"),
    ("DateLivraison", "Date de livraison"),
    ("DateCloture", "Date de clôture"),
)
# La fiche nomme les contacts sans leurs coordonnées : sans cette ligne, le
# modèle a répondu « pas disponibles dans Moduléo » à quatre demandes de
# coordonnées (#183, conversation 116).
_COORDONNEES_DES_CONTACTS = (
    "Coordonnées du client et des intervenants : absentes de cette fiche, à lire avec "
    "chercher_contacts_moduleo à partir de leur nom, seulement si le collaborateur les demande."
)


def fiche_affaire(affaire: dict, intervenants: list[dict], noms: Noms) -> Fiche:
    # Référence citée par la ligne « Sources : » : « Moduléo, affaire 2024-123 ».
    numero = _texte(affaire.get("Numero"))
    objet = _texte(affaire.get("Objet"))
    etat = _texte(enumerations.libelle(enumerations.ETATS_AFFAIRE, affaire.get("Etat")))
    dates = [(libelle, _date(affaire.get(champ))) for champ, libelle in _DATES_AFFAIRE]
    commune = noms.communes.get(_id(affaire.get("IdCommune")), "")
    adresse = _sans_la_commune(_texte(affaire.get("Adresse")), commune)
    client = _contact(noms, affaire.get("IdClient"), affaire.get("QualiteClient"))
    representant = _contact(noms, affaire.get("IdRepresentant"), affaire.get("QualiteRepresentant"))
    suivi = [
        ("Responsable", _utilisateur(noms.utilisateurs.get(_id(affaire.get("IdResponsable"))))),
        ("Chargé d'affaire", _utilisateur(noms.utilisateurs.get(_id(affaire.get("IdActeurEnCharge"))))),
    ]
    lignes_intervenants = [ligne for intervenant in intervenants if (ligne := _intervenant(noms, intervenant))]

    lignes = [f"Affaire {numero}"]
    _ajouter(lignes, "Objet", objet)
    _ajouter(lignes, "État", etat)
    for libelle, valeur in dates:
        _ajouter(lignes, libelle, valeur)
    _ajouter(lignes, "Adresse", adresse)
    _ajouter(lignes, "Commune", commune)
    _ajouter(lignes, "Client", client)
    _ajouter(lignes, "Représentant", representant)
    for libelle, valeur in suivi:
        _ajouter(lignes, libelle, valeur)
    if lignes_intervenants:
        lignes.append("Intervenants :")
        lignes.extend(f"- {ligne}" for ligne in lignes_intervenants)
    if client or representant or lignes_intervenants:
        lignes.append(_COORDONNEES_DES_CONTACTS)

    de_laffaire = f"de l'affaire {numero}"
    client_represente = f"{client}, représenté par {representant}" if client and representant else client
    questions = _questions(
        (f"Quel est l'objet {de_laffaire} ?", objet),
        (f"Quel est l'état {de_laffaire} ?", etat),
        (f"Quelles sont les dates {de_laffaire} ?", _libelles(dates)),
        (f"Où se trouve l'affaire {numero} ?", ", ".join(partie for partie in (adresse, commune) if partie)),
        (f"Qui est le client {de_laffaire} ?", client_represente),
        (f"Qui suit l'affaire {numero} ?", _libelles(suivi)),
        (f"Qui sont les intervenants {de_laffaire} ?", " ; ".join(lignes_intervenants)),
    )
    return Fiche(f"affaire {numero}", "\n".join(lignes), questions)


# TypeContact : entier dans le JSON, nom de l'énumération dans le XML du
# WADL (moduleo/enumerations.py). NonDefini ou 0 : pas de ligne.
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


def fiche_contact(contact: dict, details: DetailsContact, communes: dict[int, str]) -> Fiche:
    # Référence : « Moduléo, contact Étude Dupont ».
    nom = _texte(contact.get("Nom"))
    telephones = _valeurs(_avec_lieu(_texte(t.get("Numero")), t.get("Lieu")) for t in details.telephones)
    emails = _valeurs(_avec_lieu(_texte(e.get("Adresse")), e.get("Lieu")) for e in details.emails)
    adresses = _valeurs(_adresse(a, communes) for a in details.adresses)
    affaires = [
        ("Client des affaires", _numeros(details.affaires_client)),
        ("Intervenant dans les affaires", _numeros(details.affaires_intervenant)),
    ]

    lignes = [f"Contact {nom}"]
    type_contact = contact.get("TypeContact")
    if type_contact not in _TYPES_SANS_LIGNE:
        _ajouter(lignes, "Type", _texte(enumerations.libelle(enumerations.TYPES_CONTACT, type_contact)))
    _ajouter_liste(lignes, "Téléphones", telephones)
    _ajouter_liste(lignes, "Emails", emails)
    _ajouter_liste(lignes, "Adresses", adresses)
    for libelle, valeur in affaires:
        _ajouter(lignes, libelle, valeur)

    questions = _questions(
        (f"Comment joindre {nom} ?", " ; ".join(telephones + emails)),
        (f"Quelle est l'adresse de {nom} ?", " ; ".join(adresses)),
        (f"Dans quelles affaires apparaît {nom} ?", _libelles(affaires)),
    )
    return Fiche(f"contact {nom}", "\n".join(lignes), questions)


def _questions(*paires: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    # Jamais de retour à la ligne dans une réponse, quel que soit le champ.
    return tuple((question, " ".join(reponse.split())) for question, reponse in paires if reponse.strip())


def _libelles(valeurs: list[tuple[str, str]]) -> str:
    # « Responsable : Jean Martin ; Chargé d'affaire : Sophie Bernard ».
    return " ; ".join(f"{libelle} : {valeur}" for libelle, valeur in valeurs if valeur)


def _valeurs(valeurs) -> list[str]:
    return [valeur for valeur in valeurs if valeur]


def _ajouter_liste(lignes: list[str], libelle: str, valeurs: list[str]) -> None:
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
    # « …ALCARAZ\r\nZac Le Solan » → « …ALCARAZ Zac Le Solan ».
    return "" if valeur is None else " ".join(str(valeur).split())


def _sans_la_commune(adresse: str, commune: str) -> str:
    # Une adresse qui ne fait que répéter la commune (« 34270
    # SAINT-MATHIEU-DE-TRÉVIERS » pour « Saint-Mathieu-de-Tréviers (34270) »)
    # n'a pas de ligne (conversation 113, #180).
    mots = _mots(adresse)
    return "" if commune and mots and mots <= _mots(commune) else adresse


def _mots(texte: str) -> set[str]:
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", texte.casefold()) if not unicodedata.combining(c)
    )
    return set(re.findall(r"[a-z0-9]+", sans_accents))


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
