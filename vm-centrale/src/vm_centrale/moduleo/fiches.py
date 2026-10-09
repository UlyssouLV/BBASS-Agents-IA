import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from vm_centrale.lectures_outils import Fiche
from vm_centrale.moduleo import enumerations
from vm_centrale.moduleo.droits import DroitsModuleo, chemin
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


@dataclass(frozen=True)
class ParcellesAffaire:
    # Ce que `avec_parcelles` lit pour une affaire (#193) : ses parcelles
    # telles que Moduléo les renvoie et, par id de parcelle, les ids
    # contact de ses propriétaires ; None : propriétaires non autorisés
    # pour le compte (« Rechercher des contacts », données personnelles).
    parcelles: list[dict]
    proprietaires: dict[int, list[int]] | None


_PROPRIETAIRES_NON_AUTORISES = "Propriétaires : non autorisés pour votre compte"
# Préfixe cadastral par défaut : pas affiché (« AB 123 »).
_PREFIXES_SANS_AFFICHAGE = ("", "000")


def fiche_affaire(
    affaire: dict, intervenants: list[dict], noms: Noms, parcelles: ParcellesAffaire | None = None
) -> Fiche:
    # Référence citée par la ligne « Sources : » : « Moduléo, affaire 2024-123 ».
    # `parcelles` : seulement quand le collaborateur les demande (#193).
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
    lignes_parcelles = [_parcelle(noms, parcelle, parcelles) for parcelle in parcelles.parcelles] if parcelles else []
    if parcelles is not None:
        if lignes_parcelles:
            lignes.append("Parcelles :")
            lignes.extend(f"- {ligne}" for ligne in lignes_parcelles)
        else:
            lignes.append("Parcelles : aucune dans Moduléo")
        if parcelles.proprietaires is None and lignes_parcelles:
            lignes.append(_PROPRIETAIRES_NON_AUTORISES)

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
        (f"Quelles sont les parcelles {de_laffaire} ?", " ; ".join(lignes_parcelles)),
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


# Vérification par champ (#188) : sans ce sous-droit, la fiche dit que le
# code de comptabilité n'est pas autorisé, jamais qu'il est absent.
_DROIT_COMPTABILITE = chemin("Contacts", "Consulter et modifier le numéro de compte de comptabilité d'un contact")


def fiche_contact(contact: dict, details: DetailsContact, communes: dict[int, str], droits: DroitsModuleo) -> Fiche:
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
    if (mention := droits.section(_DROIT_COMPTABILITE, "Codes de comptabilité")) is not None:
        lignes.append(mention)
    else:
        _ajouter(lignes, "Code de comptabilité", _texte(contact.get("CodeComptabilite")))
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


# Devis (#189). `Etat` 0 : valeur par défaut, pas de ligne.
_ETATS_DEVIS_SANS_LIGNE = (None, 0, "")


