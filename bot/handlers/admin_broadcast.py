"""Рассылка сообщений всем пользователям (админ)."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.db.admin_queries import count_users, list_all_user_ids
from bot.db.pool import get_pool
from bot.handlers.admin import DEFAULT_PERIOD, _show_admin_dashboard
from bot.handlers.fsm_reprompt import show_fsm_step_callback, show_fsm_step_message
from bot.handlers.screen import delete_message_safe, replace_screen_from_message
from bot.keyboards.inline import (
    ADMIN_BROADCAST,
    ADMIN_BROADCAST_CANCEL,
    ADMIN_BROADCAST_SEND,
    admin_broadcast_compose_keyboard,
    admin_broadcast_preview_keyboard,
    broadcast_ack_keyboard,
    broadcast_result_ack_keyboard,
    CB_BROADCAST_RESULT_ACK,
)
from bot.services.admin_access import is_admin
from bot.services.screen_context import KB_ADMIN_BROADCAST, KB_ADMIN_BROADCAST_PREVIEW
from bot.states.admin import AdminStates
from bot.texts.admin import (
    ADMIN_ACCESS_DENIED,
    ADMIN_BROADCAST_EMPTY,
    ADMIN_BROADCAST_PREVIEW_FOOTER,
    ADMIN_BROADCAST_PREVIEW_HEADER,
    ADMIN_BROADCAST_PROMPT,
    ADMIN_BROADCAST_RESULT,
)

router = Router(name="admin_broadcast")
logger = logging.getLogger(__name__)

BROADCAST_TEXT_KEY = "broadcast_text"
_SEND_DELAY_SEC = 0.05


def _is_admin(user_id: int, settings: Settings) -> bool:
    return is_admin(user_id, settings.admin_ids)


async def _show_broadcast_compose(
    target: CallbackQuery | Message,
    state: FSMContext,
) -> None:
    await state.set_state(AdminStates.waiting_broadcast_text)
    await state.update_data(**{BROADCAST_TEXT_KEY: None})

    if isinstance(target, CallbackQuery):
        await show_fsm_step_callback(
            target,
            state,
            ADMIN_BROADCAST_PROMPT,
            reply_markup=admin_broadcast_compose_keyboard(),
            keyboard_kind=KB_ADMIN_BROADCAST,
        )
    else:
        await show_fsm_step_message(
            target,
            state,
            ADMIN_BROADCAST_PROMPT,
            reply_markup=admin_broadcast_compose_keyboard(),
            keyboard_kind=KB_ADMIN_BROADCAST,
        )


async def _show_broadcast_preview(
    message: Message,
    state: FSMContext,
    *,
    text: str,
) -> None:
    pool = get_pool()
    recipients = await count_users(pool)
    preview = (
        ADMIN_BROADCAST_PREVIEW_HEADER
        + text
        + ADMIN_BROADCAST_PREVIEW_FOOTER.format(count=recipients)
    )
    await state.update_data(**{BROADCAST_TEXT_KEY: text})
    await state.set_state(None)
    await replace_screen_from_message(
        message,
        preview,
        reply_markup=admin_broadcast_preview_keyboard(),
        state=state,
        delete_user_message=True,
        keyboard_kind=KB_ADMIN_BROADCAST_PREVIEW,
    )


async def _send_broadcast(bot, user_ids: list[int], text: str) -> tuple[int, int]:
    ok = 0
    fail = 0
    markup = broadcast_ack_keyboard()
    for user_id in user_ids:
        try:
            await bot.send_message(
                user_id,
                text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
            ok += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            fail += 1
        except Exception:
            logger.exception("broadcast failed for user_id=%s", user_id)
            fail += 1
        if _SEND_DELAY_SEC:
            await asyncio.sleep(_SEND_DELAY_SEC)
    return ok, fail


@router.callback_query(F.data == ADMIN_BROADCAST)
async def admin_broadcast_start(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return
    await callback.answer()
    await _show_broadcast_compose(callback, state)


@router.callback_query(F.data == ADMIN_BROADCAST_CANCEL)
async def admin_broadcast_cancel(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return
    await callback.answer()
    data = await state.get_data()
    period = str(data.get("admin_period", DEFAULT_PERIOD))
    await state.update_data(**{BROADCAST_TEXT_KEY: None})
    await _show_admin_dashboard(callback, state, settings, period)


@router.message(AdminStates.waiting_broadcast_text, F.text)
async def admin_broadcast_receive_text(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    text = (message.text or "").strip()
    if not text:
        await replace_screen_from_message(
            message,
            f"{ADMIN_BROADCAST_PROMPT}\n\n⛔️ {ADMIN_BROADCAST_EMPTY}",
            reply_markup=admin_broadcast_compose_keyboard(),
            state=state,
            delete_user_message=True,
            keyboard_kind=KB_ADMIN_BROADCAST,
        )
        return
    await _show_broadcast_preview(message, state, text=text)


@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_receive_non_text(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    await delete_message_safe(message)
    await replace_screen_from_message(
        message,
        f"{ADMIN_BROADCAST_PROMPT}\n\n⛔️ Отправьте <b>текст</b> сообщения.",
        reply_markup=admin_broadcast_compose_keyboard(),
        state=state,
        keyboard_kind=KB_ADMIN_BROADCAST,
    )


@router.callback_query(F.data == ADMIN_BROADCAST_SEND)
async def admin_broadcast_send(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return

    data = await state.get_data()
    text = (data.get(BROADCAST_TEXT_KEY) or "").strip()
    if not text:
        await callback.answer("Текст рассылки утерян. Начните снова.", show_alert=True)
        await _show_broadcast_compose(callback, state)
        return

    await callback.answer("Отправляю…")
    pool = get_pool()
    user_ids = await list_all_user_ids(pool)
    ok, fail = await _send_broadcast(callback.bot, user_ids, text)

    await state.update_data(**{BROADCAST_TEXT_KEY: None})
    period = str(data.get("admin_period", DEFAULT_PERIOD))
    result_text = ADMIN_BROADCAST_RESULT.format(ok=ok, fail=fail)
    await _show_admin_dashboard(callback, state, settings, period)
    await callback.bot.send_message(
        callback.from_user.id,
        result_text,
        reply_markup=broadcast_result_ack_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == CB_BROADCAST_RESULT_ACK)
async def admin_broadcast_result_ack(
    callback: CallbackQuery, settings: Settings
) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer(ADMIN_ACCESS_DENIED, show_alert=True)
        return
    await callback.answer()
    await delete_message_safe(callback.message)
