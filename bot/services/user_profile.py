import asyncpg
from aiogram.types import User as TgUser

from bot.db import queries


async def sync_user_profile(pool: asyncpg.Pool, tg_user: TgUser) -> None:
    await queries.ensure_user(
        pool,
        tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
    )
