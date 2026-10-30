import json
import logging
import re
from typing import Any

from vm_centrale.moduleo.carte import (
    IdIntrouvable,
    champs_modifies,
    differences_en_noms,
    element_en_noms,
    fiche_en_noms,
    lignes_en_noms,
)
from vm_centrale.moduleo.client import ErreurModuleo, LecteurModuleo, RequeteInterdite
from vm_centrale.moduleo.droits import DroitManquant, DroitsModuleo, ecriture_possible, refus_d_ecriture
from vm_centrale.moduleo.ecritures import REFUSEE, carte_de, ids_renvoyes, proposer
from vm_centrale.moduleo.relecture import RELECTURES, ElementIntrouvable, relire
from vm_centrale.moduleo.resolution import IDS_SANS_RECHERCHE_PAR_NOM, resoudre_codes_activite
from vm_centrale.moduleo.routes import ROUTES_ECRITURE, RouteEcriture
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil
from vm_centrale.outils.moduleo.commun import INDISPONIBLE, LecteurTrace
from vm_centrale.statut_tour import consultation_moduleo

# Écriture Moduléo (spec 1.5.2, #204, ADR-0023) : deux outils génériques.
# `decrire_ecriture_moduleo` donne les champs d'une route sans appeler
# Moduléo ; `ecrire_moduleo` propose l'écriture (Carte de confirmation),
# n'envoie rien. PUT et DELETE (#205) : l'élément visé est relu avant la
# carte. Règles : README.md.

_DECRIRE = "decrire_ecriture_moduleo"
_ECRIRE = "ecrire_moduleo"

SERA_SUPPRIME = "Sera supprimé"

