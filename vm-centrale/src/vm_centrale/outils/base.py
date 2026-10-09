from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from vm_centrale.mistral_client import MistralClient, Usage
from vm_centrale.moduleo.client import LecteurModuleo
from vm_centrale.moduleo.droits import AUCUN_DROIT, DroitsModuleo
from vm_centrale.moteur_recherche import MoteurRecherche
from vm_centrale.statut_tour import Publier, ne_rien_publier
from vm_centrale.telechargement_pages import TelechargeurPages


@dataclass(frozen=True)
class ContexteTour:
    # Ce qu'un outil peut lire pour décider de son éligibilité et s'exécuter
    # sur l'appel de chat principal de ce tour.
    db: Session
    conversation_id: int
    moteur_recherche: MoteurRecherche
    telechargeur_pages: TelechargeurPages
    client_mistral: MistralClient
    # Pas encore en base pendant le tour : une URL qu'il contient est déjà
    # lisible par lire_pages_web (#140).
    message_du_tour: str
    # URL normalisée → URL des pages que lire_pages_web a jugées trop
    # longues pendant ce tour (#151) : refusées à tout appel suivant du
    # tour, et mentionnées par le garde-fou à la fin de la réponse visible.
    pages_trop_longues: dict[str, str] = field(default_factory=dict)
    # Lignes `resultats_recherche_web` sans texte que lire_pages_web a
    # retentées pendant ce tour (#156) : un seul essai par tour, même en
    # échec.
    pages_retentees: set[int] = field(default_factory=set)
    # URL normalisées que lire_pages_web a retéléchargées de force pendant
    # ce tour (`retelecharger`, #157) : une seule fois par URL et par tour,
    # un appel suivant sert la copie actuelle.
    pages_relues_de_force: set[str] = field(default_factory=set)
    # Statut du tour (spec 1.4.4) : l'étape en cours, affichée par le poste.
    publier: Publier = ne_rien_publier
    # None sans config Moduléo (spec 1.5.0, #173) : les outils Moduléo ne
    # sont alors pas proposés.
    client_moduleo: LecteurModuleo | None = None
    # Droits Moduléo du compte, lus une fois pour le tour (spec 1.5.1) ;
    # sans rattachement, aucun outil Moduléo n'est proposé.
    droits_moduleo: DroitsModuleo = AUCUN_DROIT
    # Noms des outils appelés pendant ce tour, dans l'ordre (#182) : après
    # un appel Moduléo, la phrase fixe parle de Moduléo.
    outils_appeles: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AppelMistralOutil:
    # Un appel Mistral fait par l'outil lui-même (ex. l'appel d'extraction de
    # rechercher_web, spec 1.4.0). La boucle l'enregistre (Consommation et
    # inspecteur) après l'échange local de l'outil, pour l'ordre
    # chronologique. `usage` à None : l'appel a échoué, `erreur` dit
    # pourquoi.
    type_appel: str
    modele: str
    requete_payload: dict
    reponse_payload: dict | None
    usage: Usage | None
    erreur: str | None = None


@dataclass(frozen=True)
class ResultatOutil:
    # `contenu` part au modèle dans le message `tool`. `piece_jointe_id` :
    # la pièce jointe relue par l'outil, s'il y en a une, pour l'échange
    # d'inspecteur de l'appel suivant (spec 1.3.0). `trace` : ce que l'outil
    # a fait en plus (ex. résultats bruts du moteur), ajouté à la réponse de
    # son échange local d'inspecteur, jamais envoyé au modèle.
    contenu: str
    piece_jointe_id: int | None = None
    trace: dict = field(default_factory=dict)
    appels_mistral: tuple[AppelMistralOutil, ...] = ()


@dataclass(frozen=True)
class Outil:
    nom: str
    # Schéma `tools` de l'outil pour ce tour, ou None s'il n'est pas éligible
    # (éligibilité et schéma calculés ensemble : la description peut dépendre
    # de ce qui rend l'outil éligible).
    declarer: Callable[[ContexteTour], dict | None]
    executer: Callable[[dict, ContexteTour], ResultatOutil]
