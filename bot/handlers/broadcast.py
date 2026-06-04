"""Получение рассылки: кнопка «Понятно» — только удалить сообщение рассылки."""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.handlers.screen import delete_message_safe
from bot.keyboards.inline import CB_BROADCAST_ACK

router = Router(name="broadcast")


@router.callback_query(F.data == CB_BROADCAST_ACK)
async def broadcast_ack(callback: CallbackQuery) -> None:
    await callback.answer()
    await delete_message_safe(callback.message)
