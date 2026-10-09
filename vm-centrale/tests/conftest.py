import json
import threading
from contextlib import contextmanager

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from faux_moduleo import FauxModuleo

from vm_centrale.database import Base, get_db, get_fabrique_session
from vm_centrale.main import app
from vm_centrale.mistral_client import (
    AppelOutil,
    AppelOutilDemande,
    ErreurAppelMistral,
    ReponseChat,
    ReponseOcr,
    Usage,
    get_mistral_client,
)
from vm_centrale.models import Compte, ComptePole
from vm_centrale.moduleo.client import get_client_moduleo
from vm_centrale.moduleo.droits import GROUPE_DEV, charger_catalogue, creer_groupes_dev, rattacher
from vm_centrale.moteur_recherche import MoteurIndisponible, ResultatRecherche, get_moteur_recherche
from vm_centrale.outils.lire_pages_web import CONSIGNE_LECTURE_PAGE, CONSIGNE_REVERIFICATION_PAGE
from vm_centrale.outils.piece_jointe import CONSIGNE_RELECTURE_PIECES_JOINTES
from vm_centrale.outils.recherche_web import CONSIGNE_EXTRACTION
from vm_centrale.questions_couvertes import CONSIGNE_QUESTIONS_PIECE_JOINTE
from vm_centrale.security import hash_password
from vm_centrale.telechargement_pages import PageIndisponible, PageTelechargee, get_telechargeur_pages
from vm_centrale.jetons import JetonStore, get_jeton_store


@pytest.fixture(autouse=True)
def _concurrence_reinitialisee():
    # cache_idempotence et verrous_comptes sont des singletons module-level
    # (partagés par toutes les requêtes d'un même process VM centrale, voir
    # vm_centrale.concurrence), donc aussi partagés par tous les tests d'une
    # même session pytest sans ce reset : une clé d'idempotence réutilisée
    # par deux tests différents renverrait sinon la réponse mise en cache par
    # le premier test au second.
    from vm_centrale.concurrence import cache_idempotence, verrous_comptes

    cache_idempotence._entrees.clear()
    verrous_comptes._verrous.clear()


@pytest.fixture(autouse=True)
def _sans_init_db_reel(monkeypatch):
    # Le lifespan de l'app appelle `init_db()` sur l'engine réel (lié à
    # VM_CENTRALE_DATABASE_URL), en dehors du système de dependency_overrides
    # utilisé pour `get_db`. Sans ce patch, tout `TestClient(app)` exigerait
    # un PostgreSQL local démarré, alors que les tests tournent sur SQLite en
    # mémoire (fixture `db_session`) et ne doivent dépendre d'aucun service
    # externe.
    monkeypatch.setattr("vm_centrale.main.init_db", lambda: None)


# Clé Mistral de tous les tests (spec 1.5.1, #186) : chiffrée avec une clé
# maître temporaire, comme en production, faute de quoi la VM refuse de
# démarrer. Le .env de vm-centrale/ (load_dotenv dans config.py) ne doit pas
# fuiter ici : MISTRAL_API_KEY en clair est retirée.
CLE_API_MISTRAL_DE_TEST = "cle-api-mistral-de-test-0123456789"


@pytest.fixture(autouse=True)
def _cle_mistral_chiffree(monkeypatch, tmp_path_factory):
    cle_maitre = Fernet.generate_key()
    fichier_cle_maitre = tmp_path_factory.mktemp("cle_maitre") / "cle_maitre.key"
    fichier_cle_maitre.write_bytes(cle_maitre)
    monkeypatch.setenv("VM_CLE_MAITRE_FICHIER", str(fichier_cle_maitre))
    monkeypatch.setenv(
        "MISTRAL_API_KEY_CHIFFREE", Fernet(cle_maitre).encrypt(CLE_API_MISTRAL_DE_TEST.encode()).decode()
    )
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)


