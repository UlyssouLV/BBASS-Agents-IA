"""Releve, en lecture seule, les valeurs JSON des etats d'affaire et des types de contact.

Le JSON de Moduleo donne `Etat` et `TypeContact` en entiers, le WADL nomme
l'enumeration (`Accepte`, `Societe`) sans dire quel entier va avec quel nom
(test humain 1.5.0, conversation 113, #180). Pour chaque nom candidat (et ses
variantes), le script cherche quelques elements filtres par ce nom, les lit
et affiche l'entier renvoye. Moduleo ignore sans erreur un nom inconnu : une
recherche qui renvoie les memes ids que sans filtre est signalee « ignore »,
et la variante suivante est essayee. Seules des routes GET de `ROUTES_GET`
partent, par `ClientModuleo`.

Lancement : `python scripts/relever_enumerations_moduleo.py` depuis
vm-centrale/, avec le `.env` du compte administrateur (cle Moduleo chiffree).
Reporter la correspondance dans `vm_centrale/moduleo/enumerations.py` et
`vm_centrale/moduleo/README.md`.
"""

from collections import Counter

from vm_centrale.moduleo.client import ClientModuleo, ErreurModuleo
from vm_centrale.moduleo.configuration import config_moduleo
from vm_centrale.moduleo.routes import ROUTES_GET

_ROUTE_AFFAIRES = next(route for route in ROUTES_GET if route.startswith("cogeo/affaire?texte="))
_ROUTE_CONTACTS = next(route for route in ROUTES_GET if route.startswith("cogeo/contact?texte="))

# Nom affiché dans l'interface → noms d'énumération à essayer, celui du
# relevé du 2026-10-08 d'abord (au féminin, pas celui du WADL).
_ETATS = {
    "Créée": ("Creee", "Cree", "Creation"),
    "En attente": ("EnAttente", "Attente"),
    "Acceptée": ("Acceptee", "Accepte"),
    "Production": ("Production", "EnProduction"),
    "Suspendue": ("Suspendue", "Suspendu"),
    "Prod. terminée": ("Terminee", "ProductionTerminee", "ProdTerminee"),
    "Clôturée": ("Cloturee", "Cloture"),
    "Annulée": ("Annulee", "Annule"),
}
_TYPES = {
    "Personne": ("Personne",),
    "Société": ("Societe",),
    "Collectivité": ("Collectivite",),
    "Groupe de contacts": ("GroupeContacts", "GroupeContact"),
}
# Éléments lus par nom : assez pour voir si l'entier est constant.
_ECHANTILLON = 5


def _relever(
    client: ClientModuleo, candidats: dict, route_ids: str, filtre: str, nb: str, route_multi: str, champ: str
) -> None:
    sans_filtre = client.lire(route_ids, {nb: _ECHANTILLON})
    for affiche, noms in candidats.items():
        for nom in noms:
            try:
                ids = client.lire(route_ids, {filtre: nom, nb: _ECHANTILLON})
            except ErreurModuleo as erreur:
                print(f"  {affiche:<20} {nom:<20} refusé ({erreur})")
                continue
            if not ids:
                print(f"  {affiche:<20} {nom:<20} aucun résultat")
                continue
            if ids == sans_filtre:
                print(f"  {affiche:<20} {nom:<20} ignoré (mêmes ids que sans filtre)")
                continue
            elements = client.lire(route_multi, {"ids": ",".join(str(i) for i in ids)})
            valeurs = Counter(element.get(champ) for element in elements)
            print(f"  {affiche:<20} {nom:<20} {champ} = {dict(valeurs)} ({len(ids)} lus)")
            break


def main() -> None:
    config = config_moduleo()
    if config is None:
        raise SystemExit("Moduléo non configuré : voir les avertissements ci-dessus.")
    client = ClientModuleo(config.url, config.api_key, config.security_code)
    print("États d'affaire (cogeo/affaire?etatAffaire=…) :")
    _relever(client, _ETATS, _ROUTE_AFFAIRES, "etatAffaire", "nbMaxResultats", "cogeo/affaire/multi?ids={ids}", "Etat")
    print("Types de contact (cogeo/contact?typeContact=…) :")
    _relever(client, _TYPES, _ROUTE_CONTACTS, "typeContact", "nbMaxResultat", "cogeo/contact/multi?ids={ids}", "TypeContact")


if __name__ == "__main__":
    main()
