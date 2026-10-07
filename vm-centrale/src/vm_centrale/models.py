from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vm_centrale.database import Base

_FK_CONVERSATIONS_ID = "conversations.id"


class Compte(Base):
    __tablename__ = "comptes"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifiant: Mapped[str] = mapped_column(String, unique=True, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String)
    prenom: Mapped[str] = mapped_column(String)
    nom: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    agence: Mapped[str] = mapped_column(String)
    est_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    doit_changer_mot_de_passe: Mapped[bool] = mapped_column(Boolean, default=False)
    poles: Mapped[list["ComptePole"]] = relationship(
        back_populates="compte", cascade="all, delete-orphan", order_by="ComptePole.pole"
    )


class ComptePole(Base):
    # Table de jointure compte/pôle ([[0006-compte-rattache-plusieurs-poles]]) :
    # la liste des six pôles reste une liste fermée fixée dans le code, pas une
    # table `Pôle` gérable dynamiquement pour cette itération.
    __tablename__ = "comptes_poles"

    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), primary_key=True)
    pole: Mapped[str] = mapped_column(String, primary_key=True)

    compte: Mapped["Compte"] = relationship(back_populates="poles")


class Jeton(Base):
    __tablename__ = "jetons"

    jeton: Mapped[str] = mapped_column(String, primary_key=True)
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    date_emission: Mapped[datetime] = mapped_column(DateTime)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Pas de ForeignKey vers comptes.identifiant : même convention que Jeton
    # ci-dessus (le compte du jeton est résolu via JetonStore, jamais rejoint
    # en base).
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    titre: Mapped[str] = mapped_column(String)
    resume_contexte: Mapped[str] = mapped_column(String, default="")
    date_creation: Mapped[datetime] = mapped_column(DateTime)
    date_derniere_activite: Mapped[datetime] = mapped_column(DateTime)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(_FK_CONVERSATIONS_ID), index=True
    )
    role: Mapped[str] = mapped_column(String)
    contenu: Mapped[str] = mapped_column(String)
    # Jauge de contexte (spec 1.4.2) : prompt_tokens du dernier appel
    # principal du tour, sur le message `assistant` seulement. NULL pour un
    # message `user` et pour un message d'avant la 1.4.2 (jamais recalculé).
    tokens_contexte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_creation: Mapped[datetime] = mapped_column(DateTime)


class PieceJointe(Base):
    __tablename__ = "pieces_jointes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Toujours renseigné à l'upload (jeton du compte), indépendamment de
    # conversation_id ci-dessous : seule façon de vérifier la propriété d'une
    # pièce jointe pas encore rattachée à une conversation (voir
    # conversation_id).
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    # Nullable : une pièce jointe peut être téléversée avant même que la
    # conversation qui la portera n'existe (POST /pieces-jointes, sans
    # conversation_id dans l'URL) — nécessaire pour pouvoir en joindre une dès
    # le tout premier message d'une conversation (spec 1.1.2, référencement).
    # Renseigné au rattachement (création de la conversation, ou envoi d'un
    # message) si elle ne l'était pas déjà.
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey(_FK_CONVERSATIONS_ID), nullable=True, index=True
    )
    # Nullable : renseigné seulement une fois la pièce jointe liée à un
    # message envoyé (référencement dans l'envoi d'un message — spec 1.1.2).
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    nom_fichier: Mapped[str] = mapped_column(String)
    type_mime: Mapped[str] = mapped_column(String)
    taille_octets: Mapped[int] = mapped_column(Integer)
    # Chemin relatif sous VM_CENTRALE_PIECES_JOINTES_DIR, jamais absolu (le
    # fichier physique, lui, vit sur disque — voir ADR-0009).
    chemin_fichier: Mapped[str] = mapped_column(String)
    contenu_extrait: Mapped[str | None] = mapped_column(String, nullable=True)
    echec_analyse: Mapped[bool] = mapped_column(Boolean, default=False)
    date_creation: Mapped[datetime] = mapped_column(DateTime)


