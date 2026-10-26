from datetime import date, datetime
from zoneinfo import ZoneInfo

# Le cabinet est en France : « aujourd'hui », les semaines et les périodes par
# défaut se comptent à l'heure de Paris. En UTC, lundi entre 0 h et 2 h serait
# encore dimanche et « cette semaine » glisserait d'une semaine (#200).
_FUSEAU_CABINET = ZoneInfo("Europe/Paris")


def date_du_jour() -> date:
    return datetime.now(_FUSEAU_CABINET).date()
