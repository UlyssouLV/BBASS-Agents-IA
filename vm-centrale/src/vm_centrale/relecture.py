import logging

from vm_centrale.mistral_client import MistralClient, ReponseChat

TYPE_APPEL = "relecture"
# Consigne fixe de la relecture isolée (spec 1.6.3, point 9, ADR-0023) :
# elle ne reçoit que la question, la réponse marquée et ce que les outils
# ont ramené, jamais l'historique, le profil ni le résumé glissant (même
# cadre que l'appel d'extraction, ADR-0014). Appel sans outils.
CONSIGNE_RELECTURE = (
    "Tu relis une réponse dont certaines informations, introuvables dans les "
    "sources, ont été remplacées par « [non trouvé] ». Réécris-la pour le "
    "collaborateur en ne gardant que ce que les résultats d'outils et la pièce "
    "jointe ci-dessous contiennent. Dis clairement ce qui n'a pas été trouvé et "
    "où on a cherché, sans jamais recopier « [non trouvé] ». N'ajoute aucun chiffre, aucune source, aucun lien ni "
    "aucun fait qui ne soit pas écrit dans ces résultats. Garde la mise en "
    "forme Markdown utile (listes, tableaux). Réponds seulement par la "
    "réponse réécrite."
)

logger = logging.getLogger(__name__)


def _entree(question: str, reponse_marquee: str, resultats_outils: list[str], piece_jointe: str | None) -> str:
    resultats = "\n\n".join(resultats_outils) or "(aucun outil appelé)"
    blocs = [
        f"Question du collaborateur :\n{question}",
        f"Réponse à relire :\n{reponse_marquee}",
        f"Résultats des outils :\n{resultats}",
    ]
    if piece_jointe:
        blocs.append(f"Pièce jointe du message :\n{piece_jointe}")
    return "\n\n".join(blocs)


def relire(
    client: MistralClient,
    question: str,
    reponse_marquee: str,
    resultats_outils: list[str],
    piece_jointe: str | None,
) -> ReponseChat | Exception:
    # Jamais levée : un appel en échec rend son erreur, et la réponse
    # marquée reste.
    messages = [
        {"role": "system", "content": CONSIGNE_RELECTURE},
        {"role": "user", "content": _entree(question, reponse_marquee, resultats_outils, piece_jointe)},
    ]
    try:
        return client.chat(messages)
    except Exception as erreur:
        logger.warning("Relecture en échec : %s", erreur)
        return erreur
