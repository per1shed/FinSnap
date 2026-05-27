from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Settings
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.welcome import show_welcome
from bot.handlers.fsm_reprompt import reprompt_current_step
from bot.handlers.screen import replace_screen_from_message
from bot.services.user_timezone import (
    compute_utc_offset_from_hour,
    describe_timezone_human,
    parse_hour_input,
)
from bot.states.onboarding import OnboardingStates
from bot.texts.messages import INVALID_TIME_TEXT, TIMEZONE_PROMPT

router = Router(name="onboarding")


@router.message(OnboardingStates.waiting_time)
async def process_user_time(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    hour = parse_hour_input(message.text or "")
    if hour is None:
        await reprompt_current_step(
            message, state, settings, detail=INVALID_TIME_TEXT
        )
        return

    offset = compute_utc_offset_from_hour(hour)
    pool = get_pool()
    await queries.set_user_utc_offset(pool, message.from_user.id, offset)

    await state.set_state(None)
    await message.delete()

    timezone_text = describe_timezone_human(offset)
    await show_welcome(message, state, timezone_note=timezone_text)
