import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    timezone: ZoneInfo
    admin_ids: frozenset[int]

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def _parse_admin_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise RuntimeError(f"Invalid ADMIN_IDS entry: {part!r}") from exc
    return frozenset(ids)


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in environment")

    tz_name = os.getenv("TZ", "Europe/Moscow").strip()
    try:
        timezone = ZoneInfo(tz_name)
    except Exception as exc:
        raise RuntimeError(f"Invalid TZ: {tz_name}") from exc

    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

    return Settings(
        bot_token=token,
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "finsnap"),
        postgres_user=os.getenv("POSTGRES_USER", "finsnap"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
        timezone=timezone,
        admin_ids=admin_ids,
    )