PROPOSEE = "Écriture proposée au collaborateur, en attente de sa confirmation. Rien n'a été écrit."
_INTROUVABLE = "L'élément visé n'existe pas dans Moduléo : écriture non proposée. Rien n'a été écrit."
_ID_INTROUVABLE = (
    "Élément introuvable dans Moduléo : {id}. Écriture non proposée. Rien n'a été écrit. "
    "N'essaie pas un autre id : demande au collaborateur quel élément il veut."
)
_RELECTURE_REFUSEE = (
    "Votre compte ne peut pas lire l'élément visé dans Moduléo : écriture non proposée. Rien n'a été écrit. "
    "Demandez à un compte administrateur si vous en avez besoin."
)
_SANS_CHANGEMENT = "Écriture non proposée : le corps ne change aucun champ de l'élément visé. Rien n'a été écrit."
_ROUTE_INCONNUE = (
    "Route d'écriture Moduléo inconnue ou fermée : « {route} ». Choisis une route listée dans la "
    "description de ecrire_moduleo, sous la forme « MÉTHODE route ». Rien n'a été écrit."
)
_NON_PROPOSEE = "Écriture non proposée : {erreur} Rien n'a été écrit."
_JSON_ILLISIBLE = "« {nom} » n'est pas un objet JSON valide."
_ID_CONTREDIT = (
    "le champ {champ} du corps ({valeur}) ne désigne pas le même élément que le paramètre {parametre} "
    "de la route ({id})."
)
_SANS_RECHERCHE = (
    "Champs sans moyen de retrouver l'id à partir d'un nom (l'API ne les lit que par id) : {champs}. "
    "Ne devine jamais leur valeur : utilise seulement un id donné par le collaborateur. Sinon, dis-lui "
    "qu'il n'existe pas, depuis le chat, de moyen de retrouver l'élément à partir de son nom, et propose "
    "l'écriture sans ce champ s'il est facultatif."
)
_NON_FOURNIS = (
    "Champs dont aucune fiche ne donne l'id : {champs}. Ne devine jamais leur valeur et ne demande jamais "
    "d'id au collaborateur : seul un id renvoyé par une écriture confirmée de cette conversation "
    "([id Moduléo <n>]) est utilisable. Sinon, omets le champ s'il est facultatif ; s'il est requis, dis au "
    "collaborateur que cette écriture n'est pas encore possible depuis le chat."
)
# Troisième passage de #206, scénario 10 : aucune fiche ne donne l'id d'un
# code activité ni celui du collaborateur ; decrire les lit dans Moduléo.
_CODES_ACTIVITE = "Codes activité Moduléo (IdCodeActivite) : {codes}."
_COLLABORATEUR = "Collaborateur du compte (IdUtilisateur) : [id Moduléo {id}]."
_PAS_ENCORE_POSSIBLE = (
    "Cette écriture n'est pas encore possible depuis le chat : BBASS ne peut pas retrouver {elements} dans "
    "Moduléo. Rien n'a été écrit."
)
_SANS_ID_DEVINE = (
    "Ne devine pas d'id et n'en demande pas au collaborateur : dis-lui seulement que cette écriture n'est pas "
    "encore possible depuis le chat."
)
# Ids qu'aucune fiche de lecture ne donne au modèle (#257) : champ (en
# minuscules) → (élément, routes POST qui le créent). Le modèle recopiait
# l'exemple de la doc ou un autre id, qui existe ailleurs (#254 ne l'arrête
# pas). En attendant le serveur MCP Moduléo (1.8.x), seul un id renvoyé par
# une création confirmée de la Conversation sur l'une de ces routes passe.
IDS_NON_FOURNIS: dict[str, tuple[str, tuple[str, ...]]] = {
    "idtelephone": ("le téléphone", ("moduleo/telephone",)),
    "idemail": ("l'e-mail", ("cogeo/email", "cogeo/elementged/email")),
    "idadresse": ("l'adresse", ("moduleo/adresse",)),
    "idnote": ("la note", ("cogeo/note",)),
    "idtacheafaire": ("la tâche à faire", ("moduleo/tacheafaire",)),
    "iddocument": ("le document", ("cogeo/elementged/document",)),
    "idplan": ("le plan", ("cogeo/elementged/plan",)),
    "idfrais": ("le frais", ("cogeo/frais",)),
    "idrecurrence": ("la récurrence", ("planning/recurrence",)),
    "idarchive": ("l'archive", ("cogeo/archive",)),
    "idlocalisant": ("le localisant", ("cogeo/localisant?idAffaire={idAffaire}",)),
    "idenveloppeprevisionnelle": ("l'enveloppe prévisionnelle", ("cogeo/enveloppe",)),
    "idgroupecontacts": ("le groupe de contacts", ("cogeo/contact/groupecontacts",)),
}
# Clé d'un objet de l'exemple de corps JSON.
_CLE_JSON = re.compile(r'"(\w+)"\s*:')
_ROUTE_CODES_ACTIVITE = "cogeo/codeactivite"
_PROPRIETES_MODIFIEES = "ProprietesModifiees"
_SANS_MOT = "Ne dis jamais que l'écriture est faite : seul le collaborateur la confirme, sur la carte."

logger = logging.getLogger(__name__)


def _routes_ouvertes(contexte: ContexteTour) -> list[RouteEcriture]:
    # Barrière serveur de test et réglage (client), puis routes que le
    # garde des droits peut ouvrir au compte.
    client = contexte.client_moduleo
    if client is None or not client.ecriture_ouverte():
        return []
    return [
        decrite
        for (methode, route), decrite in sorted(ROUTES_ECRITURE.items())
        if ecriture_possible(methode, route, contexte.droits_moduleo)
    ]


def _nom_route(decrite: RouteEcriture) -> str:
    return f"{decrite.methode} {decrite.route}"


# Titre de la carte en langage métier (#256) : la description de la route,
# première phrase de la description de la route, verbe à l'infinitif, sans
# « en fonction de son identifiant unique ».
_VERBES = {
    "Met à jour": "Modifier",
    "Permet de modifier": "Modifier",
    "Modifie": "Modifier",
    "Crée": "Créer",
    "Supprime": "Supprimer",
    "Ajoute": "Ajouter",
    "Enleve": "Enlever",
    "Remplace": "Remplacer",
    "Affecte": "Affecter",
    "Annule": "Annuler",
    "Signe": "Signer",
    "Valide": "Valider",
    "Configure": "Configurer",
}
_SANS_IDENTIFIANT = " en fonction de son identifiant unique"