def fiche_devis(devis: dict, affaire: dict | None, noms: Noms) -> Fiche:
    # Référence : « Moduléo, devis D-2026-042 ». `affaire` : celle du devis,
    # dont le client est celui de la fiche (le destinataire du devis exige
    # le droit des factures).
    numero = _texte(devis.get("Numero"))
    objet = _texte(devis.get("Objet"))
    affaire = affaire or {}
    numero_affaire = _texte(affaire.get("Numero"))
    client = noms.contacts.get(_id(affaire.get("IdClient")), "")
    emission, reponse = _date(devis.get("DateEmission")), _date(devis.get("DateReponse"))
    etat = devis.get("Etat")
    etat = "" if etat in _ETATS_DEVIS_SANS_LIGNE else _texte(enumerations.libelle(enumerations.ETATS_DEVIS, etat))
    suivi = [
        ("Responsable", _nom(noms.utilisateurs.get(_id(devis.get("IdResponsable"))))),
        ("Rédacteur", _nom(noms.utilisateurs.get(_id(devis.get("IdRedacteur"))))),
    ]
    montant_ht, montant_ttc = montant(devis.get("MontantTotalHT")), montant(devis.get("MontantTotalTTC"))

    lignes = [f"Devis {numero}"]
    _ajouter(lignes, "Objet", objet)
    _ajouter(lignes, "Affaire", numero_affaire)
    _ajouter(lignes, "Client", client)
    _ajouter(lignes, "Date de création", _date(devis.get("DateCreation")))
    _ajouter(lignes, "Date d'émission", emission or "non émis")
    _ajouter(lignes, "Date de réponse", reponse)
    _ajouter(lignes, "Date d'expiration", _date(devis.get("DateExpiration")))
    _ajouter(lignes, "État", etat)
    for libelle, valeur in suivi:
        _ajouter(lignes, libelle, valeur)
    _ajouter(lignes, "Montant HT", montant_ht)
    _ajouter(lignes, "Montant TTC", montant_ttc)

    du_devis = f"du devis {numero}"
    ou_en_est = [
        f"Émis le {emission}" if emission else "Non émis",
        f"réponse le {reponse}" if reponse else "",
        f"état {etat}" if etat else "",
    ]
    questions = _questions(
        (f"Quel est l'objet {du_devis} ?", objet),
        (f"Quel est le montant {du_devis} ?", _montants(montant_ht, montant_ttc)),
        (f"Où en est le devis {numero} ?", " ; ".join(partie for partie in ou_en_est if partie)),
        (
            f"À quelle affaire se rattache le devis {numero} ?",
            f"{numero_affaire}, client {client}" if numero_affaire and client else numero_affaire,
        ),
        (f"Qui suit le devis {numero} ?", _libelles(suivi)),
    )
    return Fiche(f"devis {numero}", "\n".join(lignes), questions)


def synthese_devis(devis: list[dict], affiches: int, portee: str, reference: str) -> Fiche:
    # Totaux calculés par la VM sur tous les devis trouvés, pas seulement
    # les `affiches` (spec 1.5.1) : un total fait par le modèle serait
    # retiré par le garde-fou chiffres. `portee` : « trouvés (texte
    # « Bornage ») », « émis depuis le 09/09/2026 (30 derniers jours) » ;
    # `reference` : « devis émis du 09/09/2026 au 09/10/2026 ».
    nombre = len(devis)
    totaux = _montants(
        montant(sum(d.get("MontantTotalHT") or 0 for d in devis)),
        montant(sum(d.get("MontantTotalTTC") or 0 for d in devis)),
    )
    texte = f"{nombre} devis {portee}, total {totaux}."
    if nombre > affiches:
        recents = "Le plus récent affiché" if affiches == 1 else f"Les {affiches} plus récents affichés"
        texte += f" {recents}, précise la recherche."
    questions = _questions(
        (f"Combien de {reference} ?", str(nombre)),
        (f"Quel est le montant total des {reference} ?", totaux),
    )
    return Fiche(reference, texte, questions)


@dataclass(frozen=True)
class Paiements:
    # Règlements d'une facture lus dans Moduléo (#190), chacun avec son
    # échéance quand elle a été lue. `complets` : tous les `IdsReglements`
    # lus, et Moduléo ne dit rien qui empêche de déduire le reste à payer
    # (avoir, pénalités, type de règlement autre que 0).
    reglements: tuple[dict, ...]
    echeances: dict[int, dict]
    complets: bool


def facture_emise(facture: dict) -> bool:
    # Une date d'émission (#190, sens de `emise` à confirmer à l'essai
    # réel) ; l'an 1 est un champ vide côté Moduléo.
    return bool(_date(facture.get("DateEmission")))


