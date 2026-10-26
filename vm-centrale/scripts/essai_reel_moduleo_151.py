"""Essai réel 1.5.1 (#194) : lecture seule sur le serveur Moduléo du cabinet.

Pour chaque domaine (devis, factures + reste à payer, temps passés, planning,
parcelles), lit quelques éléments via ClientModuleo (GET seuls), chronomètre,
affiche les champs utiles et les points à confirmer. Aucune écriture.

Lancement : `python scripts/essai_reel_moduleo_151.py` depuis vm-centrale/,
avec le `.env` du compte administrateur (clé Moduléo chiffrée).
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from vm_centrale.moduleo.client import ClientModuleo, ErreurModuleo, LecteurModuleo, TransportHttp
from vm_centrale.moduleo.configuration import config_moduleo
from vm_centrale.moduleo.droits import DroitsModuleo, chemin
from vm_centrale.moduleo.droits.catalogue import FICHIER_CATALOGUE
from vm_centrale.moduleo.fiches import Paiements, facture_emise, reste_a_payer
from vm_centrale.moduleo.routes import ROUTES_GET

_ECHANTILLON = 5
_JOURS_DEVIS_FACTURES = 30
_JOURS_TEMPS = 7
_JOURS_PLANNING = 7

_ROUTE_DEVIS = next(r for r in ROUTES_GET if r.startswith("cogeo/devis?texte="))
_ROUTE_FACTURES = next(r for r in ROUTES_GET if r.startswith("cogeo/facture?texte="))
_ROUTE_TEMPS = next(r for r in ROUTES_GET if r.startswith("cogeo/tempspasse?dateMin="))
_ROUTE_TACHES = next(r for r in ROUTES_GET if r.startswith("planning/tacheplanning?"))
_ROUTE_AFFAIRES = next(r for r in ROUTES_GET if r.startswith("cogeo/affaire?texte="))


def _droits_admin() -> DroitsModuleo:
    # Droits du groupe Admin versionné (catalogue.json), présentés au garde
    # sans base : le script n'est le compte de personne.
    donnees = json.loads(FICHIER_CATALOGUE.read_text(encoding="utf-8"))
    chemins: set[str] = set()
    for groupe in donnees["groupes"]:
        if groupe["nom"] != "Admin":
            continue
        for parties in groupe["droits"]:
            chemins.add(chemin(*parties))
    return DroitsModuleo(
        groupe_cogeo="Admin",
        groupe_planning="Admin",
        id_utilisateur_moduleo=None,
        droits=frozenset(chemins),
    )


def _chrono(label: str, fn):
    debut = time.perf_counter()
    try:
        resultat = fn()
        ms = (time.perf_counter() - debut) * 1000
        print(f"  [{ms:7.0f} ms] {label}")
        return resultat
    except ErreurModuleo as erreur:
        ms = (time.perf_counter() - debut) * 1000
        print(f"  [{ms:7.0f} ms] {label} -> ERREUR {type(erreur).__name__}: {erreur}")
        return None


def _cles(elements: list[dict], *champs: str) -> None:
    if not elements:
        print("    (aucun élément)")
        return
    for champ in champs:
        valeurs = Counter(e.get(champ) for e in elements)
        print(f"    {champ}: {dict(valeurs)}")
    print(f"    clés d'un élément: {sorted(elements[0].keys())}")


def devis(client: LecteurModuleo) -> None:
    print("\n=== Devis ===")
    depuis = (date.today() - timedelta(days=_JOURS_DEVIS_FACTURES)).isoformat()
    ids = _chrono(
        f"cogeo/devis?emis=true&dateEmissionMin={depuis}",
        lambda: client.lire(_ROUTE_DEVIS, {"emis": "true", "dateEmissionMin": depuis}),
    )
    if not ids:
        print("  aucun devis émis sur 30 jours ; essai sans filtre…")
        ids = _chrono("cogeo/devis (sans filtre, 5)", lambda: client.lire(_ROUTE_DEVIS, {}))
    if not ids:
        return
    ids = list(ids)[:_ECHANTILLON]
    elements = _chrono(
        f"cogeo/devis/multi ({len(ids)})",
        lambda: client.lire("cogeo/devis/multi?ids={ids}", {"ids": ",".join(str(i) for i in ids)}),
    )
    if not elements:
        return
    _cles(
        elements,
        "Etat",
        "DateEmission",
        "DateReponse",
        "DateExpiration",
        "MontantTotalHT",
        "MontantTotalTTC",
        "Numero",
    )
    # Filtre emis=false vs date d'émission vide.
    sans = _chrono(
        "cogeo/devis?emis=false (échantillon ids)",
        lambda: client.lire(_ROUTE_DEVIS, {"emis": "false"}),
    )
    print(f"    emis=false -> {len(sans or [])} ids")


def factures(client: LecteurModuleo) -> None:
    print("\n=== Factures + reste à payer ===")
    depuis = (date.today() - timedelta(days=_JOURS_DEVIS_FACTURES)).isoformat()
    ids = _chrono(
        f"cogeo/facture?emise=true&dateEmissionMin={depuis}",
        lambda: client.lire(_ROUTE_FACTURES, {"emise": "true", "dateEmissionMin": depuis}),
    )
    if not ids:
        ids = _chrono("cogeo/facture (sans filtre)", lambda: client.lire(_ROUTE_FACTURES, {}))
    if not ids:
        return
    ids = list(ids)[:_ECHANTILLON]
    elements = _chrono(
        f"cogeo/facture/multi ({len(ids)})",
        lambda: client.lire("cogeo/facture/multi?ids={ids}", {"ids": ",".join(str(i) for i in ids)}),
    )
    if not elements:
        return
    _cles(elements, "DateEmission", "MontantTotalTTC", "MontantTotalHT", "Numero")
    types_reglement: Counter = Counter()
    restes: list[str] = []
    for facture in elements:
        print(f"  — facture {facture.get('Numero')} id={facture.get('IdFacture')}")
        print(f"    DateEmission={facture.get('DateEmission')!r} emise={facture_emise(facture)}")
        print(f"    IdsReglements={facture.get('IdsReglements')}")
        avoirs = _chrono(
            f"avoirs facture {facture.get('IdFacture')}",
            lambda f=facture: client.lire("cogeo/avoir/facture?idFacture={idFacture}", {"idFacture": f["IdFacture"]}),
        )
        print(f"    avoirs={avoirs}")
        reglements = []
        for id_reglement in facture.get("IdsReglements") or []:
            reglement = _chrono(
                f"reglement {id_reglement}",
                lambda i=id_reglement: client.lire("cogeo/reglement/{idReglement}", {"idReglement": i}),
            )
            if reglement:
                reglements.append(reglement)
                types_reglement[reglement.get("TypeReglement")] += 1
                print(
                    f"    règlement {id_reglement}: TypeReglement={reglement.get('TypeReglement')!r} "
                    f"MontantTTC={reglement.get('MontantTTC')} "
                    f"pénalités={reglement.get('MontantReglementPenalitesTTC')} "
                    f"IdEcheance={reglement.get('IdEcheance')}"
                )
        complets = (
            not avoirs
            and len(reglements) == len(facture.get("IdsReglements") or [])
            and all(
                not r.get("MontantReglementPenalitesTTC") and r.get("TypeReglement") in (None, 0)
                for r in reglements
            )
        )
        paiements = Paiements(tuple(reglements), {}, complets)
        reste = reste_a_payer(facture, paiements)
        restes.append(f"{facture.get('Numero')}: reste={reste} complets={complets}")
        print(f"    -> reste_a_payer={reste} complets={complets}")
    print(f"  TypeReglement rencontrés: {dict(types_reglement)}")
    print(f"  Résumé restes: {restes}")


def temps_passes(client: LecteurModuleo) -> None:
    print("\n=== Temps passés ===")
    aujourdhui = date.today()
    debut = (aujourdhui - timedelta(days=_JOURS_TEMPS)).isoformat()
    fin = aujourdhui.isoformat()
    ids = _chrono(
        f"cogeo/tempspasse {debut}→{fin}",
        lambda: client.lire(_ROUTE_TEMPS, {"dateMin": debut, "dateMax": fin}),
    )
    if not ids:
        print("  aucun sur 7 jours ; élargir à 90 jours…")
        debut = (aujourdhui - timedelta(days=90)).isoformat()
        ids = _chrono(
            f"cogeo/tempspasse {debut}→{fin}",
            lambda: client.lire(_ROUTE_TEMPS, {"dateMin": debut, "dateMax": fin}),
        )
    if not ids:
        return
    ids = list(ids)[:_ECHANTILLON]
    elements = _chrono(
        f"cogeo/tempspasse/multi ({len(ids)})",
        lambda: client.lire("cogeo/tempspasse/multi?ids={ids}", {"ids": ",".join(str(i) for i in ids)}),
    )
    if not elements:
        return
    _cles(
        elements,
        "NombreHeure",
        "PrixVenteCollaborateur",
        "PrixRevientCollaborateur",
        "NombreKilometre",
        "IdCodeActivite",
    )


def planning(client: LecteurModuleo) -> None:
    print("\n=== Planning ===")
    aujourdhui = date.today()
    debut = aujourdhui.isoformat()
    fin = (aujourdhui + timedelta(days=_JOURS_PLANNING)).isoformat()
    ids = _chrono(
        f"planning/tacheplanning {debut}→{fin}",
        lambda: client.lire(_ROUTE_TACHES, {"dateDebut": debut, "dateFin": fin}),
    )
    if not ids:
        print("  aucun sur 7 jours ; élargir à −30…+7…")
        debut = (aujourdhui - timedelta(days=30)).isoformat()
        ids = _chrono(
            f"planning/tacheplanning {debut}→{fin}",
            lambda: client.lire(_ROUTE_TACHES, {"dateDebut": debut, "dateFin": fin}),
        )
    if not ids:
        return
    ids = list(ids)[:_ECHANTILLON]
    elements = _chrono(
        f"planning/tacheplanning/multi ({len(ids)})",
        lambda: client.lire(
            "planning/tacheplanning/multi?ids={ids}", {"ids": ",".join(str(i) for i in ids)}
        ),
    )
    if not elements:
        return
    _cles(
        elements,
        "Libelle",
        "DateHeureDebut",
        "DateHeureFin",
        "IdActivite",
        "IdAffaire",
        "Emplacement",
    )
    for tache in elements:
        print(
            f"  — « {tache.get('Libelle')} » Participants={tache.get('Participants')} "
            f"idsParticipants={tache.get('idsParticipants')} Equipements={tache.get('Equipements')} "
            f"privee?={tache.get('Privee') or tache.get('EstPrivee') or tache.get('Private')}"
        )
        # Résoudre un participant pour confirmer id planning → utilisateur.
        for id_p in (tache.get("Participants") or [])[:1]:
            up = _chrono(
                f"utilisateurplanning {id_p}",
                lambda i=id_p: client.lire(
                    "planning/utilisateurplanning/{idUtilisateurPlanning}", {"idUtilisateurPlanning": i}
                ),
            )
            print(f"    utilisateurplanning {id_p} -> {up}")


def parcelles(client: LecteurModuleo) -> None:
    print("\n=== Parcelles d'une affaire ===")
    ids_affaires = _chrono(
        "cogeo/affaire (5 récentes)",
        lambda: client.lire(_ROUTE_AFFAIRES, {"nbMaxResultats": 20}),
    )
    if not ids_affaires:
        return
    # Chercher une affaire qui a des parcelles.
    for id_affaire in list(ids_affaires)[:20]:
        ids_parcelles = _chrono(
            f"affaire {id_affaire}/parcelles",
            lambda i=id_affaire: client.lire(
                "cogeo/affaire/{idAffaire}/parcelles", {"idAffaire": i}
            ),
        )
        if not ids_parcelles:
            continue
        print(f"  affaire {id_affaire} -> {len(ids_parcelles)} parcelle(s)")
        id_parcelle = list(ids_parcelles)[0]
        parcelle = _chrono(
            f"parcelle {id_parcelle}",
            lambda i=id_parcelle: client.lire("cogeo/parcelle/{idParcelle}", {"idParcelle": i}),
        )
        if parcelle:
            print(f"    clés: {sorted(parcelle.keys())}")
            print(
                f"    Prefixe={parcelle.get('Prefixe')!r} Section={parcelle.get('Section')!r} "
                f"Numero={parcelle.get('Numero')!r} ContenanceCadatrale={parcelle.get('ContenanceCadatrale')!r} "
                f"LieuDit={parcelle.get('LieuDit')!r} IdCommune={parcelle.get('IdCommune')}"
            )
        ids_prop = _chrono(
            f"proprietaires parcelle {id_parcelle}",
            lambda i=id_parcelle: client.lire(
                "cogeo/parcelle/{idParcelle}/proprietaires", {"idParcelle": i}
            ),
        )
        print(f"    proprietaires ids={ids_prop}")
        for id_prop in list(ids_prop or [])[:2]:
            prop = _chrono(
                f"proprietaire {id_prop}",
                lambda i=id_prop: client.lire("cogeo/proprietaire/{idProprietaire}", {"idProprietaire": i}),
            )
            if prop:
                print(
                    f"    proprio {id_prop}: IdContact={prop.get('IdContact')} "
                    f"TypeDroit={prop.get('TypeDroit')!r} clés={sorted(prop.keys())}"
                )
        return
    print("  aucune affaire des 20 premières n'a de parcelle")


def etats_devis(client: LecteurModuleo) -> None:
    # Comme relever_enumerations_moduleo.py, pour ETATS_DEVIS.
    print("\n=== États de devis (filtre etat=…) ===")
    candidats = {
        "Créé": ("Cree", "Creee", "Creation"),
        "Émis": ("Emis", "Emise"),
        "Accepté": ("Accepte", "Acceptee"),
        "Refusé": ("Refuse", "Refusee"),
        "Annulé": ("Annule", "Annulee"),
        "Expiré": ("Expire", "Expiree"),
        "En attente": ("EnAttente", "Attente"),
        "Sans réponse": ("SansReponse", "Sans_Reponse"),
        "En cours": ("EnCours",),
        "Validé": ("Valide", "Validee"),
        "Signé": ("Signe", "Signee"),
        "Perdu": ("Perdu", "Perdue"),
        "Gagné": ("Gagne", "Gagnee"),
        "Brouillon": ("Brouillon",),
        "En étude": ("EnEtude", "Etude"),
        "À relancer": ("ARelancer", "A_Relancer"),
    }
    sans = client.lire(_ROUTE_DEVIS, {})
    for affiche, noms in candidats.items():
        for nom in noms:
            try:
                ids = client.lire(_ROUTE_DEVIS, {"etat": nom})
            except ErreurModuleo as erreur:
                print(f"  {affiche:<16} {nom:<16} refusé ({erreur})")
                continue
            if not ids:
                print(f"  {affiche:<16} {nom:<16} aucun résultat")
                continue
            if ids == sans:
                print(f"  {affiche:<16} {nom:<16} ignoré (mêmes ids)")
                continue
            echantillon = list(ids)[:_ECHANTILLON]
            elements = client.lire(
                "cogeo/devis/multi?ids={ids}", {"ids": ",".join(str(i) for i in echantillon)}
            )
            valeurs = Counter(e.get("Etat") for e in elements)
            print(f"  {affiche:<16} {nom:<16} Etat={dict(valeurs)} ({len(ids)} ids)")
            break


def main() -> None:
    config = config_moduleo()
    if config is None:
        raise SystemExit("Moduléo non configuré : voir les avertissements ci-dessus.")
    client = ClientModuleo(TransportHttp(config.url, config.api_key, config.security_code)).pour(
        _droits_admin()
    )
    print(f"Essai reel 1.5.1 (#194) - {config.url}")
    print(f"Journal: ClientModuleo n'autorise que GET (ROUTES_GET={len(ROUTES_GET)} routes).")
    devis(client)
    etats_devis(client)
    factures(client)
    temps_passes(client)
    planning(client)
    parcelles(client)
    print("\n=== Fin ===")


if __name__ == "__main__":
    main()
