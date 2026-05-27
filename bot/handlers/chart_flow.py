"""Показ «диаграмма строится» на всё время генерации графика."""

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.screen import (
    clear_wrong_input_notice,
    delete_message_safe,
    delete_stored_screen,
    replace_screen_callback,
)
from bot.texts.messages import CHART_BUILDING_TEXT


async def show_chart_building_callback(
    callback: CallbackQuery,
    state: FSMContext | None,
) -> Message:
    """Текст в чате сразу; ответ на callback — после отправки диаграммы."""
    return await replace_screen_callback(
        callback,
        CHART_BUILDING_TEXT,
        state=state,
        defer_answer=True,
        tag_step=False,
    )


async def finish_chart_callback(callback: CallbackQuery, *, alert: str | None = None) -> None:
    """Снять индикатор загрузки на кнопке после появления результата."""
    try:
        if alert:
            await callback.answer(alert)
        else:
            await callback.answer()
    except TelegramBadRequest:
        pass


async def show_chart_building_message(
    message: Message,
    state: FSMContext | None,
    *,
    delete_user_message: bool = False,
) -> Message:
    if delete_user_message:
        await delete_message_safe(message)
    await clear_wrong_input_notice(message.bot, state)
    await delete_stored_screen(message.bot, state)
    sent = await message.answer(CHART_BUILDING_TEXT)
    if state is not None:
        from bot.handlers.screen import SCREEN_CHAT_ID_KEY, SCREEN_MESSAGE_ID_KEY

        await state.update_data(
            **{
                SCREEN_CHAT_ID_KEY: sent.chat.id,
                SCREEN_MESSAGE_ID_KEY: sent.message_id,
            }
        )
    return sent


async def hide_chart_building(waiting: Message | None) -> None:
    """Удалить экран ожидания после появления диаграммы в чате."""
    await delete_message_safe(waiting)