def reste_a_payer(facture: dict, paiements: Paiements | None) -> float | None:
    # TTC de la facture moins ses règlements, seulement quand Moduléo permet
    # de le déduire : facture émise, montants lus, règlements complets.
    # Jamais estimé (spec 1.5.1) : sinon `None`, et pas de ligne.
    ttc = facture.get("MontantTotalTTC")
    if paiements is None or not paiements.complets or not facture_emise(facture):
        return None
    if not isinstance(ttc, (int, float)) or not all(_nombre(r.get("MontantTTC")) for r in paiements.reglements):
        return None
    reste = round(ttc - sum(r["MontantTTC"] for r in paiements.reglements), 2)
    return reste if reste >= 0 else None


def fiche_facture(
    facture: dict, affaire: dict | None, destinataire: dict | None, paiements: Paiements | None, noms: Noms
) -> Fiche:
    # Référence : « Moduléo, facture F-2026-118 ». Client : le contact
    # destinataire de la facture, sinon le client de son affaire.
    # `paiements` : `None` quand ils n'ont pas été lus (facture non émise).
    numero = _texte(facture.get("Numero"))
    objet = _texte(facture.get("Objet"))
    affaire = affaire or {}
    numero_affaire = _texte(affaire.get("Numero"))
    client = noms.contacts.get(_id((destinataire or {}).get("IdContact")), "") or noms.contacts.get(
        _id(affaire.get("IdClient")), ""
    )
    emission = _date(facture.get("DateEmission"))
    suivi = [
        ("Responsable", _nom(noms.utilisateurs.get(_id(facture.get("IdResponsable"))))),
        ("Rédacteur", _nom(noms.utilisateurs.get(_id(facture.get("IdRedacteur"))))),
    ]
    montant_ht, montant_ttc = montant(facture.get("MontantTotalHT")), montant(facture.get("MontantTotalTTC"))
    reglements = [_reglement(r, paiements.echeances) for r in paiements.reglements] if paiements else []
    reste = montant(reste_a_payer(facture, paiements))

    lignes = [f"Facture {numero}"]
    _ajouter(lignes, "Objet", objet)
    _ajouter(lignes, "Affaire", numero_affaire)
    _ajouter(lignes, "Client", client)
    _ajouter(lignes, "Date de création", _date(facture.get("DateCreation")))
    _ajouter(lignes, "Date d'émission", emission or "non émise")
    for libelle, valeur in suivi:
        _ajouter(lignes, libelle, valeur)
    _ajouter(lignes, "Montant HT", montant_ht)
    _ajouter(lignes, "Montant TTC", montant_ttc)
    if reglements:
        _ajouter_liste(lignes, "Échéances et règlements", reglements)
    elif paiements is not None and emission:
        lignes.append("Échéances et règlements : aucun règlement")
    _ajouter(lignes, "Reste à payer", reste)

    regle = montant(sum(r["MontantTTC"] for r in paiements.reglements)) if paiements and reglements and reste else ""
    payee = [
        f"Émise le {emission}" if emission else "Non émise",
        f"réglé {regle} TTC" if regle else "",
        f"reste à payer {reste}" if reste else "",
    ]
    questions = _questions(
        (f"Quel est l'objet de la facture {numero} ?", objet),
        (f"Quel est le montant de la facture {numero} ?", _montants(montant_ht, montant_ttc)),
        (f"La facture {numero} est-elle payée ?", " ; ".join(partie for partie in payee if partie)),
        (
            f"À quelle affaire se rattache la facture {numero} ?",
            f"{numero_affaire}, client {client}" if numero_affaire and client else numero_affaire,
        ),
        (f"Qui suit la facture {numero} ?", _libelles(suivi)),
    )
    return Fiche(f"facture {numero}", "\n".join(lignes), questions)


