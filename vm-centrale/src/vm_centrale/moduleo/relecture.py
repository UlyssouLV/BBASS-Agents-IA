from dataclasses import dataclass
from typing import Any

from vm_centrale.moduleo.client import LecteurModuleo, ModuleoIntrouvable
from vm_centrale.moduleo.routes import ROUTES_ECRITURE, ROUTES_GET

# Relecture avant la Carte de confirmation d'un PUT ou d'un DELETE (spec
# 1.5.2, #205) : la route GET qui relit l'élément visé, et d'où vient son
# id (paramètre de la route d'écriture ou champ du corps). La lecture passe
# par le garde des droits comme toute autre. Chaque route PUT / DELETE du
# WADL est ici ; None : aucune lecture ne la relit (route fermée).


class ElementIntrouvable(Exception):
    # 404 de Moduléo, ou route `multi` qui ne rend rien.
    pass


@dataclass(frozen=True)
class Relecture:
    # `route` : gabarit de ROUTES_GET à un seul paramètre, `parametre` ;
    # `source` : nom du paramètre de la route d'écriture, ou « corps.<champ> ».
    route: str
    parametre: str
    source: str

    @property
    def identites(self) -> set[str]:
        # Champs (casse indifférente) qui portent l'id de l'élément lui-même,
        # jamais montrés sur la carte : « Id », « IdTelephone »…
        return {"id", self.parametre.casefold(), self.source.removeprefix("corps.").casefold()}


def _par_id(route: str, source: str) -> Relecture:
    parametre = route[route.index("{") + 1 : route.index("}")]
    return Relecture(route, parametre, source)


_MULTI_TEMPS = "cogeo/tempspasse/multi?ids={ids}"
_MULTI_TACHES = "planning/tacheplanning/multi?ids={ids}"
_MULTI_DEVIS = "cogeo/devis/multi?ids={ids}"

