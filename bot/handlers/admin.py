from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.config import Settings
from bot.db.admin_queries import PERIOD_LABELS, fetch_admin_dashboard
from bot.db.pool import get_pool
from bot.handlers.screen import replace_screen_callback
from bot.services.screen_context import KB_ADMIN_PANEL
from bot.keyboards.inline import (
    ADMIN_PERIOD_PREFIX,
    ADMIN_REFRESH_PREFIX,
    CB_ADMIN,
    admin_panel_keyboard,
)
from bot.services.admin_access import is_admin
from bot.services.admin_stats import format_admin_dashboard
from bot.texts.admin import ADMIN_ACCESS_DENIED

router = Router(name="admin")

DEFAULT_PERIOD = "30d"


def _parse_period(raw: str) -> str:
    return raw if raw in PERIOD_LABELS else DEFAULT_PERIOD


async def _show_admin_dashboard(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    period: str,
) -> None:
    pool = get_pool()
    stats = await fetch_admin_dashboard(pool, settings.timezone, period)
    text = format_admin_dashboard(stats)
    await state.set_state(None)
    await state.update_data(admin_period=period)
    await replace_screen_callback(
        callback,
        text,
        reply_markup=admin_panel_keyboard(period),
        state=state,
        keyboard_kind=KB_ADMIN_PANEL,
    )


@router.callback_query(F.data == CB_ADMIN)
async def open_admin_panel(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, settings.admin_ids):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    await callback.answer()
    await _show_admin_dashboard(callback, state, settings, DEFAULT_PERIOD)


@router.callback_query(F.data.startswith(ADMIN_PERIOD_PREFIX))
async def admin_change_period(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, settings.admin_ids):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    period = _parse_period((callback.data or "").removeprefix(ADMIN_PERIOD_PREFIX))
    await callback.answer()
    await _show_admin_dashboard(callback, state, settings, period)


@router.callback_query(F.data.startswith(ADMIN_REFRESH_PREFIX))
async def admin_refresh_stats(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, settings.admin_ids):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    period = _parse_period((callback.data or "").removeprefix(ADMIN_REFRESH_PREFIX))
    await callback.answer("Обновлено")
    await _show_admin_dashboard(callback, state, settings, period)