def synthese_factures(
    factures: list[dict], reste: float | None, sans_reste: str, affiches: int, portee: str, reference: str
) -> Fiche:
    # Comme `synthese_devis` (#189), avec le reste à payer des factures
    # émises (#190), calculé par l'outil sur l'ensemble trouvé : `reste`,
    # ou `None` et la raison `sans_reste` ; `None` et "" : aucune facture
    # émise, pas de reste à payer. `portee` : « trouvées (texte
    # « Bornage ») », « émises depuis le 09/09/2026 (30 derniers jours) ».
    nombre = len(factures)
    totaux = _montants(
        montant(sum(f.get("MontantTotalHT") or 0 for f in factures)),
        montant(sum(f.get("MontantTotalTTC") or 0 for f in factures)),
    )
    toutes_emises = all(facture_emise(f) for f in factures)
    du_reste = montant(reste)
    if du_reste:
        texte_reste = f", reste à payer {du_reste}" if toutes_emises else f", reste à payer sur les émises {du_reste}"
    else:
        texte_reste = f", reste à payer non calculé {sans_reste}" if sans_reste else ""
    texte = f"{nombre} {'facture' if nombre == 1 else 'factures'} {portee}, total {totaux}{texte_reste}."
    if nombre > affiches:
        recentes = "La plus récente affichée" if affiches == 1 else f"Les {affiches} plus récentes affichées"
        texte += f" {recentes}, précise la recherche."
    questions = _questions(
        (f"Combien de {reference} ?", str(nombre)),
        (f"Quel est le montant total des {reference} ?", totaux),
        (f"Quel est le reste à payer des {reference} ?", du_reste),
    )
    return Fiche(reference, texte, questions)


# Temps passés (#191). Prix seulement avec leur sous-droit, sinon une
# mention (vérification par champ, #188) ; sens exact (taux horaire ou
# prix de la ligne) à confirmer à l'essai réel : affichés tels que lus.
_PRIX_REVIENT = ("Affaires, groupes et archivage", "Voir l'onglet prix de revient")
_PRIX_TEMPS_PASSES = (
    ("PrixVenteCollaborateur", "Prix de vente", chemin(*_PRIX_REVIENT, "Voir le prix de vente des temps passés")),
    ("PrixRevientCollaborateur", "Prix de revient", chemin(*_PRIX_REVIENT, "Voir le prix de revient des temps passés")),
)


@dataclass(frozen=True)
class NomsTempsPasses:
    # Ids → noms d'un appel de chercher_temps_passes_moduleo : utilisateurs,
    # numéros d'affaire, codes activité.
    utilisateurs: dict[int, Utilisateur]
    affaires: dict[int, str]
    codes_activite: dict[int, str]


def heures(valeur: object) -> str:
    # 4.0 → « 4 h », 7.5 → « 7,5 h » ; absent : pas de ligne.
    return f"{_decimal(valeur)} h" if _nombre(valeur) else ""


def fiche_temps_passe(temps: dict, noms: NomsTempsPasses, droits: DroitsModuleo) -> Fiche:
    # Référence : « Moduléo, temps passé du 07/10/2026, Jean Martin,
    # affaire 2024-123 ».
    jour = _date(temps.get("Date")) or "date inconnue"
    collaborateur = _nom(noms.utilisateurs.get(_id(temps.get("IdUtilisateur"))))
    affaire = noms.affaires.get(_id(temps.get("IdAffaire")), "")
    code = noms.codes_activite.get(_id(temps.get("IdCodeActivite")), "")
    du_temps = heures(temps.get("NombreHeure"))
    kilometres = temps.get("NombreKilometre")

    lignes = [f"Temps passé du {jour}"]
    _ajouter(lignes, "Collaborateur", collaborateur)
    _ajouter(lignes, "Affaire", affaire)
    _ajouter(lignes, "Code activité", code)
    _ajouter(lignes, "Heures", du_temps)
    _ajouter(lignes, "Kilomètres", _decimal(kilometres) if _nombre(kilometres) and kilometres else "")
    _ajouter(lignes, "Lieu", _texte(temps.get("Lieu")))
    _ajouter(lignes, "Commentaire", _texte(temps.get("Commentaire")))
    for champ, titre, droit in _PRIX_TEMPS_PASSES:
        if (mention := droits.section(droit, titre)) is not None:
            lignes.append(mention)
        else:
            _ajouter(lignes, titre, montant(temps.get(champ)))

    reference = ", ".join(
        partie for partie in (f"temps passé du {jour}", collaborateur, f"affaire {affaire}" if affaire else "") if partie
    )
    questions = _questions(
        (f"Combien d'heures pour le {reference} ?", du_temps),
        (f"Quel code activité pour le {reference} ?", code),
    )
    return Fiche(reference, "\n".join(lignes), questions)


