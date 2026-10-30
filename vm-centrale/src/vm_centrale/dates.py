import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

# Le cabinet est en France : « aujourd'hui », les semaines et les périodes par
# défaut se comptent à l'heure de Paris. En UTC, lundi entre 0 h et 2 h serait
# encore dimanche et « cette semaine » glisserait d'une semaine (#200).
_FUSEAU_CABINET = ZoneInfo("Europe/Paris")

_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
# « 2026-11-15T00:00:00+01:00 », « 2026-11-02T13:30:00.123Z ».
_DATE_HEURE_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?")


def date_du_jour() -> date:
    return datetime.now(_FUSEAU_CABINET).date()


def _jour(jour: date) -> str:
    return f"{'1er' if jour.day == 1 else jour.day} {_MOIS[jour.month - 1]} {jour.year}"


def jour_en_lettres(valeur: str) -> str | None:
    # Un champ Moduléo qui ne porte qu'un jour (#261) : « 28 octobre 2026 »,
    # le jour écrit dans la date, sans conversion de fuseau. Le modèle
    # envoie parfois minuit avec le décalage d'été en hiver (« +02:00 ») :
    # à l'heure de Paris, ce serait la veille à 23:00. None si ce n'est pas
    # une date.
    texte = valeur.strip()
    if not (_DATE_HEURE_ISO.fullmatch(texte) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte)):
        return None
    try:
        return _jour(date.fromisoformat(texte[:10]))
    except ValueError:
        return None


def instant(valeur: str) -> datetime | None:
    # Une date ISO de Moduléo, à l'heure de Paris. Sans fuseau, l'heure est
    # celle de Paris. None si ce n'est pas une date.
    if not _DATE_HEURE_ISO.fullmatch(valeur.strip()):
        return None
    try:
        moment = datetime.fromisoformat(valeur.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_FUSEAU_CABINET)
    return moment.astimezone(_FUSEAU_CABINET)


def date_heure_en_lettres(valeur: str) -> str | None:
    # Une date ISO de Moduléo, lisible et à l'heure de Paris (#256) :
    # « 15 novembre 2026 », ou « 2 novembre 2026 à 14:30 » quand l'heure
    # n'est pas minuit. None si ce n'est pas une date.
    moment = instant(valeur)
    if moment is None:
        return None
    jour = _jour(moment.date())
    if (moment.hour, moment.minute) == (0, 0):
        return jour
    return f"{jour} à {moment:%H:%M}"
