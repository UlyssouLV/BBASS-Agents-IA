import logging
from dataclasses import asdict
from datetime import datetime, timezone

from vm_centrale.models import ResultatRechercheWeb
from vm_centrale.moteur_recherche import MoteurIndisponible, ResultatRecherche
from vm_centrale.outils.base import ContexteTour, Outil, ResultatOutil

_NOM = "rechercher_web"
_NOMBRE_RESULTATS = 5
_RECHERCHE_INDISPONIBLE = (
    "Recherche indisponible : le moteur de recherche ne répond pas. Réponds sans "
    "résultat de recherche et sans lien."
)
_AUCUN_RESULTAT = (
    "Aucun résultat pour cette recherche. Reformule la requête, ou réponds sans "
    "résultat de recherche et sans lien."
)

logger = logging.getLogger(__name__)

# Toujours le même schéma, éligible à chaque appel de chat principal (spec
# 1.4.0, décision n° 3) : c'est le modèle qui décide de chercher.
_SCHEMA = {
    "type": "function",
    "function": {
        "name": _NOM,
        "description": (
            "Cherche sur Internet. À utiliser quand la réponse demande une "
            "information à trouver : une page ou un texte officiel, un texte "
            "réglementaire, une actualité, un classement, une donnée récente. "
            "Renvoie les résultats trouvés (titre, URL, extrait) : seules ces "
            "URL peuvent être citées."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "requete": {
                    "type": "string",
                    "description": (
                        "La recherche, formulée comme dans un moteur de "
                        "recherche : mots-clés précis, sans phrase de politesse. "
                        "Seule cette chaîne part vers le moteur."
                    ),
                },
                "besoin": {
                    "type": "string",
                    "description": (
                        "Ce qu'on cherche et pourquoi, en une ou deux phrases, "
                        "pour savoir quoi retenir des pages trouvées."
                    ),
                },
            },
            "required": ["requete", "besoin"],
        },
    },
}


def _declarer(contexte: ContexteTour) -> dict:
    return _SCHEMA


def _contenu_pour_le_modele(requete: str, resultats: list[ResultatRecherche]) -> str:
    lignes = [f"Résultats de la recherche « {requete} » :"]
    for numero, resultat in enumerate(resultats, start=1):
        lignes.append(f"{numero}. {resultat.titre}\n   URL : {resultat.url}\n   Extrait : {resultat.extrait}")
    return "\n".join(lignes)


def _executer(arguments: dict, contexte: ContexteTour) -> ResultatOutil:
    # `besoin` ne part jamais vers le moteur (ADR-0013) : il servira à
    # l'appel d'extraction.
    requete = str(arguments.get("requete") or "").strip()
    if not requete:
        return ResultatOutil(_AUCUN_RESULTAT, trace={"resultats": []})
    try:
        resultats = contexte.moteur_recherche.rechercher(requete)[:_NOMBRE_RESULTATS]
    except MoteurIndisponible as erreur:
        # Jamais de 500 (spec 1.4.0, décision n° 17) : le modèle lit la panne
        # dans le message `tool` et répond sans recherche.
        logger.warning("Moteur de recherche indisponible : %s", erreur)
        return ResultatOutil(_RECHERCHE_INDISPONIBLE, trace={"erreur": str(erreur)})
    if not resultats:
        return ResultatOutil(_AUCUN_RESULTAT, trace={"resultats": []})

    maintenant = datetime.now(timezone.utc)
    contexte.db.add_all(
        ResultatRechercheWeb(
            conversation_id=contexte.conversation_id,
            requete=requete,
            url=resultat.url,
            titre=resultat.titre,
            extrait_moteur=resultat.extrait,
            texte_nettoye="",
            date_creation=maintenant,
        )
        for resultat in resultats
    )
    # Flush (jamais commit) : les garde-fous du même tour relisent ces URL en
    # base, et un tour qui échoue plus loin les annule avec le reste.
    contexte.db.flush()
    return ResultatOutil(
        _contenu_pour_le_modele(requete, resultats),
        trace={"resultats": [asdict(resultat) for resultat in resultats]},
    )


OUTIL = Outil(nom=_NOM, declarer=_declarer, executer=_executer)