def _titre(decrite: RouteEcriture) -> str:
    # « Met à jour une tâche à faire en fonction de son identifiant
    # unique. » → « Modifier une tâche à faire ».
    phrase = decrite.description.strip().split(". ", 1)[0]
    titre = phrase.removesuffix(".").replace(_SANS_IDENTIFIANT, "")
    for verbe, infinitif in _VERBES.items():
        if titre.startswith(f"{verbe} "):
            return f"{infinitif}{titre[len(verbe):]}"
    return titre


def _route_connue(nom: Any) -> RouteEcriture | None:
    # « POST moduleo/telephone » → la route du WADL.
    methode, _, route = str(nom or "").strip().partition(" ")
    return ROUTES_ECRITURE.get((methode.upper(), route.strip()))


def _route_ouverte(contexte: ContexteTour, nom: Any) -> RouteEcriture | None:
    # La route, si elle est aussi ouverte au compte.
    decrite = _route_connue(nom)
    return decrite if decrite is not None and decrite in _routes_ouvertes(contexte) else None


_ARGUMENT_ROUTE = {
    "type": "string",
    "description": "Route d'écriture, « MÉTHODE route » telle que listée par ecrire_moduleo (« POST moduleo/telephone »).",
}


def _declarer_decrire(contexte: ContexteTour) -> dict | None:
    if not _routes_ouvertes(contexte):
        return None
    return {
        "type": "function",
        "function": {
            "name": _DECRIRE,
            "description": (
                "Donne les champs attendus par une route d'écriture Moduléo : paramètres de la route, "
                "exemple de corps JSON et description. N'écrit rien dans Moduléo. À appeler avant "
                "ecrire_moduleo pour connaître le corps à envoyer."
            ),
            "parameters": {
                "type": "object",
                "properties": {"route": _ARGUMENT_ROUTE},
                "required": ["route"],
            },
        },
    }


