from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constants import EXPENSE_CATEGORIES, INCOME_CATEGORIES, TransactionType
from bot.services.goals_format import progress_percent

CB_EXPENSE = "op:expense"
CB_INCOME = "op:income"
CB_STATS = "op:stats"
CB_GOALS = "op:goals"
CB_ADMIN = "op:admin"
ADMIN_PERIOD_PREFIX = "admin:p:"
ADMIN_REFRESH_PREFIX = "admin:refresh:"
ADMIN_USERS_PAGE_PREFIX = "admin:users:p:"
ADMIN_USERS_FIND = "admin:users:find"
ADMIN_BACK_PREFIX = "admin:back:"
CB_BACK_MENU = "nav:menu"
CB_CANCEL = "nav:cancel"
CB_WELCOME_DONE = "nav:welcome_done"
CB_CHANGE_TZ = "nav:change_tz"
CB_BACK_WELCOME = "nav:welcome_back"
CB_GOAL_NEW = "goal:new"
CB_GOAL_LIST = "goal:list"
CB_STATS_TYPE_EXPENSE = "stats_type:expense"
CB_STATS_TYPE_INCOME = "stats_type:income"
CB_STATS_KIND_EXPENSE_PIE = "stats_kind:expense:pie"
CB_STATS_KIND_EXPENSE_DAILY = "stats_kind:expense:daily"
CB_STATS_KIND_INCOME_PIE = "stats_kind:income:pie"
CB_STATS_KIND_INCOME_DAILY = "stats_kind:income:daily"
CB_STATS_EXPENSE_WEEK = "stats:expense:week"
CB_STATS_EXPENSE_MONTH = "stats:expense:month"
CB_STATS_INCOME_WEEK = "stats:income:week"
CB_STATS_INCOME_MONTH = "stats:income:month"


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=CB_CANCEL,
                )
            ]
        ]
    )


def timezone_change_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=CB_BACK_WELCOME,
                )
            ]
        ]
    )


def welcome_keyboard(*, show_change_tz: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if show_change_tz:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🕐 Сменить",
                    callback_data=CB_CHANGE_TZ,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="✅ Понятно, в меню",
                callback_data=CB_WELCOME_DONE,
                style="success",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard(*, show_admin: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="➖ Расход",
                callback_data=CB_EXPENSE,
                style="danger",
            ),
            InlineKeyboardButton(
                text="➕ Доход",
                callback_data=CB_INCOME,
                style="success",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data=CB_STATS,
                style="primary",
            ),
            InlineKeyboardButton(
                text="🎯 Цели",
                callback_data=CB_GOALS,
                style="primary",
            ),
        ],
    ]
    if show_admin:
        rows.append(
            [
                InlineKeyboardButton(
                    text="👑",
                    callback_data=CB_ADMIN,
                    style="primary",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _admin_period_label(key: str, active: str) -> str:
    labels = {
        "today": "Сегодня",
        "7d": "7 дн.",
        "30d": "30 дн.",
        "all": "Всё",
    }
    text = labels.get(key, key)
    return f"• {text}" if key == active else text


def admin_panel_keyboard(active_period: str = "30d") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_admin_period_label("today", active_period),
                    callback_data=f"{ADMIN_PERIOD_PREFIX}today",
                ),
                InlineKeyboardButton(
                    text=_admin_period_label("7d", active_period),
                    callback_data=f"{ADMIN_PERIOD_PREFIX}7d",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=_admin_period_label("30d", active_period),
                    callback_data=f"{ADMIN_PERIOD_PREFIX}30d",
                ),
                InlineKeyboardButton(
                    text=_admin_period_label("all", active_period),
                    callback_data=f"{ADMIN_PERIOD_PREFIX}all",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data=f"{ADMIN_REFRESH_PREFIX}{active_period}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data=f"{ADMIN_USERS_PAGE_PREFIX}0",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=CB_BACK_MENU)],
        ]
    )


def admin_users_keyboard(
    page: int, total_pages: int, *, admin_period: str = "30d"
) -> InlineKeyboardMarkup:
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"{ADMIN_USERS_PAGE_PREFIX}{page - 1}",
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data=f"{ADMIN_USERS_PAGE_PREFIX}{page}",
        )
    )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"{ADMIN_USERS_PAGE_PREFIX}{page + 1}",
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav_row,
            [
                InlineKeyboardButton(
                    text="🔍 Найти по ID / username",
                    callback_data=ADMIN_USERS_FIND,
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К админке",
                    callback_data=f"{ADMIN_BACK_PREFIX}{admin_period}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=CB_BACK_MENU)],
        ]
    )