def synthese_temps_passes(
    temps: list[dict], noms: NomsTempsPasses, affiches: int, portee: str, reference: str
) -> Fiche:
    # Totaux calculés par la VM sur tous les temps passés trouvés (spec
    # 1.5.1) : général, par collaborateur, par code activité. `portee` :
    # « trouvés (affaire 2024-123) », « saisis du 02/10/2026 au 09/10/2026
    # (7 derniers jours) ».
    nombre = len(temps)
    total = heures(round(sum(_heures_de(t) for t in temps), 2))

    def collaborateur(id_utilisateur: int) -> str:
        return _nom(noms.utilisateurs.get(id_utilisateur)) or "collaborateur inconnu"

    def code_activite(id_code: int) -> str:
        return noms.codes_activite.get(id_code, "code activité inconnu") if id_code else "sans code activité"

    par_collaborateur = _repartition(temps, "IdUtilisateur", collaborateur)
    par_code = _repartition(temps, "IdCodeActivite", code_activite)
    texte = (
        f"{nombre} {'temps passé' if nombre == 1 else 'temps passés'} {portee}, total {total}. "
        f"Par collaborateur : {par_collaborateur}. Par code activité : {par_code}."
    )
    if nombre > affiches:
        recents = "Le plus récent affiché" if affiches == 1 else f"Les {affiches} plus récents affichés"
        texte += f" {recents}, précise la recherche."
    questions = _questions(
        (f"Combien d'heures dans les {reference} ?", total),
        (f"Combien d'heures par collaborateur dans les {reference} ?", par_collaborateur),
        (f"Combien d'heures par code activité dans les {reference} ?", par_code),
    )
    return Fiche(reference, texte, questions)


# Planning (#192). Une tâche : libellé, date et heures, participants,
# activité, matériel, affaire liée. Sans groupe Cogeo, le numéro de
# l'affaire n'est pas lu (`affaires` à None) : une mention le remplace.
_AFFAIRE_NON_AUTORISEE = "Affaire : non autorisée pour votre compte"


@dataclass(frozen=True)
class NomsPlanning:
    # Ids → noms d'un appel de chercher_planning_moduleo : utilisateurs
    # planning, activités, équipements, numéros d'affaire (None : non
    # autorisés).
    participants: dict[int, str]
    activites: dict[int, str]
    equipements: dict[int, str]
    affaires: dict[int, str] | None


def _horaire(debut: object, fin: object) -> str:
    # « 12/10/2026, 08:00 – 12:00 » ; sur plusieurs jours, « du 14/10/2026
    # 08:00 au 15/10/2026 17:00 » ; sans heure (00:00 – 00:00), le jour.
    debut, fin = _texte(debut), _texte(fin)
    jour_debut, jour_fin = _date(debut), _date(fin)
    heure_debut, heure_fin = debut[11:16], fin[11:16]
    if not jour_debut:
        return ""
    if jour_fin and jour_fin != jour_debut:
        return f"du {' '.join(_valeurs((jour_debut, heure_debut)))} au {' '.join(_valeurs((jour_fin, heure_fin)))}"
    if heure_debut in ("", "00:00") and heure_fin in ("", "00:00"):
        return jour_debut
    return f"{jour_debut}, {heure_debut} – {heure_fin}" if heure_fin else f"{jour_debut}, {heure_debut}"


