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
    agence: str
    poles: list[str]
    est_admin: bool
    doit_changer_mot_de_passe: bool


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
        self._agence: str | None = None
        self._poles: list[str] | None = None
        self._est_admin: bool | None = None
        self._doit_changer_mot_de_passe: bool | None = None
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
    def agence(self) -> str | None:
        return self._agence

    @property
    def poles(self) -> list[str] | None:
        return self._poles

    @property
    def est_admin(self) -> bool | None:
        return self._est_admin

    @property
    def doit_changer_mot_de_passe(self) -> bool | None:
        return self._doit_changer_mot_de_passe

    @property
    def persistance_degradee(self) -> bool:
        return self._persistance_degradee

    def ouvrir(
        self,
        identifiant: str,
        prenom: str,
        nom: str,
        jeton: str,
        agence: str,
        poles: list[str],
        est_admin: bool,
        doit_changer_mot_de_passe: bool,
    ) -> None:
        self._definir(identifiant, prenom, nom, jeton, agence, poles, est_admin, doit_changer_mot_de_passe)
        try:
            keyring.set_password(
                _SERVICE_NOM,
                _UTILISATEUR,
                json.dumps(
                    {
                        "identifiant": identifiant,
                        "prenom": prenom,
                        "nom": nom,
                        "jeton": jeton,
                        "agence": agence,
                        "poles": poles,
                        "est_admin": est_admin,
                        "doit_changer_mot_de_passe": doit_changer_mot_de_passe,
                    }
                ),
            )
            self._persistance_degradee = False
        except Exception:
            self._persistance_degradee = True

    def restaurer_verifiee(
        self,
        identifiant: str,
        est_admin: bool,
        prenom: str,
        nom: str,
        jeton: str,
        agence: str,
        poles: list[str],
        doit_changer_mot_de_passe: bool,
    ) -> None:
        # Utilisé uniquement par verifier_session_au_demarrage : identifiant et
        # est_admin viennent de la vérification côté VM (source de vérité,
        # jamais mis en cache au-delà de cette vérification), tandis que
        # prenom/nom/agence/poles/doit_changer_mot_de_passe viennent du blob
        # local déjà persisté. Ne ré-écrit pas le keyring (lecture puis
        # écriture identique à chaque lancement, pure perte).
        self._definir(identifiant, prenom, nom, jeton, agence, poles, est_admin, doit_changer_mot_de_passe)

    def _definir(
        self,
        identifiant: str,
        prenom: str,
        nom: str,
        jeton: str,
        agence: str,
        poles: list[str],
        est_admin: bool,
        doit_changer_mot_de_passe: bool,
    ) -> None:
        self._identifiant = identifiant
        self._prenom = prenom
        self._nom = nom
        self._jeton = jeton
        self._agence = agence
        self._poles = poles
        self._est_admin = est_admin
        self._doit_changer_mot_de_passe = doit_changer_mot_de_passe

    def fermer(self) -> None:
        self._identifiant = None
        self._prenom = None
        self._nom = None
        self._jeton = None
        self._agence = None
        self._poles = None
        self._est_admin = None
        self._doit_changer_mot_de_passe = None
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
                agence=donnees["agence"],
                poles=donnees["poles"],
                est_admin=donnees["est_admin"],
                doit_changer_mot_de_passe=donnees["doit_changer_mot_de_passe"],
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
        verification = client.verifier(donnees.jeton)
    except Exception:
        # VM injoignable au lancement : écran de connexion, sans toucher à la
        # session persistée (elle pourra être revalidée au prochain lancement).
        return

    if verification is None:
        session.fermer()
        return

    # identifiant et est_admin viennent de la réponse de la VM (source de
    # vérité, jamais du blob local) : est_admin n'est jamais mis en cache
    # au-delà de cette vérification, contrairement à prenom/nom/agence/poles
    # /doit_changer_mot_de_passe qui restent lus du cache local comme
    # aujourd'hui.
    session.restaurer_verifiee(
        identifiant=verification.identifiant,
        est_admin=verification.est_admin,
        prenom=donnees.prenom,
        nom=donnees.nom,
        jeton=donnees.jeton,
        agence=donnees.agence,
        poles=donnees.poles,
        doit_changer_mot_de_passe=donnees.doit_changer_mot_de_passe,
    )
