from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.fsm_reprompt import show_fsm_step_callback
from bot.handlers.menu_helpers import show_main_menu
from bot.handlers.screen import replace_screen_callback, replace_screen_from_message
from bot.keyboards.inline import (
    CB_BACK_WELCOME,
    CB_CHANGE_TZ,
    CB_WELCOME_DONE,
    timezone_change_keyboard,
    welcome_keyboard,
)
from bot.services.screen_context import KB_TIMEZONE_CHANGE, KB_WELCOME
from bot.services.user_timezone import describe_timezone_human, format_utc_offset
from bot.states.onboarding import OnboardingStates
from bot.texts.messages import timezone_change_prompt, welcome_screen_text

router = Router(name="welcome")

TIMEZONE_RECONFIGURE_KEY = "timezone_reconfigure"


async def show_welcome(
    target: Message | CallbackQuery,
    state: FSMContext | None,
    *,
    timezone_note: str = "",
) -> None:
    text = welcome_screen_text(timezone_note=timezone_note)
    keyboard = welcome_keyboard(show_change_tz=bool(timezone_note))
    if isinstance(target, CallbackQuery):
        await replace_screen_callback(
            target, text, reply_markup=keyboard, state=state, keyboard_kind=KB_WELCOME
        )
    else:
        await replace_screen_from_message(
            target, text, reply_markup=keyboard, state=state, keyboard_kind=KB_WELCOME
        )


@router.callback_query(F.data == CB_CHANGE_TZ)
async def start_change_timezone(
    callback: CallbackQuery, state: FSMContext
) -> None:
    pool = get_pool()
    user_id = callback.from_user.id
    offset = await queries.get_user_utc_offset(pool, user_id)
    current_label = format_utc_offset(offset) if offset is not None else None

    await state.set_state(OnboardingStates.waiting_time)
    await state.update_data(**{TIMEZONE_RECONFIGURE_KEY: True})
    await show_fsm_step_callback(
        callback,
        state,
        timezone_change_prompt(current_label),
        reply_markup=timezone_change_keyboard(),
        keyboard_kind=KB_TIMEZONE_CHANGE,
    )


@router.callback_query(F.data == CB_BACK_WELCOME)
async def back_to_welcome_from_timezone(
    callback: CallbackQuery, state: FSMContext,
) -> None:
    if await state.get_state() != OnboardingStates.waiting_time.state:
        await callback.answer()
        return

    data = await state.get_data()
    if not data.get(TIMEZONE_RECONFIGURE_KEY):
        await callback.answer()
        return

    pool = get_pool()
    offset = await queries.get_user_utc_offset(pool, callback.from_user.id)
    await state.set_state(None)
    await state.update_data(**{TIMEZONE_RECONFIGURE_KEY: False})

    timezone_note = describe_timezone_human(offset) if offset is not None else ""
    await show_welcome(callback, state, timezone_note=timezone_note)


@router.callback_query(F.data == CB_WELCOME_DONE)
async def welcome_done(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    pool = get_pool()
    await queries.mark_welcome_seen(pool, callback.from_user.id)
    await state.set_state(None)
    await state.update_data(**{TIMEZONE_RECONFIGURE_KEY: False})
    await show_main_menu(callback, settings, state)