def _executer_decrire(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    nom = arguments.get("route")
    decrite = _route_ouverte(contexte, nom)
    if decrite is None:
        # Route classée mais hors des droits du compte : la phrase du garde
        # nomme le droit manquant (#255).
        connue = _route_connue(nom)
        if connue is not None and _routes_ouvertes(contexte):
            refus = refus_d_ecriture(connue.methode, connue.route, contexte.droits_moduleo)
            if refus is not None:
                logger.info("Garde des droits Moduléo : %s", refus.refus)
                return ResultatOutil(refus.phrase, trace={"route": _nom_route(connue), "garde_des_droits": refus.refus})
        return ResultatOutil(_ROUTE_INCONNUE.format(route=nom or ""))
    parametres = ", ".join(f"{p} ({t})" for p, t in decrite.parametres.items()) or "aucun"
    corps = (
        f"Exemple de corps JSON (valeurs d'exemple à remplacer, champs inutiles à omettre) :\n{decrite.exemple}"
        if decrite.exemple is not None
        else "Pas de corps."
    )
    texte = f"{_nom_route(decrite)} : {decrite.description}\nParamètres : {parametres}\n{corps}"
    # Champs dont l'id ne se retrouve pas par un nom (#254).
    champs = [*decrite.parametres, *_CLE_JSON.findall(decrite.exemple or "")]
    sans_recherche = [c for c in dict.fromkeys(champs) if c.casefold() in IDS_SANS_RECHERCHE_PAR_NOM]
    if sans_recherche:
        texte += "\n" + _SANS_RECHERCHE.format(champs=", ".join(sans_recherche))
    # Champs dont aucune fiche ne donne l'id (#257).
    non_fournis = [c for c in dict.fromkeys(champs) if _non_fourni(decrite, c)]
    lecteur = LecteurTrace(contexte.client_moduleo, contexte.droits_moduleo)
    if "IdCodeActivite" in champs:
        try:
            codes = resoudre_codes_activite(lecteur, lecteur.lire(_ROUTE_CODES_ACTIVITE))
            texte += "\n" + _CODES_ACTIVITE.format(
                codes=", ".join(f"{nom} [id Moduléo {id_code}]" for id_code, nom in codes.items())
            )
        except (DroitManquant, ErreurModuleo, RequeteInterdite, TypeError, ValueError) as erreur:
            # Sans la liste, l'id reste un id qu'aucune fiche ne donne.
            logger.warning("Codes activité Moduléo non lus : %s", erreur)
            non_fournis.append("IdCodeActivite")
    if "IdUtilisateur" in champs and contexte.droits_moduleo.id_utilisateur_moduleo is not None:
        texte += "\n" + _COLLABORATEUR.format(id=contexte.droits_moduleo.id_utilisateur_moduleo)
    if non_fournis:
        texte += "\n" + _NON_FOURNIS.format(champs=", ".join(non_fournis))
    return ResultatOutil(texte, trace={"routes": lecteur.routes} if lecteur.routes else {})


def _non_fourni(decrite: RouteEcriture, champ: str) -> bool:
    # Hors l'id de l'élément qu'un POST crée (IdTelephone de
    # `POST moduleo/telephone`).
    non_fourni = IDS_NON_FOURNIS.get(champ.casefold())
    return non_fourni is not None and not (decrite.methode == "POST" and decrite.route in non_fourni[1])


def _valeurs_d_id(valeur: Any) -> list[str]:
    # Les ids portés par un champ ; vide, 0 ou null : champ omis.
    valeurs = valeur if isinstance(valeur, list) else [valeur]
    return [str(v).strip() for v in valeurs if v not in (None, "", 0, "0") and not isinstance(v, bool)]


def _elements_sans_id(
    decrite: RouteEcriture, parametres: dict[str, Any], corps: Any, renvoyes: set[tuple[str, str]]
) -> list[str]:
    # Éléments désignés par un id qu'aucune fiche ne donne et qu'aucune
    # création confirmée de la Conversation n'a renvoyé (#257).
    champs = [*parametres.items(), *(corps.items() if isinstance(corps, dict) else [])]
    elements: list[str] = []
    for champ, valeur in champs:
        if not _non_fourni(decrite, champ):
            continue
        element, creations = IDS_NON_FOURNIS[champ.casefold()]
        if not all(any((route, v) in renvoyes for route in creations) for v in _valeurs_d_id(valeur)):
            elements.append(element)
    return list(dict.fromkeys(elements))


def _declarer_ecrire(contexte: ContexteTour) -> dict | None:
    routes = _routes_ouvertes(contexte)
    if not routes:
        return None
    liste = "\n".join(f"{_nom_route(decrite)} — {decrite.description}" for decrite in routes)
    return {
        "type": "function",
        "function": {
            "name": _ECRIRE,
            "description": (
                "Propose une écriture dans Moduléo (serveur de test) quand le collaborateur la demande. "
                "N'envoie rien : le collaborateur voit une carte de confirmation et décide lui-même. "
                # #256 : la question en texte avant la carte coûtait un tour.
                "Quand la demande d'écriture est claire, appelle cet outil directement, sans demander "
                "de confirmation en texte : la carte est la confirmation. "
                "Désigne chaque élément par son id lu dans une fiche ([id Moduléo <n>]) ou renvoyé par "
                "une écriture confirmée ; ne devine jamais un id et n'en demande jamais au collaborateur. "
                # Troisième passage de #206 : sans fiche, le modèle doutait et
                # posait une question au lieu de chercher l'élément nommé.
                "Un élément nommé par le collaborateur (contact, affaire, devis, facture, temps passé, "
                "tâche du planning) dont tu n'as pas l'id : lis d'abord sa fiche avec l'outil de lecture "
                "(chercher_contacts_moduleo, chercher_affaires_moduleo…), sans rien demander, puis écris. "
                "Demande d'abord les champs avec decrire_ecriture_moduleo. Une écriture par appel. "
                f"Routes ouvertes :\n{liste}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "route": _ARGUMENT_ROUTE,
                    "parametres": {
                        "type": "object",
                        "description": "Paramètres de la route par nom ({\"idAffaire\": 12}) ; {} si elle n'en a pas.",
                    },
                    "corps": {
                        "type": "object",
                        "description": "Corps JSON de la requête, champs de decrire_ecriture_moduleo.",
                    },
                },
                "required": ["route"],
            },
        },
    }


def _objet(arguments: dict, nom: str, defaut: Any) -> Any:
    # Le modèle envoie parfois un objet en texte JSON.
    valeur = arguments.get(nom, defaut)
    if isinstance(valeur, str):
        try:
            return json.loads(valeur)
        except ValueError:
            raise RequeteInterdite(_JSON_ILLISIBLE.format(nom=nom)) from None
    return valeur


