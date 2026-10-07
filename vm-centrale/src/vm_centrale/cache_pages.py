from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from vm_centrale.config import VALIDITE_CACHE_PAGES
from vm_centrale.models import PageWebEnCache

# Cache commun des pages web (spec 1.4.3, ADR-0015). Clé : l'URL exacte,
# jamais normalisée (un chemin peut tenir compte de la casse). Une URL plus
# longue n'est jamais mise en cache : clé primaire, un index PostgreSQL
# refuse une valeur de plus de 2 704 octets, et le tour échouerait.
_URL_MAX = 2_000


@dataclass(frozen=True)
class CopieEnCache:
    texte: str
    titre: str
    age: timedelta


def _en_utc(date: datetime) -> datetime:
    # SQLite rend une date sans fuseau, enregistrée en UTC.
    return date if date.tzinfo is not None else date.replace(tzinfo=timezone.utc)


def lire_copie(db: Session, url: str, maintenant: datetime) -> CopieEnCache | None:
    # Une copie de plus de VALIDITE_CACHE_PAGES est ignorée, jamais supprimée
    # ici : aucune purge pendant une requête. Colonnes, pas d'objet : jamais
    # une copie périmée gardée par la session après un écrasement du tour.
    if len(url) > _URL_MAX:
        return None
    copie = (
        db.query(PageWebEnCache.texte_nettoye, PageWebEnCache.titre, PageWebEnCache.date_telechargement)
        .filter(PageWebEnCache.url == url)
        .first()
    )
    if copie is None:
        return None
    texte, titre, date_telechargement = copie
    age = maintenant - _en_utc(date_telechargement)
    if age > VALIDITE_CACHE_PAGES:
        return None
    return CopieEnCache(texte=texte, titre=titre, age=age)


def ecrire_copie(db: Session, url: str, texte: str, titre: str, maintenant: datetime) -> None:
    # Insertion ou écrasement en une instruction : deux conversations qui
    # écrivent la même URL en même temps, la dernière écriture l'emporte,
    # sans erreur de clé. Dans la transaction du tour, comme le reste.
    if len(url) > _URL_MAX:
        return
    inserer = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    valeurs = {"texte_nettoye": texte, "titre": titre, "date_telechargement": maintenant}
    instruction = inserer(PageWebEnCache).values(url=url, **valeurs)
    db.execute(instruction.on_conflict_do_update(index_elements=[PageWebEnCache.url], set_=valeurs))
