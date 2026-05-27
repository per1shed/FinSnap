from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.menu_helpers import show_main_menu
from bot.handlers.screen import replace_screen_callback, replace_screen_from_message
from bot.keyboards.inline import CB_WELCOME_DONE, welcome_keyboard
from bot.services.screen_context import KB_WELCOME
from bot.texts.messages import welcome_screen_text

router = Router(name="welcome")


async def show_welcome(
    target: Message | CallbackQuery,
    state: FSMContext | None,
    *,
    timezone_note: str = "",
) -> None:
    text = welcome_screen_text(timezone_note=timezone_note)
    keyboard = welcome_keyboard()
    if isinstance(target, CallbackQuery):
        await replace_screen_callback(
            target, text, reply_markup=keyboard, state=state, keyboard_kind=KB_WELCOME
        )
    else:
        await replace_screen_from_message(
            target, text, reply_markup=keyboard, state=state, keyboard_kind=KB_WELCOME
        )


@router.callback_query(F.data == CB_WELCOME_DONE)
async def welcome_done(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    pool = get_pool()
    await queries.mark_welcome_seen(pool, callback.from_user.id)
    await state.set_state(None)
    await show_main_menu(callback, settings, state)