def fiche_tache(tache: dict, noms: NomsPlanning) -> Fiche:
    # Référence : « Moduléo, tâche « Bornage lot B » du 12/10/2026 ».
    libelle = _texte(tache.get("Libelle")) or "sans libellé"
    jour = _date(tache.get("DateHeureDebut")) or "date inconnue"
    horaire = _horaire(tache.get("DateHeureDebut"), tache.get("DateHeureFin"))
    participants = ", ".join(_valeurs(noms.participants.get(i, "") for i in tache.get("Participants") or []))
    activite = noms.activites.get(_id(tache.get("IdActivite")), "")
    materiel = ", ".join(_valeurs(noms.equipements.get(i, "") for i in tache.get("Equipements") or []))
    id_affaire = _id(tache.get("IdAffaire"))
    affaire = noms.affaires.get(id_affaire, "") if noms.affaires is not None else ""

    lignes = [f"Tâche « {libelle} »"]
    _ajouter(lignes, "Date", horaire)
    _ajouter(lignes, "Participants", participants)
    _ajouter(lignes, "Activité", activite)
    _ajouter(lignes, "Matériel", materiel)
    if id_affaire and noms.affaires is None:
        lignes.append(_AFFAIRE_NON_AUTORISEE)
    else:
        _ajouter(lignes, "Affaire", affaire)
    _ajouter(lignes, "Lieu", _texte(tache.get("Emplacement")))

    reference = f"tâche « {libelle} » du {jour}"
    questions = _questions(
        (f"Quand a lieu la {reference} ?", horaire),
        (f"Qui participe à la {reference} ?", participants),
        (f"Quelle activité pour la {reference} ?", activite),
        (f"Quel matériel pour la {reference} ?", materiel),
        (f"Quelle affaire pour la {reference} ?", affaire),
    )
    return Fiche(reference, "\n".join(lignes), questions)


def synthese_planning(
    taches: list[dict], participants: dict[int, str], affiches: int, entete: str, reference: str
) -> Fiche:
    # Calculée par la VM sur toutes les tâches trouvées (spec 1.5.1) :
    # nombre, et participants avec leur nombre de tâches. `entete` : « 2
    # tâches au planning du 09/10/2026 au 16/10/2026 (…) ».
    nombre = len(taches)
    comptes: dict[str, int] = {}
    for tache in taches:
        for nom in dict.fromkeys(_valeurs(participants.get(i, "") for i in tache.get("Participants") or [])):
            comptes[nom] = comptes.get(nom, 0) + 1
    qui = ", ".join(
        f"{nom} ({n} {'tâche' if n == 1 else 'tâches'})"
        for nom, n in sorted(comptes.items(), key=lambda element: (-element[1], element[0]))
    )
    texte = f"{entete}."
    if qui:
        texte += f" Participants : {qui}."
    if nombre > affiches:
        premieres = "La première affichée" if affiches == 1 else f"Les {affiches} premières affichées"
        texte += f" {premieres}, précise la recherche."
    questions = _questions(
        (f"Combien de tâches au {reference} ?", str(nombre)),
        (f"Qui est au {reference} ?", qui),
    )
    return Fiche(reference, texte, questions)


def _heures_de(temps: dict) -> float:
    valeur = temps.get("NombreHeure")
    return valeur if _nombre(valeur) else 0.0


def _repartition(temps: list[dict], champ: str, nom) -> str:
    # « Jean Martin 6 h, Sophie Bernard 1,5 h » : le plus d'heures d'abord.
    totaux: dict[str, float] = {}
    for t in temps:
        libelle = nom(_id(t.get(champ)))
        totaux[libelle] = totaux.get(libelle, 0.0) + _heures_de(t)
    return ", ".join(
        f"{libelle} {heures(round(valeur, 2))}"
        for libelle, valeur in sorted(totaux.items(), key=lambda element: (-element[1], element[0]))
    )


