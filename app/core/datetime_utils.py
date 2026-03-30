from datetime import datetime
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")


def madrid_now() -> datetime:
    """Return current Europe/Madrid time as naive datetime for DB DateTime columns."""
    return datetime.now(MADRID_TZ).replace(tzinfo=None)
