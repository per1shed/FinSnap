from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal

import asyncpg

from bot.db.queries import _to_db_timestamp


@dataclass(frozen=True)
class AdminDashboardStats:
    generated_at: datetime
    period_key: str
    period_label: str

    users_total: int
    users_new_today: int
    users_new_7d: int
    users_new_30d: int
    users_with_tz: int
    users_welcome_seen: int
    users_no_transactions: int
    users_active_7d: int
    users_active_30d: int

    tx_total: int
    tx_today: int
    tx_7d: int
    tx_30d: int
    tx_period: int
    tx_expense_period: int
    tx_income_period: int
    sum_expense_period: Decimal
    sum_income_period: Decimal
    avg_tx_amount_period: Decimal
    avg_tx_per_user_period: Decimal
    peak_day: date | None
    peak_day_count: int

    top_expense_month: list[tuple[str, Decimal]]
    top_expense_all: list[tuple[str, Decimal]]
    top_income_month: list[tuple[str, Decimal]]
    top_income_all: list[tuple[str, Decimal]]
    top_category_name: str | None
    top_category_count: int

    goals_total: int
    goals_active: int
    goals_completed: int
    goals_created_7d: int
    goals_created_30d: int
    goals_avg_progress_pct: Decimal
    goals_sum_saved: Decimal
    goals_users_count: int

    balance_sum: Decimal
    balance_avg: Decimal
    balance_negative_users: int

    users_with_tx_month: int
    users_with_goals_pct: Decimal
    goals_avg_per_user: Decimal


PERIOD_LABELS = {
    "today": "сегодня",
    "7d": "7 дней",
    "30d": "30 дней",
    "all": "всё время",
}


def _local_now(tz: tzinfo) -> datetime:
    return datetime.now(tz)


def _day_start(local: datetime) -> datetime:
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _period_bounds(
    period_key: str, now: datetime, tz: tzinfo
) -> tuple[datetime | None, datetime, datetime]:
    """Нижняя граница (None = без ограничения), конец, «сейчас» в TZ."""
    local = now.astimezone(tz)
    end_local = local
    if period_key == "today":
        return _day_start(local), end_local, local
    if period_key == "7d":
        start = _day_start(local - timedelta(days=7))
        return start, end_local, local
    if period_key == "30d":
        start = _day_start(local - timedelta(days=30))
        return start, end_local, local
    if period_key == "all":
        return None, end_local, local
    raise ValueError(f"Unknown period: {period_key}")