def _decimal(valeur: object) -> str:
    # 4.0 → « 4 », 7.5 → « 7,5 », 1.25 → « 1,25 ».
    return f"{valeur:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _reglement(reglement: dict, echeances: dict[int, dict]) -> str:
    # « Règlement du 25/09/2026 : 600,00 € TTC (Virement), échéance du
    # 30/09/2026 de 600,00 € ».
    ligne = f"Règlement du {_date(reglement.get('Date')) or 'date inconnue'}"
    if du_montant := montant(reglement.get("MontantTTC")):
        ligne += f" : {du_montant} TTC"
    ligne = _avec_lieu(ligne, reglement.get("Mode"))
    echeance = echeances.get(_id(reglement.get("IdEcheance")))
    if echeance:
        jour, du_montant = _date(echeance.get("Date")), montant(echeance.get("Montant"))
        ligne += f", échéance{f' du {jour}' if jour else ''}{f' de {du_montant}' if du_montant else ''}"
    return ligne


def _nombre(valeur: object) -> bool:
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def montant(valeur: object) -> str:
    # 18400.5 → « 18 400,50 € » ; absent : pas de ligne.
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return ""
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _montants(ht: str, ttc: str) -> str:
    # « 1 200,00 € HT, 1 440,00 € TTC ».
    return ", ".join(f"{valeur} {taxe}" for valeur, taxe in ((ht, "HT"), (ttc, "TTC")) if valeur)


def _nom(utilisateur: Utilisateur | None) -> str:
    return utilisateur.nom if utilisateur is not None else ""


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


def _parcelle(noms: Noms, parcelle: dict, parcelles: ParcellesAffaire) -> str:
    # « AB 123, Castries (34160), lieu-dit Les Plans, contenance 1 234 m²,
    # propriétaires : SCI Les Oliviers, Paul Durand ».
    prefixe = _texte(parcelle.get("Prefixe"))
    reference = " ".join(
        _valeurs((
            "" if prefixe in _PREFIXES_SANS_AFFICHAGE else prefixe,
            _texte(parcelle.get("Section")),
            _texte(parcelle.get("Numero")),
        ))
    )
    contenance = parcelle.get("ContenanceCadatrale")
    proprietaires = (parcelles.proprietaires or {}).get(_id(parcelle.get("IdParcelle")), [])
    noms_proprietaires = ", ".join(_valeurs(dict.fromkeys(noms.contacts.get(i, "") for i in proprietaires)))
    return ", ".join(
        _valeurs((
            reference or "référence inconnue",
            noms.communes.get(_id(parcelle.get("IdCommune")), ""),
            f"lieu-dit {lieu_dit}" if (lieu_dit := _texte(parcelle.get("LieuDit"))) else "",
            f"contenance {_surface(contenance)}" if _nombre(contenance) and contenance else "",
            f"propriétaires : {noms_proprietaires}" if noms_proprietaires else "",
        ))
    )


def _surface(valeur: float) -> str:
    # Contenance cadastrale, en m² (unité à confirmer à l'essai réel,
    # #178) : 1234.0 → « 1 234 m² », 560.5 → « 560,5 m² ».
    entier = f"{valeur:,.2f}".rstrip("0").rstrip(".")
    return entier.replace(",", " ").replace(".", ",") + " m²"


def _intervenant(noms: Noms, intervenant: dict) -> str:
    # « Office notarial Rives (Notaire), représenté par Claire Rives (Clerc) ».
    ligne = _contact(noms, intervenant.get("IdContact"), intervenant.get("QualiteIntervenant"))
    if not ligne:
        return ""
    representant = _contact(noms, intervenant.get("IdRepresentant"), intervenant.get("QualiteRepresentant"))
    return f"{ligne}, représenté par {representant}" if representant else ligne
