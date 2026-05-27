import math
from datetime import datetime

from bot.db.admin_queries import USERS_PAGE_SIZE, AdminUserDetail, AdminUserRow
from bot.services.user_timezone import describe_timezone_human
from bot.texts.messages import format_money


def _format_username(username: str | None) -> str:
    if username:
        return f"@{username}"
    return "—"


def format_users_list(
    users: list[AdminUserRow],
    *,
    page: int,
    total_users: int,
) -> str:
    total_pages = max(1, math.ceil(total_users / USERS_PAGE_SIZE))
    page = min(page, total_pages - 1)

    lines = [
        "👥 <b>Пользователи</b>",
        f"Страница <b>{page + 1}</b> из <b>{total_pages}</b> "
        f"(всего <b>{total_users}</b>)\n",
    ]

    if not users:
        lines.append("<i>На этой странице никого нет.</i>")
    else:
        start_num = page * USERS_PAGE_SIZE + 1
        for i, user in enumerate(users, start=start_num):
            name = user.first_name or "—"
            label = _format_username(user.username)
            if label == "—":
                label = f"ID <code>{user.user_id}</code>"
            lines.append(
                f"<b>{i}.</b> {label} · {name} <b>{user.tx_count} оп</b>"
            )

    return "\n".join(lines)


def format_user_detail(user: AdminUserDetail) -> str:
    join = user.join_date
    join_str = join.strftime("%d.%m.%Y %H:%M") if isinstance(join, datetime) else "—"
    tz = (
        describe_timezone_human(user.utc_offset_minutes)
        if user.utc_offset_minutes is not None
        else "не задан"
    )
    welcome = "да" if user.welcome_seen else "нет"

    return (
        f"👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{user.user_id}</code>\n"
        f"Username: {_format_username(user.username)}\n"
        f"Имя: <b>{user.first_name or '—'}</b>\n"
        f"Регистрация: <b>{join_str}</b>\n"
        f"Часовой пояс: <b>{tz}</b>\n"
        f"Ознакомление: <b>{welcome}</b>\n\n"
        f"Общий баланс: <b>{format_money(user.total_balance)}</b>\n"
        f"Операций: <b>{user.tx_count}</b>\n"
        f"Целей: <b>{user.goals_count}</b> "
        f"(активных: <b>{user.goals_active}</b>)"
    )