def admin_user_search_keyboard(*, list_page: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ К списку",
                    callback_data=f"{ADMIN_USERS_PAGE_PREFIX}{list_page}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=CB_BACK_MENU)],
        ]
    )


def admin_user_detail_keyboard(*, list_page: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ К списку",
                    callback_data=f"{ADMIN_USERS_PAGE_PREFIX}{list_page}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔍 Новый поиск",
                    callback_data=ADMIN_USERS_FIND,
                )
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=CB_BACK_MENU)],
        ]
    )


def goals_list_keyboard(goals: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for goal in goals:
        pct = int(progress_percent(goal.saved_amount, goal.target_amount))
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{goal.title} ({pct}%)",
                    callback_data=f"goal:open:{goal.id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="➕ Новая цель", callback_data=CB_GOAL_NEW)]
    )
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data=CB_BACK_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def goal_detail_keyboard(goal_id: int, is_completed: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not is_completed:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💰 Пополнить",
                    callback_data=f"goal:deposit:{goal_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"goal:delete:{goal_id}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ К целям", callback_data=CB_GOAL_LIST)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def goal_delete_confirm_keyboard(goal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"goal:delete_confirm:{goal_id}",
                    style="danger",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"goal:open:{goal_id}",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ К целям", callback_data=CB_GOAL_LIST)],
        ]
    )


def category_keyboard(tx_type: TransactionType) -> InlineKeyboardMarkup:
    categories = (
        EXPENSE_CATEGORIES
        if tx_type == TransactionType.EXPENSE
        else INCOME_CATEGORIES
    )
    prefix = "cat:e" if tx_type == TransactionType.EXPENSE else "cat:i"
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in categories:
        row.append(
            InlineKeyboardButton(
                text=categories[key],
                callback_data=f"{prefix}:{key}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data=CB_BACK_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stats_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➖ Расходы",
                    callback_data=CB_STATS_TYPE_EXPENSE,
                    style="danger",
                ),
                InlineKeyboardButton(
                    text="➕ Доходы",
                    callback_data=CB_STATS_TYPE_INCOME,
                    style="success",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=CB_BACK_MENU)],
        ]
    )


def stats_period_keyboard(tx_type: TransactionType) -> InlineKeyboardMarkup:
    if tx_type == TransactionType.EXPENSE:
        week_cb = CB_STATS_EXPENSE_WEEK
        month_cb = CB_STATS_EXPENSE_MONTH
    else:
        week_cb = CB_STATS_INCOME_WEEK
        month_cb = CB_STATS_INCOME_MONTH

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="За неделю", callback_data=week_cb),
                InlineKeyboardButton(text="За месяц", callback_data=month_cb),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_STATS)],
        ]
    )


def stats_kind_keyboard(tx_type: TransactionType) -> InlineKeyboardMarkup:
    if tx_type == TransactionType.EXPENSE:
        pie_cb = CB_STATS_KIND_EXPENSE_PIE
        daily_cb = CB_STATS_KIND_EXPENSE_DAILY
    else:
        pie_cb = CB_STATS_KIND_INCOME_PIE
        daily_cb = CB_STATS_KIND_INCOME_DAILY

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Круговая по категориям", callback_data=pie_cb),
            ],
            [
                InlineKeyboardButton(
                    text="Гистограмма по дням (месяц)",
                    callback_data=daily_cb,
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_STATS)],
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Вернуться в меню", callback_data=CB_BACK_MENU)]
        ]
    )
