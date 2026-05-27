from datetime import tzinfo

import asyncpg

from bot.config import Settings
from bot.db import queries
from bot.services.user_timezone import offset_minutes_to_tz


async def resolve_user_tz(
    pool: asyncpg.Pool, user_id: int, settings: Settings
) -> tzinfo:
    offset = await queries.get_user_utc_offset(pool, user_id)
    if offset is None:
        return settings.timezone
    return offset_minutes_to_tz(offset)