def _avec_l_id_de_la_route(decrite: RouteEcriture, parametres: dict[str, Any], corps: Any) -> Any:
    # Le PUT de Moduléo veut l'id de l'élément aussi dans le corps (« Id »,
    # « IdNote »… de l'exemple) ; le modèle ne le met souvent que dans le
    # paramètre de la route (#260). Absent : rempli ; différent : refusé.
    relecture = RELECTURES.get((decrite.methode, decrite.route))
    if decrite.methode != "PUT" or relecture is None or relecture.source.startswith("corps."):
        return corps
    id_route = parametres.get(relecture.source)
    exemple = json.loads(decrite.exemple) if decrite.exemple is not None else None
    if id_route is None or not isinstance(corps, dict) or not isinstance(exemple, dict):
        return corps
    for champ in exemple:
        if champ.casefold() not in relecture.identites:
            continue
        valeur = corps.get(champ)
        if valeur in (None, "", 0, "0"):
            corps = {**corps, champ: id_route}
        elif str(valeur).strip() != str(id_route).strip():
            raise RequeteInterdite(
                _ID_CONTREDIT.format(champ=champ, valeur=valeur, parametre=relecture.source, id=id_route)
            )
    return corps


def _carte(
    lecteur: LecteurModuleo, droits: DroitsModuleo, decrite: RouteEcriture, parametres: dict[str, Any], corps: Any
) -> tuple[dict | None, Any]:
    # La carte et le corps à envoyer. POST : paramètres et corps en noms.
    # PUT / DELETE (#205) : l'élément visé relu d'abord. Carte None : un PUT
    # qui ne change rien.
    relecture = RELECTURES.get((decrite.methode, decrite.route))
    if relecture is None:
        return {"titre": _titre(decrite), "lignes": lignes_en_noms(lecteur, parametres, corps)}, corps
    element = relire(lecteur, relecture, parametres, corps)
    if decrite.methode == "DELETE":
        fiche, lignes = element_en_noms(lecteur, relecture.route, element, droits, relecture.identites)
        return {"titre": _titre(decrite), "lignes": lignes, "rubrique": SERA_SUPPRIME, "fiche": fiche}, corps
    # PUT : la fiche de l'élément visé, au-dessus des lignes (#253).
    fiche = fiche_en_noms(lecteur, relecture.route, element, droits, relecture.identites)
    if not isinstance(corps, dict):
        # PUT sans corps (émettre un devis…) : ses paramètres, en noms.
        lignes = lignes_en_noms(lecteur, parametres, corps)
        return {"titre": _titre(decrite), "lignes": lignes, "fiche": fiche}, corps
    lignes = differences_en_noms(lecteur, element, corps, relecture.identites)
    if decrite.exemple is not None and _PROPRIETES_MODIFIEES in decrite.exemple:
        # Le PUT de Moduléo remet à vide un champ absent du corps, sauf
        # ceux hors de `ProprietesModifiees` (#251) : seuls ceux de la carte,
        # jamais la liste du modèle.
        corps = {**corps, _PROPRIETES_MODIFIEES: champs_modifies(element, corps, relecture.identites)}
    return ({"titre": _titre(decrite), "lignes": lignes, "fiche": fiche} if lignes else None), corps


def _refuser(
    contexte: ContexteTour,
    methode: str,
    route: str,
    parametres: dict[str, Any],
    corps: Any,
    phrase: str,
    refus: str,
) -> ResultatOutil:
    # Refus du garde des droits : inscrit au journal, sans carte.
    logger.info("Garde des droits Moduléo : %s", refus)
    ecriture = proposer(
        contexte.db,
        contexte.identifiant_compte,
        contexte.conversation_id,
        methode,
        route,
        parametres,
        corps,
        None,
        statut=REFUSEE,
        erreur=phrase,
    )
    return ResultatOutil(
        phrase, trace={"route": f"{methode} {route}", "ecriture_id": ecriture.id, "garde_des_droits": refus}
    )


