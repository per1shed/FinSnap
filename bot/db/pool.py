from pathlib import Path

import asyncpg

from bot.config import Settings

_pool: asyncpg.Pool | None = None
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def init_pool(settings: Settings) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        min_size=1,
        max_size=10,
    )
    await _apply_schema(_pool)
    return _pool


async def _apply_schema(pool: asyncpg.Pool) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS utc_offset_minutes INTEGER;"
        )
        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS total_balance NUMERIC(14, 2) NOT NULL DEFAULT 0;
            """
        )
        await conn.execute(
            """
            UPDATE users u
            SET total_balance = COALESCE(
                (
                    SELECT SUM(
                        CASE
                            WHEN t.type = 'income' THEN t.amount
                            ELSE -t.amount
                        END
                    )
                    FROM transactions t
                    WHERE t.user_id = u.user_id
                ),
                0
            )
            WHERE EXISTS (SELECT 1 FROM transactions t WHERE t.user_id = u.user_id);
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_goals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                title VARCHAR(128) NOT NULL,
                target_amount NUMERIC(14, 2) NOT NULL CHECK (target_amount > 0),
                saved_amount NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (saved_amount >= 0),
                is_completed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_financial_goals_user_active
            ON financial_goals (user_id, is_completed, created_at DESC);
            """
        )
        await conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS welcome_seen BOOLEAN NOT NULL DEFAULT FALSE;
            """
        )
        await conn.execute(
            """
            UPDATE users
            SET welcome_seen = TRUE
            WHERE utc_offset_minutes IS NOT NULL AND welcome_seen = FALSE;
            """
        )
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(64);"
        )
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(128);"
        )


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
