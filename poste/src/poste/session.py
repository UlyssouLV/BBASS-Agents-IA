import json
from dataclasses import dataclass

import keyring

from poste.vm_centrale_client import VmCentraleClient

_SERVICE_NOM = "bbass-agents-ia-poste"
_UTILISATEUR = "session"


@dataclass
class DonneesSessionPersistee:
    identifiant: str
    prenom: str
    nom: str
    jeton: str


class SessionStore:
    # État en mémoire du processus, reflétant (sauf dégradation, voir
    # persistance_degradee) ce qui est persisté via le gestionnaire
    # d'identifiants Windows (keyring) : la session survit à la fermeture de
    # l'appli et à un redémarrage du poste (voir CONTEXT.md, "Session"). Une
    # seule session à la fois, puisqu'un poste n'a qu'un collaborateur
    # connecté. Le mot de passe n'est jamais conservé, ici ni côté keyring.
    def __init__(self) -> None:
        self._identifiant: str | None = None
        self._prenom: str | None = None
        self._nom: str | None = None
        self._jeton: str | None = None
        self._persistance_degradee = False

    @property
    def est_connecte(self) -> bool:
        return self._identifiant is not None

    @property
    def identifiant(self) -> str | None:
        return self._identifiant

    @property
    def prenom(self) -> str | None:
        return self._prenom

    @property
    def nom(self) -> str | None:
        return self._nom

    @property
    def jeton(self) -> str | None:
        return self._jeton

    @property
    def persistance_degradee(self) -> bool:
        return self._persistance_degradee

    def ouvrir(self, identifiant: str, prenom: str, nom: str, jeton: str) -> None:
        self._definir(identifiant, prenom, nom, jeton)
        try:
            keyring.set_password(
                _SERVICE_NOM,
                _UTILISATEUR,
                json.dumps(
                    {"identifiant": identifiant, "prenom": prenom, "nom": nom, "jeton": jeton}
                ),
            )
            self._persistance_degradee = False
        except Exception:
            self._persistance_degradee = True

    def restaurer_verifiee(self, identifiant: str, prenom: str, nom: str, jeton: str) -> None:
        # Utilisé uniquement par verifier_session_au_demarrage : les données
        # sont déjà persistées (elles viennent d'en être lues) et l'identifiant
        # vient de la vérification côté VM, jamais du blob local en l'état où
        # il a été lu. Ne ré-écrit pas le keyring (lecture puis écriture
        # identique à chaque lancement, pure perte).
        self._definir(identifiant, prenom, nom, jeton)

    def _definir(self, identifiant: str, prenom: str, nom: str, jeton: str) -> None:
        self._identifiant = identifiant
        self._prenom = prenom
        self._nom = nom
        self._jeton = jeton

    def fermer(self) -> None:
        self._identifiant = None
        self._prenom = None
        self._nom = None
        self._jeton = None
        try:
            keyring.delete_password(_SERVICE_NOM, _UTILISATEUR)
        except Exception:
            # Couvre aussi bien "rien à supprimer" (déconnexion sans session
            # persistée) qu'un gestionnaire d'identifiants indisponible.
            pass

    def lire_session_persistee(self) -> DonneesSessionPersistee | None:
        try:
            brut = keyring.get_password(_SERVICE_NOM, _UTILISATEUR)
            self._persistance_degradee = False
        except Exception:
            self._persistance_degradee = True
            return None

        if brut is None:
            return None

        try:
            donnees = json.loads(brut)
            return DonneesSessionPersistee(
                identifiant=donnees["identifiant"],
                prenom=donnees["prenom"],
                nom=donnees["nom"],
                jeton=donnees["jeton"],
            )
        except (ValueError, KeyError, TypeError):
            return None


_session_store = SessionStore()


def get_session_store() -> SessionStore:
    return _session_store


def verifier_session_au_demarrage(session: SessionStore, client: VmCentraleClient) -> None:
    # Au lancement de l'appli, un jeton stocké est validé auprès de la VM
    # avant d'afficher l'écran de chat (jamais de vérification périodique en
    # tâche de fond pendant l'usage, voir US #3 / issue #9).
    donnees = session.lire_session_persistee()
    if donnees is None:
        return

    try:
        identifiant_verifie = client.verifier(donnees.jeton)
    except Exception:
        # VM injoignable au lancement : écran de connexion, sans toucher à la
        # session persistée (elle pourra être revalidée au prochain lancement).
        return

    if identifiant_verifie is None:
        session.fermer()
        return

    # L'identifiant vient de la réponse de la VM (source de vérité), jamais
    # du blob local : le jeton stocké est la seule donnée que la VM
    # authentifie réellement ici.
    session.restaurer_verifiee(identifiant_verifie, donnees.prenom, donnees.nom, donnees.jeton)
