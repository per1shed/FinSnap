from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import asyncpg

MAX_ACTIVE_GOALS = 10


@dataclass
class FinancialGoal:
    id: int
    user_id: int
    title: str
    target_amount: Decimal
    saved_amount: Decimal
    is_completed: bool
    created_at: datetime


def _row_to_goal(row: asyncpg.Record) -> FinancialGoal:
    return FinancialGoal(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        target_amount=Decimal(row["target_amount"]),
        saved_amount=Decimal(row["saved_amount"]),
        is_completed=row["is_completed"],
        created_at=row["created_at"],
    )


async def count_active_goals(pool: asyncpg.Pool, user_id: int) -> int:
    val = await pool.fetchval(
        """
        SELECT COUNT(*) FROM financial_goals
        WHERE user_id = $1 AND is_completed = FALSE
        """,
        user_id,
    )
    return int(val or 0)


async def list_active_goals(
    pool: asyncpg.Pool, user_id: int, *, limit: int = 10
) -> list[FinancialGoal]:
    rows = await pool.fetch(
        """
        SELECT id, user_id, title, target_amount, saved_amount, is_completed, created_at
        FROM financial_goals
        WHERE user_id = $1 AND is_completed = FALSE
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return [_row_to_goal(row) for row in rows]


async def get_goal(
    pool: asyncpg.Pool, goal_id: int, user_id: int
) -> FinancialGoal | None:
    row = await pool.fetchrow(
        """
        SELECT id, user_id, title, target_amount, saved_amount, is_completed, created_at
        FROM financial_goals
        WHERE id = $1 AND user_id = $2
        """,
        goal_id,
        user_id,
    )
    if row is None:
        return None
    return _row_to_goal(row)


async def create_goal(
    pool: asyncpg.Pool, user_id: int, title: str, target_amount: Decimal
) -> FinancialGoal:
    row = await pool.fetchrow(
        """
        INSERT INTO financial_goals (user_id, title, target_amount)
        VALUES ($1, $2, $3)
        RETURNING id, user_id, title, target_amount, saved_amount, is_completed, created_at
        """,
        user_id,
        title.strip()[:128],
        target_amount,
    )
    return _row_to_goal(row)


async def add_to_goal(
    pool: asyncpg.Pool, goal_id: int, user_id: int, amount: Decimal
) -> FinancialGoal | None:
    row = await pool.fetchrow(
        """
        UPDATE financial_goals
        SET
            saved_amount = saved_amount + $3,
            is_completed = CASE
                WHEN saved_amount + $3 >= target_amount THEN TRUE
                ELSE is_completed
            END
        WHERE id = $1 AND user_id = $2 AND is_completed = FALSE
        RETURNING id, user_id, title, target_amount, saved_amount, is_completed, created_at
        """,
        goal_id,
        user_id,
        amount,
    )
    if row is None:
        return None
    return _row_to_goal(row)


async def delete_goal(pool: asyncpg.Pool, goal_id: int, user_id: int) -> bool:
    result = await pool.execute(
        "DELETE FROM financial_goals WHERE id = $1 AND user_id = $2",
        goal_id,
        user_id,
    )
    return result.endswith("1")
