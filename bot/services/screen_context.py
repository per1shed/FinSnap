"""Контекст текущего экрана для повтора шага при неверном вводе."""

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from bot.config import Settings
from bot.constants import TransactionType
from bot.db import goals_queries
from bot.db.pool import get_pool
from bot.keyboards.inline import (
    admin_panel_keyboard,
    admin_user_search_keyboard,
    back_to_menu_keyboard,
    category_keyboard,
    goals_list_keyboard,
    main_menu_keyboard,
    stats_kind_keyboard,
    stats_period_keyboard,
    stats_type_keyboard,
    timezone_change_keyboard,
    welcome_keyboard,
)
from bot.services.admin_access import is_admin

SCREEN_EXPECTS_BUTTONS = "screen_expects_buttons"
SCREEN_IS_PHOTO = "screen_is_photo"
FSM_STEP_TEXT_KEY = "fsm_step_text"
FSM_STEP_KEYBOARD_KEY = "fsm_step_keyboard"
MENU_SHOW_ADMIN_KEY = "menu_show_admin"

KB_NONE = "none"
KB_MAIN_MENU = "main_menu"
KB_ADMIN_SEARCH = "admin_search"
KB_CATEGORY_EXPENSE = "category_expense"
KB_CATEGORY_INCOME = "category_income"
KB_STATS_TYPE = "stats_type"
KB_STATS_KIND = "stats_kind"
KB_STATS_PERIOD = "stats_period"
KB_WELCOME = "welcome"
KB_ADMIN_PANEL = "admin_panel"
KB_GOALS_LIST = "goals_list"
KB_BACK_MENU = "back_menu"
KB_TIMEZONE_CHANGE = "timezone_change"

_TEXT_ENTRY_STATES = frozenset(
    {
        "OnboardingStates:waiting_time",
        "TransactionStates:waiting_input",
        "GoalStates:waiting_title",
        "GoalStates:waiting_target",
        "GoalStates:waiting_deposit",
        "AdminStates:waiting_user_search",
    }
)


async def tag_screen_step(
    state: FSMContext | None,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    keyboard_kind: str | None = None,
    **extra: object,
) -> None:
    if state is None:
        return
    payload: dict[str, object] = {FSM_STEP_TEXT_KEY: text, **extra}
    if reply_markup is not None:
        payload[SCREEN_EXPECTS_BUTTONS] = True
        if keyboard_kind:
            payload[FSM_STEP_KEYBOARD_KEY] = keyboard_kind
    else:
        payload[SCREEN_EXPECTS_BUTTONS] = False
    if "screen_is_photo" not in extra:
        payload[SCREEN_IS_PHOTO] = False
        if keyboard_kind is not None:
            payload[FSM_STEP_KEYBOARD_KEY] = keyboard_kind
    await state.update_data(**payload)


async def keyboard_for_kind(
    kind: str, data: dict, *, user_id: int, settings: Settings
) -> InlineKeyboardMarkup | None:
    if kind == KB_MAIN_MENU:
        show_admin = bool(data.get(MENU_SHOW_ADMIN_KEY, is_admin(user_id, settings.admin_ids)))
        return main_menu_keyboard(show_admin=show_admin)
    if kind == KB_ADMIN_SEARCH:
        return admin_user_search_keyboard(list_page=data.get("admin_list_page", 0))
    if kind == KB_CATEGORY_EXPENSE:
        return category_keyboard(TransactionType.EXPENSE)
    if kind == KB_CATEGORY_INCOME:
        return category_keyboard(TransactionType.INCOME)
    if kind == KB_STATS_TYPE:
        return stats_type_keyboard()
    if kind == KB_STATS_KIND:
        tx_type = TransactionType(data.get("stats_tx_type", TransactionType.EXPENSE.value))
        return stats_kind_keyboard(tx_type)
    if kind == KB_STATS_PERIOD:
        tx_type = TransactionType(data.get("stats_tx_type", TransactionType.EXPENSE.value))
        return stats_period_keyboard(tx_type)
    if kind == KB_WELCOME:
        return welcome_keyboard()
    if kind == KB_ADMIN_PANEL:
        period = data.get("admin_period", "30d")
        return admin_panel_keyboard(str(period))
    if kind == KB_GOALS_LIST:
        pool = get_pool()
        goals = await goals_queries.list_active_goals(pool, user_id)
        return goals_list_keyboard(goals)
    if kind == KB_BACK_MENU:
        return back_to_menu_keyboard()
    if kind == KB_TIMEZONE_CHANGE:
        return timezone_change_keyboard()
    return None


async def restored_step(
    state: FSMContext,
    *,
    user_id: int,
    settings: Settings,
) -> tuple[str, InlineKeyboardMarkup | None]:
    data = await state.get_data()
    stored_text = data.get(FSM_STEP_TEXT_KEY)
    if stored_text:
        kind = str(data.get(FSM_STEP_KEYBOARD_KEY, KB_NONE))
        keyboard = await keyboard_for_kind(kind, data, user_id=user_id, settings=settings)
        return str(stored_text), keyboard
    return "Повторите ввод.", None


def is_text_entry_state(state_name: str | None) -> bool:
    return state_name in _TEXT_ENTRY_STATES


def expects_button_screen(data: dict) -> bool:
    return bool(data.get(SCREEN_EXPECTS_BUTTONS))
