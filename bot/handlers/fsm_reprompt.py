"""Повтор текущего шага при неверном вводе."""

from aiogram import F, Router
from aiogram.filters import BaseFilter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.config import Settings
from bot.constants import TransactionType
from bot.handlers.screen import (
    clear_wrong_input_notice,
    delete_message_safe,
    replace_screen_callback,
    replace_screen_from_message,
    resend_screen_after_notice,
    store_wrong_input_notice,
)
from bot.keyboards.inline import admin_user_search_keyboard, category_keyboard
from bot.services.screen_context import (
    KB_ADMIN_SEARCH,
    KB_CATEGORY_EXPENSE,
    KB_CATEGORY_INCOME,
    KB_NONE,
    SCREEN_IS_PHOTO,
    is_text_entry_state,
    restored_step,
)
from bot.states.admin import AdminStates
from bot.states.goal import GoalStates
from bot.states.onboarding import OnboardingStates
from bot.states.transaction import TransactionStates
from bot.texts.admin import ADMIN_USERS_SEARCH_PROMPT
from bot.texts.goals import (
    GOAL_DEPOSIT_PROMPT,
    GOAL_TARGET_PROMPT,
    GOAL_TITLE_PROMPT,
)
from bot.texts.messages import (
    TIMEZONE_PROMPT,
    WRONG_INPUT_NEED_TEXT,
    category_prompt,
    wrong_input_notice_text,
)

router = Router(name="fsm_reprompt")

# Re-export for handlers
__all__ = [
    "KB_NONE",
    "KB_ADMIN_SEARCH",
    "KB_CATEGORY_EXPENSE",
    "KB_CATEGORY_INCOME",
    "reprompt_current_step",
    "show_fsm_step_callback",
    "show_fsm_step_message",
]

_STATES_EXPECT_BUTTONS = (TransactionStates.choosing_category,)

_TEXT_ENTRY_STATES = (
    OnboardingStates.waiting_time,
    TransactionStates.waiting_input,
    GoalStates.waiting_title,
    GoalStates.waiting_target,
    GoalStates.waiting_deposit,
    AdminStates.waiting_user_search,
)


class ExpectsButtonInput(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        if not data.get("screen_expects_buttons"):
            return False
        return not is_text_entry_state(await state.get_state())


def _fallback_step(
    state_name: str | None, data: dict
) -> tuple[str, InlineKeyboardMarkup | None]:
    if state_name == OnboardingStates.waiting_time.state:
        return TIMEZONE_PROMPT, None

    if state_name == TransactionStates.choosing_category.state:
        tx_type = TransactionType(data.get("tx_type", TransactionType.EXPENSE.value))
        if tx_type == TransactionType.INCOME:
            return "Выберите категорию дохода:", category_keyboard(TransactionType.INCOME)
        return "Выберите категорию расхода:", category_keyboard(TransactionType.EXPENSE)

    if state_name == TransactionStates.waiting_input.state:
        tx_type = TransactionType(data["tx_type"])
        label = "Расход" if tx_type == TransactionType.EXPENSE else "Доход"
        return category_prompt(label, data["category_label"]), None

    if state_name == GoalStates.waiting_title.state:
        return GOAL_TITLE_PROMPT, None

    if state_name == GoalStates.waiting_target.state:
        return GOAL_TARGET_PROMPT.format(title=data.get("goal_title", "—")), None

    if state_name == GoalStates.waiting_deposit.state:
        title = data.get("goal_title") or "цель"
        return GOAL_DEPOSIT_PROMPT.format(title=title), None

    if state_name == AdminStates.waiting_user_search.state:
        return (
            ADMIN_USERS_SEARCH_PROMPT,
            admin_user_search_keyboard(list_page=data.get("admin_list_page", 0)),
        )

    return "Повторите ввод.", None


async def _resolve_step(
    state: FSMContext, *, user_id: int, settings: Settings
) -> tuple[str, InlineKeyboardMarkup | None]:
    step_text, keyboard = await restored_step(state, user_id=user_id, settings=settings)
    if step_text != "Повторите ввод.":
        return step_text, keyboard
    data = await state.get_data()
    return _fallback_step(await state.get_state(), data)


async def show_fsm_step_callback(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    keyboard_kind: str = KB_NONE,
) -> Message:
    return await replace_screen_callback(
        callback,
        text,
        reply_markup=reply_markup,
        state=state,
        keyboard_kind=keyboard_kind,
    )


async def show_fsm_step_message(
    message: Message,
    state: FSMContext,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    keyboard_kind: str = KB_NONE,
    delete_user_message: bool = False,
) -> Message:
    return await replace_screen_from_message(
        message,
        text,
        reply_markup=reply_markup,
        state=state,
        delete_user_message=delete_user_message,
        keyboard_kind=keyboard_kind,
    )


async def _wrong_input_flow(
    message: Message,
    state: FSMContext,
    settings: Settings,
    *,
    detail: str | None = None,
) -> None:
    await delete_message_safe(message)
    await clear_wrong_input_notice(message.bot, state)
    notice = await message.answer(wrong_input_notice_text(detail=detail))
    await store_wrong_input_notice(state, notice)
    data = await state.get_data()
    if data.get(SCREEN_IS_PHOTO):
        return
    step_text, keyboard = await _resolve_step(
        state, user_id=message.from_user.id, settings=settings
    )
    await resend_screen_after_notice(
        message, step_text, reply_markup=keyboard, state=state
    )


async def reprompt_current_step(
    message: Message,
    state: FSMContext,
    settings: Settings,
    *,
    detail: str | None = None,
) -> None:
    await _wrong_input_flow(message, state, settings, detail=detail)


@router.message(ExpectsButtonInput(), F.text)
async def unexpected_text_on_button_screen(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    await _wrong_input_flow(message, state, settings)


@router.message(ExpectsButtonInput(), ~F.text)
async def unexpected_media_on_button_screen(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    await _wrong_input_flow(message, state, settings, detail=WRONG_INPUT_NEED_TEXT)


@router.message(StateFilter(*_STATES_EXPECT_BUTTONS), F.text)
async def text_instead_of_category_button(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    await reprompt_current_step(message, state, settings)


@router.message(StateFilter(*_STATES_EXPECT_BUTTONS), ~F.text)
async def media_instead_of_category_button(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    await reprompt_current_step(message, state, settings, detail=WRONG_INPUT_NEED_TEXT)


@router.message(StateFilter(*_TEXT_ENTRY_STATES), ~F.text)
async def media_during_text_entry(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    await reprompt_current_step(message, state, settings, detail=WRONG_INPUT_NEED_TEXT)
