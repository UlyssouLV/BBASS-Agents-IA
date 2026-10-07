# Une page trop longue pour lire_pages_web n'est pas transmise au modèle, qui
# reçoit la consigne de le dire au collaborateur. Il a pourtant résumé de
# mémoire un roman présenté comme lu (#151, conversation 100) : ce
# garde-fou prévient le collaborateur quelle que soit la réponse.


def mentionner_pages_trop_longues(reponse: str, urls: list[str]) -> str:
    if not urls:
        return reponse
    mentions = "\n".join(f"La page {url} était trop longue pour être lue en entier." for url in urls)
    return f"{reponse.rstrip()}\n\n{mentions}"
