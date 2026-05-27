import re
from datetime import datetime, timedelta, timezone, tzinfo

_HOUR_RE = re.compile(r"^\s*(\d{1,2})\s*$")

# Смещение от UTC (в минутах) → прилагательное для «… часовом поясе»
_OFFSET_LABELS_RU: dict[int, str] = {
    -720: "времени на линии перемены дат (UTC−12)",
    -660: "времени UTC−11",
    -600: "гавайском",
    -540: "аляскинском",
    -480: "тихоокеанском (США и Канада)",
    -420: "горном",
    -360: "центральном (США и Канада)",
    -300: "восточном (США и Канада)",
    -240: "атлантическом",
    -180: "аргентинском",
    -120: "бразильском",
    -60: "азорском",
    0: "нулевом (Лондон, UTC)",
    60: "центральноевропейском",
    120: "калининградском",
    180: "московском",
    210: "иранском",
    240: "самарском",
    270: "армянском",
    300: "екатеринбургском",
    330: "индийском",
    345: "непальском",
    360: "омском",
    390: "мьянманском",
    420: "красноярском",
    480: "иркутском",
    525: "австралийском (центральном)",
    540: "якутском",
    570: "австралийском (восточном)",
    600: "владивостокском",
    630: "австралийском (полуострове)",
    660: "магаданском",
    720: "камчатском",
    780: "время UTC+13",
}


def parse_hour_input(text: str) -> int | None:
    """Парсит только час (0–23)."""
    match = _HOUR_RE.match(text or "")
    if not match:
        return None
    hour = int(match.group(1))
    if hour > 23:
        return None
    return hour


def compute_utc_offset_from_hour(hour: int, now_utc: datetime | None = None) -> int:
    """
    Смещение в минутах: локальное = UTC + offset.
    Минуты берём из текущего UTC (у всех «сейчас» одни и те же минуты на сервере).
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    user_minutes = hour * 60 + now_utc.minute
    utc_minutes = now_utc.hour * 60 + now_utc.minute
    diff = user_minutes - utc_minutes

    if diff > 12 * 60:
        diff -= 24 * 60
    elif diff < -12 * 60:
        diff += 24 * 60

    return diff


def offset_minutes_to_tz(offset_minutes: int) -> timezone:
    return timezone(timedelta(minutes=offset_minutes))


def format_utc_offset(offset_minutes: int) -> str:
    sign = "+" if offset_minutes >= 0 else "-"
    total = abs(offset_minutes)
    hours, minutes = divmod(total, 60)
    if minutes:
        return f"UTC{sign}{hours}:{minutes:02d}"
    return f"UTC{sign}{hours}"


def describe_timezone_human(offset_minutes: int) -> str:
    """Текст для пользователя: «московском часовом поясе» и т.п."""
    label = _OFFSET_LABELS_RU.get(offset_minutes)
    if label:
        if label.startswith("времени") or label.startswith("время"):
            return f"Отлично! У вас <b>{label}</b>."
        return f"Отлично! Вы находитесь в <b>{label}</b> часовом поясе."

    return (
        f"Отлично! Установлен часовой пояс <b>{format_utc_offset(offset_minutes)}</b>."
    )


def tz_to_postgres_name(tz: tzinfo) -> str:
    """Имя зоны для PostgreSQL AT TIME ZONE (IANA или ±HH:MM)."""
    key = getattr(tz, "key", None)
    if key:
        return key

    offset = tz.utcoffset(datetime.now(timezone.utc))
    if offset is None:
        return "UTC"

    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"
