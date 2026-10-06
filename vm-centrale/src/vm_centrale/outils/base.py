from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from vm_centrale.mistral_client import MistralClient, Usage
from vm_centrale.moteur_recherche import MoteurRecherche
from vm_centrale.telechargement_pages import TelechargeurPages


@dataclass(frozen=True)
class ContexteTour:
    # Ce qu'un outil peut lire pour décider de son éligibilité et s'exécuter
    # sur l'appel de chat principal de ce tour. `ids_fenetre` : les messages
    # déjà en base envoyés tels quels au modèle (fenêtre des derniers
    # messages, avant ce tour).
    db: Session
    conversation_id: int
    ids_fenetre: frozenset[int]
    moteur_recherche: MoteurRecherche
    telechargeur_pages: TelechargeurPages
    client_mistral: MistralClient


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
