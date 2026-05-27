from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.menu_helpers import show_main_menu
from bot.handlers.fsm_reprompt import KB_NONE, show_fsm_step_message
from bot.handlers.welcome import show_welcome
from bot.handlers.screen import (
    SCREEN_CHAT_ID_KEY,
    SCREEN_MESSAGE_ID_KEY,
    delete_screen,
    replace_screen_from_message,
)
from bot.keyboards.inline import CB_BACK_MENU
from bot.states.onboarding import OnboardingStates
from bot.texts.messages import TIMEZONE_PROMPT

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings: Settings) -> None:
    data = await state.get_data()
    chat_id = data.get(SCREEN_CHAT_ID_KEY)
    message_id = data.get(SCREEN_MESSAGE_ID_KEY)
    await state.clear()

    pool = get_pool()
    user_id = message.from_user.id
    await queries.ensure_user(pool, user_id)

    await delete_screen(message.bot, chat_id, message_id)

    offset = await queries.get_user_utc_offset(pool, user_id)
    if offset is None:
        await state.set_state(OnboardingStates.waiting_time)
        await show_fsm_step_message(
            message, state, TIMEZONE_PROMPT, keyboard_kind=KB_NONE
        )
        return

    if not await queries.has_seen_welcome(pool, user_id):
        await show_welcome(message, state)
        return

    await show_main_menu(message, settings, state)


@router.callback_query(F.data == CB_BACK_MENU)
async def back_to_menu(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await state.set_state(None)
    await show_main_menu(callback, settings, state)