class Consommation(Base):
    __tablename__ = "consommations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Pas de ForeignKey vers comptes.identifiant : même convention que
    # Conversation/Jeton/ProfilTravail ci-dessus.
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    # Nullable : mis explicitement à NULL (jamais de cascade) à la
    # suppression de la conversation qui l'a produite (spec 1.1.3) — la
    # ligne de consommation survit à ce qui l'a produite, seul le
    # rattachement disparaît.
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey(_FK_CONVERSATIONS_ID), nullable=True, index=True
    )
    # "chat" / "titrage" / "resume_et_profil" / "ocr" / "vision" (spec 1.1.3).
    type_appel: Mapped[str] = mapped_column(String)
    # La constante MODELE_CHAT/MODELE_OCR effectivement utilisée pour cet appel.
    modele: Mapped[str] = mapped_column(String)
    # Renseignés pour tout sauf "ocr" (facturé à la page, pas au token).
    tokens_entree: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_sortie: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Renseigné seulement pour "ocr".
    pages_traitees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Figé au tarif du jour de l'appel (spec 1.1.3) : jamais recalculé à la
    # lecture, même si les constantes de tarif de config.py changent ensuite.
    cout_usd: Mapped[Decimal] = mapped_column(Numeric)
    date_creation: Mapped[datetime] = mapped_column(DateTime)


class EchangeInspecteur(Base):
    # Inspecteur des échanges avec le modèle (spec 1.3.0), distincte de
    # Consommation : capture le payload exact envoyé et la réponse brute
    # reçue pour chaque appel Mistral réel, pas seulement des métadonnées
    # agrégées. Outil de débogage technique, jamais consulté par le code
    # applicatif lui-même.
    __tablename__ = "echanges_inspecteur"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifiant_compte: Mapped[str] = mapped_column(String, index=True)
    # Nullable, bien que la spec 1.3.0 ne le présente pas ainsi : un échec dès
    # le tout premier appel Mistral de creer_conversation survient avant le
    # commit de la conversation flushée pour obtenir son id (aucune
    # conversation fantôme, spec 1.1.2) — le db.rollback() qui annule cette
    # conversation interdit toute ligne qui la référencerait par FK. ON
    # DELETE CASCADE ci-dessous ne s'applique simplement jamais à ces lignes
    # orphelines (NULL n'est jamais affecté par la suppression d'une autre
    # ligne).
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey(_FK_CONVERSATIONS_ID, ondelete="CASCADE"), nullable=True, index=True
    )
    # Nullable : pas toujours de pièce jointe concernée par l'appel (spec
    # 1.3.0). Pas de ondelete ici (comme PieceJointe elle-même) : jamais
    # affecté par la suppression d'une pièce jointe, hors périmètre de ce
    # ticket.
    piece_jointe_id: Mapped[int | None] = mapped_column(
        ForeignKey("pieces_jointes.id"), nullable=True
    )
    # "mistral" : un appel Mistral réel ; "local" : du travail de la VM elle-
    # même, comme l'exécution d'un outil (spec 1.4.0).
    origine: Mapped[str] = mapped_column(String)
    # Mistral : même vocabulaire que Consommation.type_appel ("chat" /
    # "titrage" / "resume_et_profil" / "ocr" / "vision"). Local :
    # "outil:<nom de l'outil>" ou "garde_fous".
    type_appel: Mapped[str] = mapped_column(String)
    # Vide pour un échange local (aucun modèle appelé).
    modele: Mapped[str] = mapped_column(String)
    # Payload exact tel que construit juste avant l'appel HTTP à Mistral :
    # jamais la clé API ni l'en-tête Authorization, ajoutés séparément du
    # corps JSON, après le moment où ce payload est capturé (spec 1.3.0).
    requete_payload: Mapped[dict] = mapped_column(JSON)
    # Nullable : absent pour un échange en échec (statut ci-dessous).
    reponse_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # "succes" / "echec".
    statut: Mapped[str] = mapped_column(String)
    erreur: Mapped[str | None] = mapped_column(String, nullable=True)
    date_creation: Mapped[datetime] = mapped_column(DateTime)


