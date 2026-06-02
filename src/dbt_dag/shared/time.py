from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def now_msk() -> datetime:
    return datetime.now(tz=MSK)


def normalize_to_msk(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MSK)
