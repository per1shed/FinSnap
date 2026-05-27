from datetime import date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal

import asyncpg

from bot.constants import TransactionType
from bot.services.user_timezone import tz_to_postgres_name


def _to_db_timestamp(dt: datetime) -> datetime:
    """PostgreSQL TIMESTAMP без TZ: передаём naive UTC."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def ensure_user(
    pool: asyncpg.Pool,
    user_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
) -> None:
    await pool.execute(
        """
        INSERT INTO users (user_id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE SET
            username = COALESCE(EXCLUDED.username, users.username),
            first_name = COALESCE(EXCLUDED.first_name, users.first_name)
        """,
        user_id,
        username,
        first_name,
    )


async def get_user_utc_offset(pool: asyncpg.Pool, user_id: int) -> int | None:
    row = await pool.fetchrow(
        "SELECT utc_offset_minutes FROM users WHERE user_id = $1",
        user_id,
    )
    if row is None:
        return None
    return row["utc_offset_minutes"]


async def has_seen_welcome(pool: asyncpg.Pool, user_id: int) -> bool:
    row = await pool.fetchrow(
        "SELECT welcome_seen FROM users WHERE user_id = $1",
        user_id,
    )
    if row is None:
        return False
    return bool(row["welcome_seen"])


async def mark_welcome_seen(pool: asyncpg.Pool, user_id: int) -> None:
    await pool.execute(
        """
        UPDATE users SET welcome_seen = TRUE WHERE user_id = $1
        """,
        user_id,
    )


async def set_user_utc_offset(
    pool: asyncpg.Pool, user_id: int, offset_minutes: int
) -> None:
    await pool.execute(
        """
        INSERT INTO users (user_id, utc_offset_minutes)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE
        SET utc_offset_minutes = EXCLUDED.utc_offset_minutes
        """,
        user_id,
        offset_minutes,
    )


def _month_bounds(now: datetime, tz: tzinfo) -> tuple[datetime, datetime]:
    local = now.astimezone(tz)
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _period_bounds(
    period: str, now: datetime, tz: tzinfo
) -> tuple[datetime, datetime]:
    local = now.astimezone(tz)
    end = local
    if period == "week":
        start = (local - timedelta(days=7)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif period == "month":
        start, end = _month_bounds(now, tz)
    else:
        raise ValueError(f"Unknown period: {period}")
    return start, end


async def get_month_summary(
    pool: asyncpg.Pool,
    user_id: int,
    now: datetime,
    tz: tzinfo,
) -> tuple[Decimal, Decimal]:
    start, end = _month_bounds(now, tz)
    row = await pool.fetchrow(
        """
        SELECT
            COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0) AS income,
            COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS expense
        FROM transactions
        WHERE user_id = $1
          AND created_at >= $2
          AND created_at < $3
        """,
        user_id,
        _to_db_timestamp(start),
        _to_db_timestamp(end),
    )
    return Decimal(row["income"]), Decimal(row["expense"])


async def get_total_balance(pool: asyncpg.Pool, user_id: int) -> Decimal:
    row = await pool.fetchrow(
        "SELECT total_balance FROM users WHERE user_id = $1",
        user_id,
    )
    if row is None:
        return Decimal("0")
    return Decimal(row["total_balance"])


async def insert_transaction(
    pool: asyncpg.Pool,
    user_id: int,
    tx_type: TransactionType,
    category: str,
    amount: Decimal,
    comment: str,
) -> None:
    delta = amount if tx_type == TransactionType.INCOME else -amount
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO transactions (user_id, type, category, amount, comment)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                tx_type.value,
                category,
                amount,
                comment,
            )
            await conn.execute(
                """
                UPDATE users
                SET total_balance = total_balance + $2
                WHERE user_id = $1
                """,
                user_id,
                delta,
            )


async def get_expenses_by_category(
    pool: asyncpg.Pool,
    user_id: int,
    period: str,
    now: datetime,
    tz: tzinfo,
) -> list[tuple[str, Decimal]]:
    return await get_by_category(pool, user_id, TransactionType.EXPENSE, period, now, tz)


async def get_by_category(
    pool: asyncpg.Pool,
    user_id: int,
    tx_type: TransactionType,
    period: str,
    now: datetime,
    tz: tzinfo,
) -> list[tuple[str, Decimal]]:
    start, end = _period_bounds(period, now, tz)
    rows = await pool.fetch(
        """
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE user_id = $1
          AND type = $2
          AND created_at >= $3
          AND created_at < $4
        GROUP BY category
        ORDER BY total DESC
        """,
        user_id,
        tx_type.value,
        _to_db_timestamp(start),
        _to_db_timestamp(end),
    )
    return [(row["category"], Decimal(row["total"])) for row in rows]


async def get_daily_totals_for_month(
    pool: asyncpg.Pool,
    user_id: int,
    tx_type: TransactionType,
    now: datetime,
    tz: tzinfo,
) -> list[tuple[date, Decimal]]:
    start, end = _month_bounds(now, tz)
    tz_name = tz_to_postgres_name(tz)
    rows = await pool.fetch(
        """
        SELECT
            ((created_at AT TIME ZONE 'UTC') AT TIME ZONE $5)::date AS day,
            SUM(amount) AS total
        FROM transactions
        WHERE user_id = $1
          AND type = $2
          AND created_at >= $3
          AND created_at < $4
        GROUP BY day
        ORDER BY day
        """,
        user_id,
        tx_type.value,
        _to_db_timestamp(start),
        _to_db_timestamp(end),
        tz_name,
    )
    return [(row["day"], Decimal(row["total"])) for row in rows]