RELECTURES: dict[tuple[str, str], Relecture | None] = {
    ("DELETE", "cogeo/elementged/document/{idDocument}"): _par_id(
        "cogeo/elementged/document/{idDocument}", "idDocument"
    ),
    ("DELETE", "cogeo/elementged/email/{idEmail}"): _par_id("cogeo/elementged/email/{idEmail}", "idEmail"),
    ("DELETE", "cogeo/elementged/plan/{idPlan}"): _par_id("cogeo/elementged/plan/{idPlan}", "idPlan"),
    ("DELETE", "cogeo/email/{idEmail}"): _par_id("cogeo/email/{idEmail}", "idEmail"),
    # Le WADL nomme « idAffaire » l'id de l'enveloppe (« en fonction de son
    # identifiant unique »).
    ("DELETE", "cogeo/enveloppe/{idAffaire}"): _par_id(
        "cogeo/enveloppe/{idEnveloppePrevisionnelle}", "idAffaire"
    ),
    ("DELETE", "cogeo/frais/{IdFrais}"): _par_id("cogeo/frais/{idFrais}", "IdFrais"),
    ("DELETE", "cogeo/note/{idNote}"): _par_id("cogeo/note/{idNote}", "idNote"),
    # Temps passés et tâches : la route `multi`, ouverte aux siens (#191).
    ("DELETE", "cogeo/tempspasse/{idTempsPasse}"): Relecture(_MULTI_TEMPS, "ids", "idTempsPasse"),
    ("DELETE", "fileo/dossier/{idDossier}"): _par_id("fileo/dossier/{idDossier}", "idDossier"),
    ("DELETE", "fileo/fichier/{idFichier}"): _par_id("fileo/fichier/{idFichier}", "idFichier"),
    ("DELETE", "moduleo/adresse/{idAdresse}"): _par_id("moduleo/adresse/{idAdresse}", "idAdresse"),
    ("DELETE", "moduleo/telephone/{idTelephone}"): _par_id("moduleo/telephone/{idTelephone}", "idTelephone"),
    ("DELETE", "planning/recurrence/{idRecurrence}"): _par_id(
        "planning/recurrence/{idRecurrenceGroupeTache}", "idRecurrence"
    ),
    ("DELETE", "planning/tacheplanning/{idTachePlanning}"): Relecture(_MULTI_TACHES, "ids", "idTachePlanning"),
    ("DELETE", "webhook"): None,
    ("PUT", "cogeo/affaire/polygones"): _par_id("cogeo/affaire/{idAffaire}/polygones", "corps.IdAffaire"),
    ("PUT", "cogeo/affaire/{idAffaire}"): _par_id("cogeo/affaire/{idAffaire}", "idAffaire"),
    ("PUT", "cogeo/archive?idArchive={idArchive}&idAffaire={idAffaire}"): _par_id(
        "cogeo/affaire/{idAffaire}", "idAffaire"
    ),
    ("PUT", "cogeo/champspecifique/{idChampSpecifique}"): _par_id(
        "cogeo/champspecifique/{idChampSpecifique}", "idChampSpecifique"
    ),
    ("PUT", "cogeo/contact/collectivite/{idCollectivite}"): _par_id(
        "cogeo/contact/collectivite/{idContact}", "idCollectivite"
    ),
    ("PUT", "cogeo/contact/groupecontacts/{idGroupeContacts}"): _par_id(
        "cogeo/contact/groupecontacts/{idContact}", "idGroupeContacts"
    ),
    ("PUT", "cogeo/contact/personne/{idPersonne}"): _par_id("cogeo/contact/personne/{idContact}", "idPersonne"),
    ("PUT", "cogeo/contact/societe/{idSociete}"): _par_id("cogeo/contact/societe/{idContact}", "idSociete"),
    ("PUT", "cogeo/devis/{idDevis}"): Relecture(_MULTI_DEVIS, "ids", "idDevis"),
    ("PUT", "cogeo/devis/{idDevis}/accepter"): Relecture(_MULTI_DEVIS, "ids", "idDevis"),
    ("PUT", "cogeo/devis/{idDevis}/emettre"): Relecture(_MULTI_DEVIS, "ids", "idDevis"),
    ("PUT", "cogeo/devis/{idDevis}/refuser"): Relecture(_MULTI_DEVIS, "ids", "idDevis"),
    ("PUT", "cogeo/elementged/document"): _par_id("cogeo/elementged/document/{idDocument}", "corps.Id"),
    ("PUT", "cogeo/elementged/email"): _par_id("cogeo/elementged/email/{idEmail}", "corps.Id"),
    ("PUT", "cogeo/elementged/plan"): _par_id("cogeo/elementged/plan/{idPlan}", "corps.Id"),
    ("PUT", "cogeo/email/{idEmail}"): _par_id("cogeo/email/{idEmail}", "idEmail"),
    ("PUT", "cogeo/enveloppe/{idEnveloppePrevisionnelle}"): _par_id(
        "cogeo/enveloppe/{idEnveloppePrevisionnelle}", "idEnveloppePrevisionnelle"
    ),
    ("PUT", "cogeo/frais/{idFrais}"): _par_id("cogeo/frais/{idFrais}", "idFrais"),
    ("PUT", "cogeo/groupe/{idGroupe}"): _par_id("cogeo/groupe/{idGroupe}", "idGroupe"),
    ("PUT", "cogeo/localisant/{idLocalisant}"): _par_id("cogeo/localisant/{idLocalisant}", "idLocalisant"),
    ("PUT", "cogeo/note/{idNote}"): _par_id("cogeo/note/{idNote}", "idNote"),
    ("PUT", "cogeo/tempspasse/{idTempsPasse}"): Relecture(_MULTI_TEMPS, "ids", "idTempsPasse"),
    ("PUT", "cogeo/titre/ajoutparcelle?idTitre={idTitre}&idsParcelle={idsParcelle}"): _par_id(
        "cogeo/titre/{idTitre}", "idTitre"
    ),
    ("PUT", "cogeo/titre/enleverparcelle?idTitre={idTitre}&idsParcelle={idsParcelle}"): _par_id(
        "cogeo/titre/{idTitre}", "idTitre"
    ),
    ("PUT", "cogeo/titre/{idTitre}"): _par_id("cogeo/titre/{idTitre}", "idTitre"),
    # Plusieurs dossiers à la fois, sans route qui les relise ensemble.
    ("PUT", "fileo/dossierproduction?ids={ids}&status={status}"): None,
    ("PUT", "fileo/fichier/{idFichier}"): _par_id("fileo/fichier/{idFichier}", "idFichier"),
    ("PUT", "moduleo/adresse/{idAdresse}"): _par_id("moduleo/adresse/{idAdresse}", "idAdresse"),
    ("PUT", "moduleo/tacheafaire/{idTacheAFaire}"): _par_id("moduleo/tacheafaire/{idTacheAFaire}", "idTacheAFaire"),
    ("PUT", "moduleo/telephone/{idTelephone}"): _par_id("moduleo/telephone/{idTelephone}", "idTelephone"),
    ("PUT", "planning/recurrence/{idRecurrence}"): _par_id(
        "planning/recurrence/{idRecurrenceGroupeTache}", "idRecurrence"
    ),
    ("PUT", "planning/tacheplanning/{idTachePlanning}"): Relecture(_MULTI_TACHES, "ids", "idTachePlanning"),
}


def _verifier_table() -> None:
    # Une route PUT / DELETE ajoutée au WADL sans relecture, ou une lecture
    # absente de ROUTES_GET, fait échouer le chargement.
    attendues = {cle for cle in ROUTES_ECRITURE if cle[0] != "POST"}
    if set(RELECTURES) != attendues:
        raise ValueError(f"relecture.py : routes sans relecture : {sorted(attendues ^ set(RELECTURES))}")
    for relecture in RELECTURES.values():
        if relecture is not None and relecture.route not in ROUTES_GET:
            raise ValueError(f"relecture.py : lecture absente de ROUTES_GET : {relecture.route}")


_verifier_table()


def relire(lecteur: LecteurModuleo, relecture: Relecture, parametres: dict[str, Any], corps: Any) -> dict:
    # L'élément visé, tel que Moduléo le rend. DroitManquant (garde des
    # droits) et ErreurModuleo passent ; un id absent ou un élément
    # introuvable lèvent ElementIntrouvable.
    if relecture.source.startswith("corps."):
        id_element = corps.get(relecture.source.removeprefix("corps.")) if isinstance(corps, dict) else None
    else:
        id_element = parametres.get(relecture.source)
    if id_element in (None, "", 0):
        raise ElementIntrouvable()
    try:
        lu = lecteur.lire(relecture.route, {relecture.parametre: id_element})
    except ModuleoIntrouvable:
        raise ElementIntrouvable() from None
    if isinstance(lu, list):
        lu = lu[0] if lu else None
    if not isinstance(lu, dict):
        raise ElementIntrouvable()
    return lu