def _executer_ecrire(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    # Une route connue mais fermée au compte va au garde des droits : sa
    # phrase dit quel droit manque.
    client = contexte.client_moduleo
    nom = arguments.get("route")
    decrite = _route_connue(nom)
    if client is None or decrite is None or not _routes_ouvertes(contexte):
        return ResultatOutil(_ROUTE_INCONNUE.format(route=nom or ""))
    methode, route = decrite.methode, decrite.route
    contexte.publier(consultation_moduleo("préparation de l'écriture"))
    lecteur = LecteurTrace(client, contexte.droits_moduleo)
    parametres: dict[str, Any] = {}
    corps: Any = None
    try:
        lus = _objet(arguments, "parametres", {}) or {}
        if not isinstance(lus, dict):
            raise RequeteInterdite(_JSON_ILLISIBLE.format(nom="parametres"))
        parametres, corps = lus, _objet(arguments, "corps", None)
        corps = _avec_l_id_de_la_route(decrite, parametres, corps)
        client.verifier_ecriture(methode, route, parametres, corps, contexte.droits_moduleo)
    except RequeteInterdite as erreur:
        return ResultatOutil(_NON_PROPOSEE.format(erreur=erreur), trace={"route": f"{methode} {route}"})
    except DroitManquant as refus:
        return _refuser(contexte, methode, route, parametres, corps, refus.phrase, refus.refus)
    except ErreurModuleo as erreur:
        # La relecture d'un élément `siens` (garde des droits) a échoué.
        logger.warning("Moduléo indisponible : %s", erreur)
        return ResultatOutil(INDISPONIBLE, trace={"route": f"{methode} {route}", "erreur": str(erreur)})
    # Un id qu'aucune fiche ne donne (#257) : refusé avant la carte, sans
    # relecture ni journal.
    renvoyes = ids_renvoyes(contexte.db, contexte.conversation_id)
    if elements := _elements_sans_id(decrite, parametres, corps, renvoyes):
        phrase = _PAS_ENCORE_POSSIBLE.format(elements=" ni ".join(elements))
        return ResultatOutil(
            f"{phrase} {_SANS_ID_DEVINE}", trace={"route": f"{methode} {route}", "ids_non_fournis": elements}
        )
    try:
        carte, corps = _carte(lecteur, contexte.droits_moduleo, decrite, parametres, corps)
    except DroitManquant as refus:
        # Le garde refuse la relecture de l'élément visé (#205).
        return _refuser(contexte, methode, route, parametres, corps, _RELECTURE_REFUSEE, refus.refus)
    except ElementIntrouvable:
        return ResultatOutil(_INTROUVABLE, trace={"route": f"{methode} {route}", "routes": lecteur.routes})
    except IdIntrouvable as introuvable:
        # Un id du corps ou des paramètres que Moduléo ne trouve pas (#254).
        return ResultatOutil(
            _ID_INTROUVABLE.format(id=introuvable), trace={"route": f"{methode} {route}", "routes": lecteur.routes}
        )
    except ErreurModuleo as erreur:
        logger.warning("Moduléo indisponible : %s", erreur)
        return ResultatOutil(INDISPONIBLE, trace={"route": f"{methode} {route}", "erreur": str(erreur)})
    if carte is None:
        return ResultatOutil(_SANS_CHANGEMENT, trace={"route": f"{methode} {route}", "routes": lecteur.routes})
    ecriture = proposer(
        contexte.db,
        contexte.identifiant_compte,
        contexte.conversation_id,
        methode,
        route,
        parametres,
        corps,
        carte,
    )
    carte_envoyee = carte_de(ecriture)
    contexte.publier_carte(carte_envoyee)
    contexte.cartes_du_tour.append(ecriture.id)
    return ResultatOutil(
        f"{PROPOSEE} {_SANS_MOT}",
        trace={
            "route": f"{methode} {route}",
            "parametres": parametres,
            "corps": corps,
            "carte": carte_envoyee,
            "routes": lecteur.routes,
        },
    )


OUTIL_DECRIRE = Outil(nom=_DECRIRE, declarer=_declarer_decrire, executer=_executer_decrire)
OUTIL_ECRIRE = Outil(nom=_ECRIRE, declarer=_declarer_ecrire, executer=_executer_ecrire)