# Usage/pages_processed factices (spec 1.1.3) : ce double ne sert encore
# qu'à vérifier que le contrat MistralClient.chat()/.ocr() (ReponseChat/
# ReponseOcr) est bien celui consommé par les appelants — aucun test ne
# vérifie encore ces valeurs (ticket #53, la persistance Consommation
# viendra avec le ticket suivant).
_USAGE_FACTICE = Usage(tokens_entree=10, tokens_sortie=5, tokens_total=15)
_PAGES_PROCESSED_FACTICE = 1
_EXTRAIT_FACTICE = json.dumps({"faits": [], "questions_couvertes": []})
_QUESTIONS_PIECE_JOINTE_FACTICES = json.dumps({"questions_couvertes": []})
_LECTURE_PAGE_FACTICE = json.dumps({"trouvee": False, "reponse": "", "source": ""})
# Hors du JSON attendu (aucune question pour des questions envoyées) : sans
# réponse configurée, une revérification supprime les questions de la page.
_REVERIFICATION_PAGE_FACTICE = json.dumps({"questions": []})


class ClientMistralFactice:
    # Le routeur envoyer_message lance désormais l'appel de réponse et
    # l'appel résumé+profil en parallèle (vrais threads, cf.
    # vm_centrale.routers.conversations.envoyer_message) : ce double doit
    # donc être thread-safe (verrou) et distinguer les deux types d'appel
    # par response_format plutôt que par ordre d'arrivée, qui n'est plus
    # déterministe entre deux appels concurrents.
    def __init__(self) -> None:
        self.messages_recus: list = []
        self.response_formats_recus: list = []
        # Prompts reçus par type d'appel, dans l'ordre — utiliser ces listes
        # plutôt que messages_recus/response_formats_recus pour retrouver
        # « le dernier appel de réponse de chat » ou « le dernier appel
        # résumé+profil », dont l'ordre d'arrivée relatif n'est pas garanti.
        self.appels_reponse: list = []
        self.appels_structures: list = []
        # `tools` reçu par chaque appel de réponse de chat, même ordre et
        # même longueur que appels_reponse (spec 1.1.2, tool calling) — une
        # entrée par appel, y compris le second appel (tools=None) d'un
        # aller-retour d'outil.
        self.tools_appels_reponse: list = []
        self._verrou = threading.Lock()
        self._reponses: list[str] = []
        self._reponse_structuree: str | None = None
        self._exception: Exception | None = None
        # Appels .ocr() reçus : (document, type_mime), distincts de
        # messages_recus (appels .chat()) — voir televerser_piece_jointe.
        self.appels_ocr: list[tuple[bytes, str]] = []
        self._reponse_ocr = ""
        self._exception_ocr: Exception | None = None
        # File des demandes d'outils (spec 1.4.0) : chaque entrée est la
        # liste des appels d'une réponse, consommée par le prochain appel
        # .chat() portant `tools`.
        self._demandes_outils: list[list[AppelOutil]] = []
        self._echec_apres_demandes_outils: Exception | None = None
        # Appels d'extraction de rechercher_web (spec 1.4.0, ADR-0014),
        # reconnus à leur consigne fixe : leur propre canal, pour ne pas
        # consommer la file `_reponses` du chat principal.
        self.appels_extraction: list = []
        self._reponse_extraction = _EXTRAIT_FACTICE
        self._exception_extraction: Exception | None = None
        # Appels de questions couvertes d'une pièce jointe (spec 1.4.1),
        # reconnus à leur consigne fixe comme l'extraction, et lancés en
        # parallèle de la réponse de chat.
        self.appels_questions_piece_jointe: list = []
        self._reponse_questions_piece_jointe = _QUESTIONS_PIECE_JOINTE_FACTICES
        self._exception_questions_piece_jointe: Exception | None = None
        # Appels d'extraction de lire_pages_web (spec 1.4.1), une page par
        # appel, reconnus à leur consigne fixe.
        self.appels_lecture_page: list = []
        self._reponse_lecture_page = _LECTURE_PAGE_FACTICE
        self._exception_lecture_page: Exception | None = None
        # Appels de revérification des questions couvertes d'une page relue
        # de force (spec 1.4.3, #158), reconnus à leur consigne fixe.
        self.appels_reverification_page: list = []
        self._reponse_reverification_page = _REVERIFICATION_PAGE_FACTICE
        self._exception_reverification_page: Exception | None = None
        # Appels d'extraction de relire_pieces_jointes avec un besoin (spec
        # 1.4.1, #141), reconnus à leur consigne fixe.
        self.appels_relecture_pieces_jointes: list = []
        self._reponse_relecture_pieces_jointes = _LECTURE_PAGE_FACTICE
        self._exception_relecture_pieces_jointes: Exception | None = None
        # prompt_tokens des prochains appels de chat principaux (spec 1.4.2,
        # jauge de contexte), consommés dans l'ordre ; sans valeur, l'usage
        # factice habituel.
        self._prompt_tokens_principaux: list[int] = []

    def repondre_ocr(self, texte: str) -> None:
        self._reponse_ocr = texte
        self._exception_ocr = None

    def echouer_ocr(self, exception: Exception) -> None:
        self._exception_ocr = exception

    def repondre_vision(self, contenu_extrait: str, echec_analyse: bool = False) -> None:
        # Même canal que resume_et_profil ci-dessous (appel .chat() avec
        # response_format) : l'analyse d'image (vm_centrale.
        # analyse_pieces_jointes.image) est une sortie structurée au même
        # titre, distinguée par son schéma plutôt que par un mécanisme dédié.
        self._reponse_structuree = json.dumps(
            {"contenu_extrait": contenu_extrait, "echec_analyse": echec_analyse}
        )
        self._exception = None

    def ocr(self, document: bytes, type_mime: str) -> ReponseOcr:
        with self._verrou:
            self.appels_ocr.append((document, type_mime))
            # payload_envoye/reponse_brute factices (spec 1.3.0) : comme pour
            # Usage ci-dessus, juste assez pour que le contrat
            # MistralClient.ocr() (ReponseOcr) soit bien celui consommé par
            # les appelants (vm_centrale.inspecteur), pas une reproduction
            # fidèle du vrai payload base64 construit par MistralClient.
            payload = {"model": "mistral-ocr-factice", "document": {"type": "document_url"}}
            if self._exception_ocr is not None:
                raise ErreurAppelMistral(
                    str(self._exception_ocr), payload_envoye=payload
                ) from self._exception_ocr
            return ReponseOcr(
                contenu=self._reponse_ocr,
                pages_processed=_PAGES_PROCESSED_FACTICE,
                payload_envoye=payload,
                reponse_brute={
                    "pages": [{"markdown": self._reponse_ocr}],
                    "usage_info": {"pages_processed": _PAGES_PROCESSED_FACTICE},
                },
            )

    def repondre(self, *reponses: str, resume_et_profil: str | None = None) -> None:
        # `reponses` : file pour les appels sans response_format (réponse de
        # chat, titrage) — un appel consomme la réponse suivante, sauf s'il
        # n'en reste qu'une, alors répétée indéfiniment (cas d'usage
        # historique à un seul `client.chat` par requête, ex. `/relais`).
        # `resume_et_profil` : réponse dédiée à l'appel structuré
        # (response_format non None), indépendante de cette file puisque cet
        # appel peut s'exécuter en parallèle du premier.
        self._reponses = list(reponses)
        self._reponse_structuree = resume_et_profil
        self._exception = None

    def echouer(self, exception: Exception) -> None:
        self._exception = exception

    def fixer_prompt_tokens_principaux(self, *valeurs: int) -> None:
        self._prompt_tokens_principaux = list(valeurs)

    def _usage_principal(self, messages) -> Usage:
        # Un appel principal reçoit une liste de messages ; le titrage, une
        # chaîne.
        if isinstance(messages, str) or not self._prompt_tokens_principaux:
            return _USAGE_FACTICE
        tokens_entree = self._prompt_tokens_principaux.pop(0)
        return Usage(tokens_entree=tokens_entree, tokens_sortie=5, tokens_total=tokens_entree + 5)

    def repondre_avec_appel_outil(
        self, nom_outil: str, arguments: dict, tool_call_id: str = "call_1"
    ) -> None:
        # Consommé une seule fois par le prochain appel .chat() portant
        # `tools` (spec 1.1.2) : l'appel suivant retombe sur la file
        # `_reponses` normale, configurée via repondre() comme d'habitude.
        self.repondre_avec_appels_outils([(nom_outil, arguments, tool_call_id)])

    def repondre_avec_appels_outils(self, *demandes: list[tuple[str, dict, str]]) -> None:
        # Spec 1.4.0 : chaque argument est une réponse du modèle qui demande
        # un ou plusieurs outils à la fois ((nom, arguments, tool_call_id)),
        # consommée dans l'ordre par les appels .chat() portant `tools`.
        self._demandes_outils.extend(
            [AppelOutil(id=id_appel, nom=nom, arguments=arguments) for nom, arguments, id_appel in demande]
            for demande in demandes
        )

    def repondre_extraction(
        self, faits: list[tuple[str, str]] = (), questions: list[tuple[str, str, str]] = ()
    ) -> None:
        # Sortie JSON de l'appel d'extraction : les faits (texte, source ;
        # spec 1.4.3, #160) et les questions couvertes (question, réponse,
        # source ; spec 1.4.1).
        self.repondre_extraction_brute(
            json.dumps(
                {
                    "faits": [{"texte": texte, "source": source} for texte, source in faits],
                    "questions_couvertes": [
                        {"question": question, "reponse": reponse, "source": source}
                        for question, reponse, source in questions
                    ],
                },
                ensure_ascii=False,
            )
        )

    def repondre_extraction_brute(self, texte: str) -> None:
        self._reponse_extraction = texte
        self._exception_extraction = None

    def repondre_questions_piece_jointe(self, questions: list[tuple[str, str]]) -> None:
        # (question, réponse) par question couverte.
        self.repondre_questions_piece_jointe_brute(
            json.dumps(
                {"questions_couvertes": [{"question": q, "reponse": r} for q, r in questions]},
                ensure_ascii=False,
            )
        )

    def repondre_questions_piece_jointe_brute(self, texte: str) -> None:
        self._reponse_questions_piece_jointe = texte
        self._exception_questions_piece_jointe = None

    def echouer_questions_piece_jointe(self, exception: Exception) -> None:
        self._exception_questions_piece_jointe = exception

    def repondre_lecture_page(self, trouvee: bool, reponse: str = "", source: str = "") -> None:
        self.repondre_lecture_page_brute(
            json.dumps({"trouvee": trouvee, "reponse": reponse, "source": source}, ensure_ascii=False)
        )

    def repondre_lecture_page_brute(self, texte: str) -> None:
        self._reponse_lecture_page = texte
        self._exception_lecture_page = None

    def echouer_lecture_page(self, exception: Exception) -> None:
        self._exception_lecture_page = exception

    def repondre_reverification_page(
        self, questions: list[tuple[bool, str]], besoin: tuple[bool, str] | None = None
    ) -> None:
        # (trouvee, réponse) par ancienne question, dans l'ordre envoyé.
        donnees: dict = {"questions": [{"trouvee": t, "reponse": r} for t, r in questions]}
        if besoin is not None:
            donnees["besoin"] = {"trouvee": besoin[0], "reponse": besoin[1]}
        self.repondre_reverification_page_brute(json.dumps(donnees, ensure_ascii=False))

    def repondre_reverification_page_brute(self, texte: str) -> None:
        self._reponse_reverification_page = texte
        self._exception_reverification_page = None

    def echouer_reverification_page(self, exception: Exception) -> None:
        self._exception_reverification_page = exception

    def repondre_relecture_pieces_jointes(self, trouvee: bool, reponse: str = "", source: str = "") -> None:
        self.repondre_relecture_pieces_jointes_brute(
            json.dumps({"trouvee": trouvee, "reponse": reponse, "source": source}, ensure_ascii=False)
        )

    def repondre_relecture_pieces_jointes_brute(self, texte: str) -> None:
        self._reponse_relecture_pieces_jointes = texte
        self._exception_relecture_pieces_jointes = None

    def echouer_relecture_pieces_jointes(self, exception: Exception) -> None:
        self._exception_relecture_pieces_jointes = exception

    def echouer_extraction(self, exception: Exception) -> None:
        self._exception_extraction = exception

    def echouer_apres_demandes_outils(self, exception: Exception) -> None:
        # L'appel de réponse qui suit la dernière demande d'outil en file
        # échoue (rollback d'un tour, spec 1.4.0).
        self._echec_apres_demandes_outils = exception

    def _extraire(self, messages, response_format) -> ReponseChat:
        self.appels_extraction.append(messages)
        return self._repondre_canal(
            messages, response_format, self._reponse_extraction, self._exception_extraction
        )

    def _questions_piece_jointe(self, messages, response_format) -> ReponseChat:
        self.appels_questions_piece_jointe.append(messages)
        return self._repondre_canal(
            messages,
            response_format,
            self._reponse_questions_piece_jointe,
            self._exception_questions_piece_jointe,
        )

    def _lire_page(self, messages, response_format) -> ReponseChat:
        self.appels_lecture_page.append(messages)
        return self._repondre_canal(
            messages, response_format, self._reponse_lecture_page, self._exception_lecture_page
        )

    def _reverifier_page(self, messages, response_format) -> ReponseChat:
        self.appels_reverification_page.append(messages)
        return self._repondre_canal(
            messages, response_format, self._reponse_reverification_page, self._exception_reverification_page
        )

    def _relire_pieces_jointes(self, messages, response_format) -> ReponseChat:
        self.appels_relecture_pieces_jointes.append(messages)
        return self._repondre_canal(
            messages,
            response_format,
            self._reponse_relecture_pieces_jointes,
            self._exception_relecture_pieces_jointes,
        )

    @staticmethod
    def _repondre_canal(messages, response_format, contenu: str, exception: Exception | None) -> ReponseChat:
        payload = {"model": "mistral-factice", "messages": messages, "response_format": response_format}
        if exception is not None:
            raise ErreurAppelMistral(str(exception), payload_envoye=payload) from exception
        return ReponseChat(
            contenu=contenu,
            usage=_USAGE_FACTICE,
            payload_envoye=payload,
            reponse_brute={"choices": [{"message": {"content": contenu}}]},
        )

    def chat(self, messages, response_format=None, tools=None) -> ReponseChat:
        with self._verrou:
            if not isinstance(messages, str) and messages and messages[0]["content"] == CONSIGNE_EXTRACTION:
                return self._extraire(messages, response_format)
            if (
                not isinstance(messages, str)
                and messages
                and messages[0]["content"] == CONSIGNE_QUESTIONS_PIECE_JOINTE
            ):
                return self._questions_piece_jointe(messages, response_format)
            if not isinstance(messages, str) and messages and messages[0]["content"] == CONSIGNE_LECTURE_PAGE:
                return self._lire_page(messages, response_format)
            if (
                not isinstance(messages, str)
                and messages
                and messages[0]["content"] == CONSIGNE_REVERIFICATION_PAGE
            ):
                return self._reverifier_page(messages, response_format)
            if (
                not isinstance(messages, str)
                and messages
                and messages[0]["content"] == CONSIGNE_RELECTURE_PIECES_JOINTES
            ):
                return self._relire_pieces_jointes(messages, response_format)
            self.messages_recus.append(messages)
            self.response_formats_recus.append(response_format)
            if response_format is not None:
                self.appels_structures.append(messages)
            else:
                self.appels_reponse.append(messages)
                self.tools_appels_reponse.append(tools)

            # payload_envoye factice (spec 1.3.0) : reprend la forme réelle du
            # payload MistralClient (model/messages/response_format/tools),
            # suffisant pour que les appelants (vm_centrale.inspecteur) aient
            # quelque chose à persister, sans reproduire le modèle réel.
            # Normalisation str -> liste de messages comme le vrai
            # MistralClient.chat() (titrage/résumé+profil l'appellent avec une
            # simple chaîne) : messages_recus/appels_reponse ci-dessus gardent
            # eux la valeur brute reçue, pour ne pas casser les assertions
            # existantes qui testent dessus par inclusion de sous-chaîne.
            messages_normalises = (
                [{"role": "user", "content": messages}] if isinstance(messages, str) else messages
            )
            payload: dict = {"model": "mistral-factice", "messages": messages_normalises}
            if response_format is not None:
                payload["response_format"] = response_format
            if tools is not None:
                payload["tools"] = tools

            if self._exception is not None:
                raise ErreurAppelMistral(str(self._exception), payload_envoye=payload) from self._exception

            if response_format is not None:
                assert self._reponse_structuree is not None, (
                    "Aucune réponse structurée configurée : passer resume_et_profil= à repondre()"
                )
                return ReponseChat(
                    contenu=self._reponse_structuree,
                    usage=_USAGE_FACTICE,
                    payload_envoye=payload,
                    reponse_brute={"choices": [{"message": {"content": self._reponse_structuree}}]},
                )

            if tools and self._demandes_outils:
                appels = self._demandes_outils.pop(0)
                message_assistant = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": appel.id,
                            "function": {"name": appel.nom, "arguments": json.dumps(appel.arguments)},
                        }
                        for appel in appels
                    ],
                }
                raise AppelOutilDemande(
                    appels,
                    message_assistant,
                    self._usage_principal(messages),
                    payload_envoye=payload,
                    reponse_brute={"choices": [{"message": message_assistant}]},
                )

            if self._echec_apres_demandes_outils is not None:
                erreur = self._echec_apres_demandes_outils
                self._echec_apres_demandes_outils = None
                raise ErreurAppelMistral(str(erreur), payload_envoye=payload) from erreur

            assert self._reponses, "Aucune réponse configurée : appeler repondre() d'abord"
            contenu = self._reponses.pop(0) if len(self._reponses) > 1 else self._reponses[0]
            return ReponseChat(
                contenu=contenu,
                usage=self._usage_principal(messages),
                payload_envoye=payload,
                reponse_brute={"choices": [{"message": {"content": contenu}}]},
            )