def _month_bounds(local: datetime) -> tuple[datetime, datetime]:
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _to_db_timestamp_optional(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return _to_db_timestamp(dt)


async def _count_users_joined_since(
    pool: asyncpg.Pool, since: datetime, until: datetime
) -> int:
    return await pool.fetchval(
        """
        SELECT COUNT(*)::int FROM users
        WHERE join_date >= $1 AND join_date < $2
        """,
        since,
        until,
    )


async def _count_active_users(
    pool: asyncpg.Pool, since: datetime, until: datetime
) -> int:
    return await pool.fetchval(
        """
        SELECT COUNT(DISTINCT user_id)::int FROM transactions
        WHERE created_at >= $1 AND created_at < $2
        """,
        since,
        until,
    )


async def _tx_stats_in_range(
    pool: asyncpg.Pool, since: datetime | None, until: datetime
) -> dict:
    if since is None:
        row = await pool.fetchrow(
            """
            SELECT
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE type = 'expense')::int AS expenses,
                COUNT(*) FILTER (WHERE type = 'income')::int AS incomes,
                COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS sum_expense,
                COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0) AS sum_income
            FROM transactions
            WHERE created_at < $1
            """,
            until,
        )
    else:
        row = await pool.fetchrow(
            """
            SELECT
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE type = 'expense')::int AS expenses,
                COUNT(*) FILTER (WHERE type = 'income')::int AS incomes,
                COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0) AS sum_expense,
                COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0) AS sum_income
            FROM transactions
            WHERE created_at >= $1 AND created_at < $2
            """,
            since,
            until,
        )
    total = row["total"]
    sum_all = Decimal(row["sum_expense"]) + Decimal(row["sum_income"])
    avg = sum_all / total if total else Decimal("0")
    return {
        "total": total,
        "expenses": row["expenses"],
        "incomes": row["incomes"],
        "sum_expense": Decimal(row["sum_expense"]),
        "sum_income": Decimal(row["sum_income"]),
        "avg_amount": avg,
    }


async def _top_categories(
    pool: asyncpg.Pool,
    tx_type: str,
    since: datetime | None,
    until: datetime,
    limit: int = 5,
) -> list[tuple[str, Decimal]]:
    if since is None:
        rows = await pool.fetch(
            """
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE type = $1 AND created_at < $2
            GROUP BY category
            ORDER BY total DESC
            LIMIT $3
            """,
            tx_type,
            until,
            limit,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE type = $1 AND created_at >= $2 AND created_at < $3
            GROUP BY category
            ORDER BY total DESC
            LIMIT $4
            """,
            tx_type,
            since,
            until,
            limit,
        )
    return [(r["category"], Decimal(r["total"])) for r in rows]


async def _top_category_by_count(
    pool: asyncpg.Pool, since: datetime | None, until: datetime
) -> tuple[str | None, int]:
    if since is None:
        row = await pool.fetchrow(
            """
            SELECT category, COUNT(*)::int AS cnt
            FROM transactions
            WHERE created_at < $1
            GROUP BY category
            ORDER BY cnt DESC
            LIMIT 1
            """,
            until,
        )
    else:
        row = await pool.fetchrow(
            """
            SELECT category, COUNT(*)::int AS cnt
            FROM transactions
            WHERE created_at >= $1 AND created_at < $2
            GROUP BY category
            ORDER BY cnt DESC
            LIMIT 1
            """,
            since,
            until,
        )
    if row is None:
        return None, 0
    return row["category"], row["cnt"]


async def fetch_admin_dashboard(
    pool: asyncpg.Pool,
    tz: tzinfo,
    period_key: str = "30d",
) -> AdminDashboardStats:
    if period_key not in PERIOD_LABELS:
        period_key = "30d"

    now = _local_now(tz)
    local = now.astimezone(tz)
    until = _to_db_timestamp(now)

    today_start = _to_db_timestamp(_period_bounds("today", now, tz)[0])
    start_7d = _to_db_timestamp(_period_bounds("7d", now, tz)[0])
    start_30d = _to_db_timestamp(_period_bounds("30d", now, tz)[0])
    period_start_raw, period_end_local, _ = _period_bounds(period_key, now, tz)
    period_start = _to_db_timestamp_optional(period_start_raw)
    period_until = _to_db_timestamp(period_end_local)

    month_start_local, month_end_local = _month_bounds(local)
    month_start = _to_db_timestamp(month_start_local)
    month_until = _to_db_timestamp(month_end_local)

    users_total = await pool.fetchval("SELECT COUNT(*)::int FROM users")
    users_with_tz = await pool.fetchval(
        "SELECT COUNT(*)::int FROM users WHERE utc_offset_minutes IS NOT NULL"
    )
    users_welcome_seen = await pool.fetchval(
        "SELECT COUNT(*)::int FROM users WHERE welcome_seen = TRUE"
    )
    users_no_transactions = await pool.fetchval(
        """
        SELECT COUNT(*)::int FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM transactions t WHERE t.user_id = u.user_id
        )
        """
    )

    users_new_today = await _count_users_joined_since(pool, today_start, until)
    users_new_7d = await _count_users_joined_since(pool, start_7d, until)
    users_new_30d = await _count_users_joined_since(pool, start_30d, until)

    users_active_7d = await _count_active_users(pool, start_7d, until)
    users_active_30d = await _count_active_users(pool, start_30d, until)

    tx_total = await pool.fetchval("SELECT COUNT(*)::int FROM transactions")

    tx_today = (await _tx_stats_in_range(pool, today_start, until))["total"]
    tx_7d = (await _tx_stats_in_range(pool, start_7d, until))["total"]
    tx_30d = (await _tx_stats_in_range(pool, start_30d, until))["total"]
    period_tx = await _tx_stats_in_range(pool, period_start, period_until)

    active_in_period = (
        await _count_active_users(pool, period_start, period_until)
        if period_start is not None
        else await pool.fetchval("SELECT COUNT(DISTINCT user_id)::int FROM transactions")
    )
    avg_per_user = (
        Decimal(period_tx["total"]) / active_in_period
        if active_in_period
        else Decimal("0")
    )

    peak_row = await pool.fetchrow(
        """
        SELECT day::date AS day, COUNT(*)::int AS cnt
        FROM (
            SELECT (created_at AT TIME ZONE 'UTC')::date AS day
            FROM transactions
        ) d
        GROUP BY day
        ORDER BY cnt DESC
        LIMIT 1
        """
    )
    peak_day = peak_row["day"] if peak_row else None
    peak_day_count = peak_row["cnt"] if peak_row else 0

    top_expense_month = await _top_categories(
        pool, "expense", month_start, month_until
    )
    top_expense_all = await _top_categories(pool, "expense", None, until)
    top_income_month = await _top_categories(pool, "income", month_start, month_until)
    top_income_all = await _top_categories(pool, "income", None, until)

    top_cat_name, top_cat_count = await _top_category_by_count(
        pool, period_start, period_until
    )

    goals_total = await pool.fetchval("SELECT COUNT(*)::int FROM financial_goals")
    goals_active = await pool.fetchval(
        "SELECT COUNT(*)::int FROM financial_goals WHERE is_completed = FALSE"
    )
    goals_completed = await pool.fetchval(
        "SELECT COUNT(*)::int FROM financial_goals WHERE is_completed = TRUE"
    )
    goals_created_7d = await pool.fetchval(
        """
        SELECT COUNT(*)::int FROM financial_goals
        WHERE created_at >= $1 AND created_at < $2
        """,
        start_7d,
        until,
    )
    goals_created_30d = await pool.fetchval(
        """
        SELECT COUNT(*)::int FROM financial_goals
        WHERE created_at >= $1 AND created_at < $2
        """,
        start_30d,
        until,
    )
    goals_sum_saved = Decimal(
        await pool.fetchval(
            "SELECT COALESCE(SUM(saved_amount), 0) FROM financial_goals"
        )
    )
    goals_users_count = await pool.fetchval(
        "SELECT COUNT(DISTINCT user_id)::int FROM financial_goals"
    )

    progress_row = await pool.fetchrow(
        """
        SELECT AVG(
            LEAST(saved_amount / NULLIF(target_amount, 0), 1) * 100
        ) AS avg_pct
        FROM financial_goals
        WHERE is_completed = FALSE AND target_amount > 0
        """
    )
    goals_avg_progress = Decimal(progress_row["avg_pct"] or 0)

    balance_sum = Decimal(
        await pool.fetchval("SELECT COALESCE(SUM(total_balance), 0) FROM users")
    )
    balance_avg = Decimal(
        await pool.fetchval(
            """
            SELECT COALESCE(AVG(u.total_balance), 0)
            FROM users u
            WHERE EXISTS (
                SELECT 1 FROM transactions t WHERE t.user_id = u.user_id
            )
            """
        )
    )
    balance_negative_users = await pool.fetchval(
        "SELECT COUNT(*)::int FROM users WHERE total_balance < 0"
    )

    users_with_tx_month = await _count_active_users(pool, month_start, month_until)

    users_with_goals_pct = (
        (Decimal(goals_users_count) / Decimal(users_total) * 100)
        if users_total
        else Decimal("0")
    )
    goals_avg_per_user = (
        Decimal(goals_total) / Decimal(goals_users_count)
        if goals_users_count
        else Decimal("0")
    )

    return AdminDashboardStats(
        generated_at=local,
        period_key=period_key,
        period_label=PERIOD_LABELS[period_key],
        users_total=users_total,
        users_new_today=users_new_today,
        users_new_7d=users_new_7d,
        users_new_30d=users_new_30d,
        users_with_tz=users_with_tz,
        users_welcome_seen=users_welcome_seen,
        users_no_transactions=users_no_transactions,
        users_active_7d=users_active_7d,
        users_active_30d=users_active_30d,
        tx_total=tx_total,
        tx_today=tx_today,
        tx_7d=tx_7d,
        tx_30d=tx_30d,
        tx_period=period_tx["total"],
        tx_expense_period=period_tx["expenses"],
        tx_income_period=period_tx["incomes"],
        sum_expense_period=period_tx["sum_expense"],
        sum_income_period=period_tx["sum_income"],
        avg_tx_amount_period=period_tx["avg_amount"],
        avg_tx_per_user_period=avg_per_user,
        peak_day=peak_day,
        peak_day_count=peak_day_count,
        top_expense_month=top_expense_month,
        top_expense_all=top_expense_all,
        top_income_month=top_income_month,
        top_income_all=top_income_all,
        top_category_name=top_cat_name,
        top_category_count=top_cat_count,
        goals_total=goals_total,
        goals_active=goals_active,
        goals_completed=goals_completed,
        goals_created_7d=goals_created_7d,
        goals_created_30d=goals_created_30d,
        goals_avg_progress_pct=goals_avg_progress,
        goals_sum_saved=goals_sum_saved,
        goals_users_count=goals_users_count,
        balance_sum=balance_sum,
        balance_avg=balance_avg,
        balance_negative_users=balance_negative_users,
        users_with_tx_month=users_with_tx_month,
        users_with_goals_pct=users_with_goals_pct,
        goals_avg_per_user=goals_avg_per_user,
    )


USERS_PAGE_SIZE = 10


@dataclass(frozen=True)
class AdminUserRow:
    user_id: int
    username: str | None
    first_name: str | None
    join_date: datetime
    total_balance: Decimal
    tx_count: int


@dataclass(frozen=True)
class AdminUserDetail:
    user_id: int
    username: str | None
    first_name: str | None
    join_date: datetime
    utc_offset_minutes: int | None
    welcome_seen: bool
    total_balance: Decimal
    tx_count: int
    goals_count: int
    goals_active: int


async def count_users(pool: asyncpg.Pool) -> int:
    return await pool.fetchval("SELECT COUNT(*)::int FROM users")


async def list_users_page(
    pool: asyncpg.Pool, page: int, *, page_size: int = USERS_PAGE_SIZE
) -> list[AdminUserRow]:
    page = max(0, page)
    offset = page * page_size
    rows = await pool.fetch(
        """
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            u.join_date,
            u.total_balance,
            COUNT(t.id)::int AS tx_count
        FROM users u
        LEFT JOIN transactions t ON t.user_id = u.user_id
        GROUP BY u.user_id, u.username, u.first_name, u.join_date, u.total_balance
        ORDER BY u.join_date DESC
        LIMIT $1 OFFSET $2
        """,
        page_size,
        offset,
    )
    return [
        AdminUserRow(
            user_id=row["user_id"],
            username=row["username"],
            first_name=row["first_name"],
            join_date=row["join_date"],
            total_balance=Decimal(row["total_balance"]),
            tx_count=row["tx_count"],
        )
        for row in rows
    ]


async def get_user_by_id(pool: asyncpg.Pool, user_id: int) -> AdminUserDetail | None:
    row = await pool.fetchrow(
        """
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            u.join_date,
            u.utc_offset_minutes,
            u.welcome_seen,
            u.total_balance,
            COUNT(DISTINCT t.id)::int AS tx_count,
            COUNT(DISTINCT g.id)::int AS goals_count,
            COUNT(DISTINCT g.id) FILTER (WHERE g.is_completed = FALSE)::int AS goals_active
        FROM users u
        LEFT JOIN transactions t ON t.user_id = u.user_id
        LEFT JOIN financial_goals g ON g.user_id = u.user_id
        WHERE u.user_id = $1
        GROUP BY u.user_id, u.username, u.first_name, u.join_date,
                 u.utc_offset_minutes, u.welcome_seen, u.total_balance
        """,
        user_id,
    )
    if row is None:
        return None
    return _row_to_user_detail(row)


async def find_user_by_username(
    pool: asyncpg.Pool, username: str
) -> AdminUserDetail | None:
    normalized = username.lstrip("@").lower()
    if not normalized:
        return None
    row = await pool.fetchrow(
        """
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            u.join_date,
            u.utc_offset_minutes,
            u.welcome_seen,
            u.total_balance,
            COUNT(DISTINCT t.id)::int AS tx_count,
            COUNT(DISTINCT g.id)::int AS goals_count,
            COUNT(DISTINCT g.id) FILTER (WHERE g.is_completed = FALSE)::int AS goals_active
        FROM users u
        LEFT JOIN transactions t ON t.user_id = u.user_id
        LEFT JOIN financial_goals g ON g.user_id = u.user_id
        WHERE LOWER(u.username) = $1
        GROUP BY u.user_id, u.username, u.first_name, u.join_date,
                 u.utc_offset_minutes, u.welcome_seen, u.total_balance
        """,
        normalized,
    )
    if row is None:
        return None
    return _row_to_user_detail(row)


def _row_to_user_detail(row: asyncpg.Record) -> AdminUserDetail:
    return AdminUserDetail(
        user_id=row["user_id"],
        username=row["username"],
        first_name=row["first_name"],
        join_date=row["join_date"],
        utc_offset_minutes=row["utc_offset_minutes"],
        welcome_seen=bool(row["welcome_seen"]),
        total_balance=Decimal(row["total_balance"]),
        tx_count=row["tx_count"],
        goals_count=row["goals_count"],
        goals_active=row["goals_active"],
    )
