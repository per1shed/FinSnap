from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.services.screen_context import tag_screen_step

SCREEN_CHAT_ID_KEY = "screen_chat_id"
SCREEN_MESSAGE_ID_KEY = "screen_message_id"
NOTICE_CHAT_ID_KEY = "notice_chat_id"
NOTICE_MESSAGE_ID_KEY = "notice_message_id"


async def delete_message_safe(message: Message | None) -> None:
    if message is None:
        return
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def delete_screen(bot: Bot, chat_id: int | None, message_id: int | None) -> None:
    if chat_id is None or message_id is None:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        pass


async def store_wrong_input_notice(
    state: FSMContext | None, message: Message
) -> None:
    if state is None:
        return
    await state.update_data(
        **{
            NOTICE_CHAT_ID_KEY: message.chat.id,
            NOTICE_MESSAGE_ID_KEY: message.message_id,
        }
    )


async def clear_wrong_input_notice(bot: Bot, state: FSMContext | None) -> None:
    if state is None:
        return
    data = await state.get_data()
    await delete_screen(
        bot,
        data.get(NOTICE_CHAT_ID_KEY),
        data.get(NOTICE_MESSAGE_ID_KEY),
    )
    await state.update_data(
        **{NOTICE_CHAT_ID_KEY: None, NOTICE_MESSAGE_ID_KEY: None}
    )


async def delete_stored_screen(bot: Bot, state: FSMContext | None) -> None:
    if state is None:
        return
    data = await state.get_data()
    await delete_screen(
        bot,
        data.get(SCREEN_CHAT_ID_KEY),
        data.get(SCREEN_MESSAGE_ID_KEY),
    )


async def _store_screen(state: FSMContext | None, message: Message) -> None:
    if state is None:
        return
    await state.update_data(
        **{
            SCREEN_CHAT_ID_KEY: message.chat.id,
            SCREEN_MESSAGE_ID_KEY: message.message_id,
        }
    )


async def send_screen(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    state: FSMContext | None = None,
    remove_stored: bool = True,
    keyboard_kind: str | None = None,
    tag_step: bool = True,
    **screen_extra: object,
) -> Message:
    await clear_wrong_input_notice(bot, state)
    if remove_stored:
        await delete_stored_screen(bot, state)
    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    await _store_screen(state, sent)
    if tag_step:
        await tag_screen_step(
            state,
            text,
            reply_markup=reply_markup,
            keyboard_kind=keyboard_kind,
            **screen_extra,
        )
    return sent


async def replace_screen_callback(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    state: FSMContext | None = None,
    alert: str | None = None,
    defer_answer: bool = False,
    keyboard_kind: str | None = None,
    tag_step: bool = True,
    **screen_extra: object,
) -> Message:
    if not defer_answer:
        if alert:
            await callback.answer(alert)
        else:
            await callback.answer()
    await clear_wrong_input_notice(callback.bot, state)
    await delete_stored_screen(callback.bot, state)
    await delete_message_safe(callback.message)
    sent = await callback.message.answer(text, reply_markup=reply_markup)
    await _store_screen(state, sent)
    if tag_step:
        await tag_screen_step(
            state,
            text,
            reply_markup=reply_markup,
            keyboard_kind=keyboard_kind,
            **screen_extra,
        )
    return sent


async def resend_screen_after_notice(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    state: FSMContext | None = None,
) -> Message:
    """Повторно показать экран после отдельного предупреждения (тот же текст и кнопки)."""
    await delete_stored_screen(message.bot, state)
    sent = await message.answer(text, reply_markup=reply_markup)
    await _store_screen(state, sent)
    return sent


async def replace_screen_from_message(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    state: FSMContext | None = None,
    delete_user_message: bool = False,
    keyboard_kind: str | None = None,
    tag_step: bool = True,
    **screen_extra: object,
) -> Message:
    if delete_user_message:
        await delete_message_safe(message)
    await clear_wrong_input_notice(message.bot, state)
    await delete_stored_screen(message.bot, state)
    sent = await message.answer(text, reply_markup=reply_markup)
    await _store_screen(state, sent)
    if tag_step:
        await tag_screen_step(
            state,
            text,
            reply_markup=reply_markup,
            keyboard_kind=keyboard_kind,
            **screen_extra,
        )
    return sent
