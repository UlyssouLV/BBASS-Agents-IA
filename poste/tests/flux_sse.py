import json

# Lecture du flux `text/event-stream` des deux envois d'un message (ADR-0016) :
# des événements `statut`, puis `fin` ou `erreur`.


def evenements(reponse) -> list[tuple[str, dict]]:
    assert reponse.status_code == 200, reponse.text
    assert reponse.headers["content-type"].startswith("text/event-stream")
    resultat = []
    for bloc in reponse.text.split("\n\n"):
        if not bloc.strip():
            continue
        champs = dict(ligne.split(": ", 1) for ligne in bloc.splitlines())
        resultat.append((champs["event"], json.loads(champs["data"])))
    return resultat


def statuts(reponse) -> list[str]:
    return [donnees["libelle"] for nom, donnees in evenements(reponse) if nom == "statut"]


def fin(reponse) -> dict:
    nom, donnees = evenements(reponse)[-1]
    assert nom == "fin", (nom, donnees)
    return donnees


def erreur(reponse) -> dict:
    nom, donnees = evenements(reponse)[-1]
    assert nom == "erreur", (nom, donnees)
    return donnees
