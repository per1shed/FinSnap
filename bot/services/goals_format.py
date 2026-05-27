from decimal import Decimal

from bot.db.goals_queries import FinancialGoal
from bot.texts.messages import format_money


def progress_percent(saved: Decimal, target: Decimal) -> float:
    if target <= 0:
        return 0.0
    return float(min(saved / target * 100, Decimal("100")))


def progress_bar(saved: Decimal, target: Decimal, width: int = 12) -> str:
    pct = progress_percent(saved, target)
    filled = int(round(width * pct / 100))
    return "█" * filled + "░" * (width - filled)


def format_goal_caption(goal: FinancialGoal, *, header: str = "") -> str:
    """Подпись к круговой диаграмме цели."""
    pct = progress_percent(goal.saved_amount, goal.target_amount)
    remaining = max(goal.target_amount - goal.saved_amount, Decimal("0"))

    if goal.is_completed:
        status = "🎉 <b>Цель достигнута!</b>"
    else:
        status = f"Прогресс: <b>{pct:.0f}%</b>"

    body = (
        f"<b>{goal.title}</b>\n"
        f"Накоплено: <b>{format_money(goal.saved_amount)}</b> "
        f"из <b>{format_money(goal.target_amount)}</b>\n"
        f"Осталось: <b>{format_money(remaining)}</b>\n\n"
        f"{status}"
    )
    if header:
        return f"{header}\n\n{body}"
    return body


def format_goal_detail(goal: FinancialGoal) -> str:
    return format_goal_caption(goal)


def format_goals_list_caption(goals: list[FinancialGoal]) -> str:
    if not goals:
        return (
            "<b>🎯 Финансовые цели</b>\n\n"
            "Пока целей нет. Создайте первую — например, "
            "«Накопить на квартиру»."
        )

    lines = [
        "<b>🎯 Финансовые цели</b>\n",
        "Нажмите на цель, чтобы открыть подробную диаграмму.\n",
    ]
    for goal in goals:
        pct = progress_percent(goal.saved_amount, goal.target_amount)
        lines.append(
            f"• <b>{goal.title}</b> — {format_money(goal.saved_amount)} / "
            f"{format_money(goal.target_amount)} ({pct:.0f}%)"
        )
    return "\n".join(lines)


def format_goals_list(goals: list[FinancialGoal]) -> str:
    if not goals:
        return (
            "<b>🎯 Финансовые цели</b>\n\n"
            "Пока целей нет. Создайте первую — например, "
            "«Накопить на квартиру»."
        )

    lines = ["<b>🎯 Финансовые цели</b>\n"]
    for goal in goals:
        pct = progress_percent(goal.saved_amount, goal.target_amount)
        lines.append(
            f"• <b>{goal.title}</b> — {format_money(goal.saved_amount)} / "
            f"{format_money(goal.target_amount)} ({pct:.0f}%)"
        )
    return "\n".join(lines)


def format_goals_menu_hint(goals: list[FinancialGoal]) -> str:
    if not goals:
        return ""
    top = goals[0]
    pct = progress_percent(top.saved_amount, top.target_amount)
    if len(goals) == 1:
        return (
            f"\n<b>Цель:</b> {top.title} — {pct:.0f}% "
            f"({format_money(top.saved_amount)} / {format_money(top.target_amount)})"
        )
    return (
        f"\n<b>Цели:</b> {len(goals)} активных · ближайшая «{top.title}» — {pct:.0f}%"
    )
