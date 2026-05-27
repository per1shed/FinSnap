from datetime import datetime

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.user_tz import resolve_user_tz
from bot.handlers.screen import replace_screen_callback, replace_screen_from_message
from bot.keyboards.inline import main_menu_keyboard
from bot.services.admin_access import is_admin
from bot.services.screen_context import KB_MAIN_MENU, MENU_SHOW_ADMIN_KEY
from bot.db import goals_queries
from bot.services.goals_format import format_goals_menu_hint
from bot.texts.messages import main_menu_text


async def build_main_menu_payload(user_id: int, settings: Settings) -> tuple[str, object]:
    pool = get_pool()
    await queries.ensure_user(pool, user_id)
    user_tz = await resolve_user_tz(pool, user_id, settings)
    now = datetime.now(user_tz)
    income, expense = await queries.get_month_summary(pool, user_id, now, user_tz)
    total_balance = await queries.get_total_balance(pool, user_id)
    active_goals = await goals_queries.list_active_goals(pool, user_id, limit=5)
    goals_hint = format_goals_menu_hint(active_goals)
    local = now.astimezone(user_tz)
    text = main_menu_text(
        income, expense, local.month, local.year, total_balance, goals_hint
    )
    keyboard = main_menu_keyboard(show_admin=is_admin(user_id, settings.admin_ids))
    return text, keyboard


async def show_main_menu(
    target: Message | CallbackQuery,
    settings: Settings,
    state: FSMContext | None = None,
) -> None:
    user_id = target.from_user.id
    text, keyboard = await build_main_menu_payload(user_id, settings)
    show_admin = is_admin(user_id, settings.admin_ids)
    screen_extra = {MENU_SHOW_ADMIN_KEY: show_admin}

    if isinstance(target, CallbackQuery):
        await replace_screen_callback(
            target,
            text,
            reply_markup=keyboard,
            state=state,
            keyboard_kind=KB_MAIN_MENU,
            **screen_extra,
        )
    else:
        await replace_screen_from_message(
            target,
            text,
            reply_markup=keyboard,
            state=state,
            keyboard_kind=KB_MAIN_MENU,
            **screen_extra,
        )