class ResultatRechercheWeb(Base):
    # Une ligne par résultat de l'outil rechercher_web (spec 1.4.0) : les
    # garde-fous lisent ces sources sur toute la conversation (une URL
    # trouvée à un tour reste citable au tour suivant).
    __tablename__ = "resultats_recherche_web"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(_FK_CONVERSATIONS_ID, ondelete="CASCADE"), index=True
    )
    # Nullable : renseigné à la persistance de la réponse du tour, pour la
    # numéro de tour de la recherche dans la Mémoire de la conversation
    # (spec 1.4.1).
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True, index=True
    )
    requete: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    titre: Mapped[str] = mapped_column(String)
    extrait_moteur: Mapped[str] = mapped_column(String)
    # Texte principal de la page téléchargée et nettoyée ; vide si la page
    # n'a pas été téléchargée.
    texte_nettoye: Mapped[str] = mapped_column(String, default="")
    # `recherche` (trouvée par rechercher_web) ou `utilisateur` (URL écrite
    # par le compte, téléchargée par lire_pages_web, requête vide) : spec
    # 1.4.1, #140. Les deux sont des sources du garde-fou chiffres.
    provenance: Mapped[str] = mapped_column(String, default="recherche", server_default="recherche")
    date_creation: Mapped[datetime] = mapped_column(DateTime)


class PageWebEnCache(Base):
    # Cache commun des pages web (spec 1.4.3, ADR-0015) : une ligne par URL
    # exacte, partagée entre tous les comptes et tous les pôles. Aucune clé
    # étrangère vers une conversation : la supprimer ne touche pas au cache.
    # Seulement des pages lues avec succès, jamais un extrait ni une
    # question couverte (ils portent le besoin d'un compte).
    __tablename__ = "cache_pages_web"

    url: Mapped[str] = mapped_column(String, primary_key=True)
    # Texte principal nettoyé, avant tout plafond de tokens.
    texte_nettoye: Mapped[str] = mapped_column(String)
    titre: Mapped[str] = mapped_column(String)
    # Avec fuseau : l'âge de la copie se calcule en UTC quel que soit le
    # fuseau du serveur PostgreSQL.
    date_telechargement: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionCouverte(Base):
    # Une question à laquelle le contenu d'un élément de la conversation
    # répond (spec 1.4.1) : une pièce jointe ou un résultat de recherche web,
    # jamais les deux. Écrite par un modèle : jamais une source des
    # garde-fous.
    __tablename__ = "questions_couvertes"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(_FK_CONVERSATIONS_ID, ondelete="CASCADE"), index=True
    )
    piece_jointe_id: Mapped[int | None] = mapped_column(
        ForeignKey("pieces_jointes.id"), nullable=True, index=True
    )
    resultat_recherche_web_id: Mapped[int | None] = mapped_column(
        ForeignKey("resultats_recherche_web.id"), nullable=True, index=True
    )
    question: Mapped[str] = mapped_column(String)
    reponse: Mapped[str] = mapped_column(String)
    # Nom de fichier ou URL de l'élément.
    source: Mapped[str] = mapped_column(String)
    # Faux : « non présent selon l'extraction » pour ce besoin.
    trouvee: Mapped[bool] = mapped_column(Boolean, default=True)
    # "initiale" (générée à la lecture de l'élément) / "besoin" (relecture
    # avec un besoin).
    origine: Mapped[str] = mapped_column(String)
    date_creation: Mapped[datetime] = mapped_column(DateTime)


class ProfilTravail(Base):
    __tablename__ = "profils_travail"

    # Un-à-un avec Compte (une ligne par compte, identifiant_compte en PK).
    # Pas de ForeignKey vers comptes.identifiant : même convention que
    # Conversation/Jeton ci-dessus (le compte du jeton est résolu via
    # JetonStore, jamais rejoint en base).
    identifiant_compte: Mapped[str] = mapped_column(String, primary_key=True)
    contenu: Mapped[str] = mapped_column(String, default="")
    date_derniere_maj: Mapped[datetime] = mapped_column(DateTime)
