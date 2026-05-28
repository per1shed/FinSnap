"""Отмена текущего шага ввода (❌ Отмена)."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.config import Settings
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.goals import _show_goal_detail, _show_goals_list
from bot.handlers.menu_helpers import show_main_menu
from bot.handlers.screen import clear_wrong_input_notice
from bot.handlers.welcome import TIMEZONE_RECONFIGURE_KEY, show_welcome
from bot.keyboards.inline import CB_CANCEL
from bot.services.user_timezone import describe_timezone_human
from bot.states.goal import GoalStates
from bot.states.onboarding import OnboardingStates
from bot.states.transaction import TransactionStates

router = Router(name="cancel")


@router.callback_query(F.data == CB_CANCEL)
async def cancel_current_step(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    current = await state.get_state()
    data = await state.get_data()
    user_id = callback.from_user.id

    await clear_wrong_input_notice(callback.bot, state)
    await callback.answer()

    if current == OnboardingStates.waiting_time.state:
        if not data.get(TIMEZONE_RECONFIGURE_KEY):
            return
        pool = get_pool()
        offset = await queries.get_user_utc_offset(pool, user_id)
        await state.set_state(None)
        await state.update_data(**{TIMEZONE_RECONFIGURE_KEY: False})
        timezone_note = describe_timezone_human(offset) if offset is not None else ""
        await show_welcome(callback, state, timezone_note=timezone_note)
        return

    if current == TransactionStates.waiting_input.state:
        await state.set_state(None)
        await show_main_menu(callback, settings, state)
        return

    if current in (
        GoalStates.waiting_title.state,
        GoalStates.waiting_target.state,
    ):
        await state.set_state(None)
        await _show_goals_list(callback, state, user_id)
        return

    if current == GoalStates.waiting_deposit.state:
        goal_id = data.get("goal_id")
        await state.set_state(None)
        if goal_id is not None:
            await _show_goal_detail(callback, state, int(goal_id), user_id)
        else:
            await _show_goals_list(callback, state, user_id)
        return