class MoteurRechercheFactice:
    # Remplace SearXNG (spec 1.4.0) : aucun test ne sort sur le réseau. Sans
    # configuration, aucun résultat.
    def __init__(self) -> None:
        self.requetes_recues: list = []
        self._resultats: list[ResultatRecherche] = []
        self._indisponible = False

    def repondre(self, *resultats: tuple[str, str, str]) -> None:
        # (titre, url, extrait) par résultat, dans l'ordre du moteur.
        self._resultats = [ResultatRecherche(titre, url, extrait) for titre, url, extrait in resultats]
        self._indisponible = False

    def echouer(self) -> None:
        self._indisponible = True

    def rechercher(self, *args, **kwargs) -> list[ResultatRecherche]:
        self.requetes_recues.append((args, kwargs))
        if self._indisponible:
            raise MoteurIndisponible("moteur injoignable")
        return list(self._resultats)


class TelechargeurPagesFactice:
    # Remplace le téléchargement des pages trouvées (spec 1.4.0) : aucun test
    # ne sort sur le réseau. Une URL non servie est injoignable.
    def __init__(self) -> None:
        self.urls_recues: list[str] = []
        self._pages: dict[str, PageTelechargee] = {}

    def servir(
        self, url: str, corps: str, statut: int = 200, type_contenu: str = "text/html; charset=utf-8"
    ) -> None:
        self._pages[url] = PageTelechargee(statut=statut, type_contenu=type_contenu, corps=corps)

    def telecharger(self, url: str) -> PageTelechargee:
        self.urls_recues.append(url)
        page = self._pages.get(url)
        if page is None:
            raise PageIndisponible("délai dépassé")
        return page


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mistral_client_factice():
    return ClientMistralFactice()


