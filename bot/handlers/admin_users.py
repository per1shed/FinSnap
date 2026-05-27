import math

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db.admin_queries import USERS_PAGE_SIZE, count_users, find_user_by_username, get_user_by_id, list_users_page
from bot.db.pool import get_pool
from bot.handlers.admin import DEFAULT_PERIOD, _parse_period, _show_admin_dashboard
from bot.handlers.fsm_reprompt import (
    KB_ADMIN_SEARCH,
    reprompt_current_step,
    show_fsm_step_callback,
)
from bot.handlers.screen import replace_screen_callback, replace_screen_from_message
from bot.keyboards.inline import (
    ADMIN_BACK_PREFIX,
    ADMIN_USERS_FIND,
    ADMIN_USERS_PAGE_PREFIX,
    admin_user_detail_keyboard,
    admin_user_search_keyboard,
    admin_users_keyboard,
)
from bot.services.admin_access import is_admin
from bot.services.admin_users_format import format_user_detail, format_users_list
from bot.states.admin import AdminStates
from bot.texts.admin import (
    ADMIN_ACCESS_DENIED,
    ADMIN_INVALID_SEARCH,
    ADMIN_USER_NOT_FOUND,
    ADMIN_USERS_SEARCH_PROMPT,
)

router = Router(name="admin_users")


def _is_admin(user_id: int, settings: Settings) -> bool:
    return is_admin(user_id, settings.admin_ids)


async def _show_users_list(
    target: CallbackQuery | Message,
    state: FSMContext,
    page: int,
) -> None:
    pool = get_pool()
    total_users = await count_users(pool)
    total_pages = max(1, math.ceil(total_users / USERS_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))

    users = await list_users_page(pool, page)
    text = format_users_list(users, page=page, total_users=total_users)
    data = await state.get_data()
    admin_period = data.get("admin_period", DEFAULT_PERIOD)
    keyboard = admin_users_keyboard(page, total_pages, admin_period=admin_period)

    await state.update_data(admin_list_page=page)
    await state.set_state(None)

    if isinstance(target, CallbackQuery):
        await replace_screen_callback(target, text, reply_markup=keyboard, state=state)
    else:
        await replace_screen_from_message(
            target, text, reply_markup=keyboard, state=state
        )


def _parse_search_query(text: str) -> tuple[str, int | str] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    cleaned = raw.lstrip("@")
    if cleaned.isdigit():
        return ("id", int(cleaned))
    if cleaned:
        return ("username", cleaned.lower())
    return None


@router.callback_query(F.data.startswith(ADMIN_USERS_PAGE_PREFIX))
async def admin_users_page(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    suffix = (callback.data or "").removeprefix(ADMIN_USERS_PAGE_PREFIX)
    try:
        page = int(suffix)
    except ValueError:
        page = 0

    await callback.answer()
    await _show_users_list(callback, state, page)


@router.callback_query(F.data == ADMIN_USERS_FIND)
async def admin_users_find_start(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    data = await state.get_data()
    list_page = data.get("admin_list_page", 0)

    await state.set_state(AdminStates.waiting_user_search)
    await callback.answer()
    await show_fsm_step_callback(
        callback,
        state,
        ADMIN_USERS_SEARCH_PROMPT,
        reply_markup=admin_user_search_keyboard(list_page=list_page),
        keyboard_kind=KB_ADMIN_SEARCH,
    )


@router.message(AdminStates.waiting_user_search)
async def admin_users_find_process(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(message.from_user.id, settings):
        return

    parsed = _parse_search_query(message.text or "")
    if parsed is None:
        await reprompt_current_step(
            message, state, settings, detail=ADMIN_INVALID_SEARCH
        )
        return

    pool = get_pool()
    kind, value = parsed
    if kind == "id":
        user = await get_user_by_id(pool, int(value))
    else:
        user = await find_user_by_username(pool, str(value))

    data = await state.get_data()
    list_page = data.get("admin_list_page", 0)

    if user is None:
        await reprompt_current_step(
            message, state, settings, detail=ADMIN_USER_NOT_FOUND
        )
        return

    await state.set_state(None)
    await replace_screen_from_message(
        message,
        format_user_detail(user),
        reply_markup=admin_user_detail_keyboard(list_page=list_page),
        state=state,
        delete_user_message=True,
    )


@router.callback_query(F.data.startswith(ADMIN_BACK_PREFIX))
async def admin_back_to_dashboard(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    period = _parse_period((callback.data or "").removeprefix(ADMIN_BACK_PREFIX))
    await callback.answer()
    await _show_admin_dashboard(callback, state, settings, period)