@pytest.fixture
def moteur_recherche_factice():
    return MoteurRechercheFactice()


@pytest.fixture
def telechargeur_pages_factice():
    return TelechargeurPagesFactice()


class FabriqueSessionPartagee:
    # Le tour d'un envoi de message (ADR-0016) s'exécute dans son propre
    # thread avec sa propre session : ici celle du test, comme get_db, pour
    # qu'un test relise en base ce que le tour a écrit. Compte les tours
    # terminés, pour attendre celui dont personne ne lit le flux ; les
    # vérifications d'avant le flux, sur le thread de la requête, ne
    # comptent pas.
    def __init__(self, db) -> None:
        self._db = db
        self._tours_termines = threading.Semaphore(0)

    @contextmanager
    def __call__(self):
        try:
            yield self._db
        finally:
            if threading.current_thread().name == "tour-de-chat":
                self._tours_termines.release()

    def attendre_tours(self, nombre: int, delai: float = 5.0) -> bool:
        return all(self._tours_termines.acquire(timeout=delai) for _ in range(nombre))


@pytest.fixture
def fabrique_session(db_session):
    return FabriqueSessionPartagee(db_session)


@pytest.fixture
def jeton_store(db_session):
    return JetonStore(db_session)


@pytest.fixture
def client(
    db_session,
    fabrique_session,
    mistral_client_factice,
    moteur_recherche_factice,
    telechargeur_pages_factice,
    jeton_store,
):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_fabrique_session] = lambda: fabrique_session
    app.dependency_overrides[get_mistral_client] = lambda: mistral_client_factice
    app.dependency_overrides[get_moteur_recherche] = lambda: moteur_recherche_factice
    app.dependency_overrides[get_telechargeur_pages] = lambda: telechargeur_pages_factice
    app.dependency_overrides[get_jeton_store] = lambda: jeton_store
    # Moduléo non configuré par défaut : aucun test ne lit le .env réel ni
    # ne sort vers le serveur du cabinet. Fixture `faux_moduleo` pour le
    # configurer (spec 1.5.0).
    app.dependency_overrides[get_client_moduleo] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def compte_tous_droits_moduleo(db_session):
    # Le compte j.dupont rattaché aux groupes « Tous droits (dev) » (spec
    # 1.5.1) : sans groupe, aucun outil Moduléo ne lui serait proposé.
    charger_catalogue(db_session)
    creer_groupes_dev(db_session)
    rattacher(db_session, "j.dupont", GROUPE_DEV, GROUPE_DEV, None)
    db_session.commit()


@pytest.fixture
def faux_moduleo(client, compte_tous_droits_moduleo):
    # Moduléo configuré, servi par le faux de tests/faux_moduleo.py.
    faux = FauxModuleo()
    app.dependency_overrides[get_client_moduleo] = lambda: faux
    return faux


@pytest.fixture
def jeton_valide(jeton_store):
    return jeton_store.emettre("j.dupont")


@pytest.fixture
def seed_compte(db_session):
    def _seed(
        identifiant: str,
        mot_de_passe: str,
        agence: str,
        poles: list[str],
        prenom: str,
        nom: str,
        email: str | None = None,
        est_admin: bool = False,
        doit_changer_mot_de_passe: bool = False,
    ) -> Compte:
        compte = Compte(
            identifiant=identifiant,
            mot_de_passe_hash=hash_password(mot_de_passe),
            prenom=prenom,
            nom=nom,
            email=email,
            agence=agence,
            est_admin=est_admin,
            doit_changer_mot_de_passe=doit_changer_mot_de_passe,
            poles=[ComptePole(pole=p) for p in poles],
        )
        db_session.add(compte)
        db_session.commit()
        db_session.refresh(compte)
        return compte

    return _seed
