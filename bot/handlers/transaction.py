from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import EXPENSE_CATEGORIES, INCOME_CATEGORIES, TransactionType
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.menu_helpers import build_main_menu_payload
from bot.services.admin_access import is_admin
from bot.services.screen_context import KB_MAIN_MENU, MENU_SHOW_ADMIN_KEY
from bot.handlers.fsm_reprompt import (
    KB_CATEGORY_EXPENSE,
    KB_CATEGORY_INCOME,
    KB_TEXT_CANCEL,
    reprompt_current_step,
    show_fsm_step_callback,
)
from bot.handlers.screen import replace_screen_from_message
from bot.keyboards.inline import CB_EXPENSE, CB_INCOME, cancel_keyboard, category_keyboard
from bot.services.parser import parse_amount_and_comment
from bot.states.transaction import TransactionStates
from bot.texts.messages import INVALID_AMOUNT_TEXT, category_prompt

router = Router(name="transaction")


def _resolve_category(tx_type: TransactionType, key: str) -> str | None:
    mapping = (
        EXPENSE_CATEGORIES
        if tx_type == TransactionType.EXPENSE
        else INCOME_CATEGORIES
    )
    return mapping.get(key)


@router.callback_query(F.data == CB_EXPENSE)
async def choose_expense(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TransactionStates.choosing_category)
    await state.update_data(tx_type=TransactionType.EXPENSE.value)
    await show_fsm_step_callback(
        callback,
        state,
        "Выберите категорию расхода:",
        reply_markup=category_keyboard(TransactionType.EXPENSE),
        keyboard_kind=KB_CATEGORY_EXPENSE,
    )


@router.callback_query(F.data == CB_INCOME)
async def choose_income(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TransactionStates.choosing_category)
    await state.update_data(tx_type=TransactionType.INCOME.value)
    await show_fsm_step_callback(
        callback,
        state,
        "Выберите категорию дохода:",
        reply_markup=category_keyboard(TransactionType.INCOME),
        keyboard_kind=KB_CATEGORY_INCOME,
    )


@router.callback_query(F.data.startswith("cat:e:"))
async def expense_category_selected(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await _start_input(callback, state, TransactionType.EXPENSE, callback.data.split(":")[-1])


@router.callback_query(F.data.startswith("cat:i:"))
async def income_category_selected(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await _start_input(callback, state, TransactionType.INCOME, callback.data.split(":")[-1])


async def _start_input(
    callback: CallbackQuery,
    state: FSMContext,
    tx_type: TransactionType,
    category_key: str,
) -> None:
    category_label = _resolve_category(tx_type, category_key)
    if category_label is None:
        await callback.answer("Неизвестная категория", show_alert=True)
        return

    await state.set_state(TransactionStates.waiting_input)
    await state.update_data(
        tx_type=tx_type.value,
        category_label=category_label,
    )
    prompt = category_prompt(
        "Расход" if tx_type == TransactionType.EXPENSE else "Доход",
        category_label,
    )
    await show_fsm_step_callback(
        callback,
        state,
        prompt,
        reply_markup=cancel_keyboard(),
        keyboard_kind=KB_TEXT_CANCEL,
    )


@router.message(TransactionStates.waiting_input)
async def process_transaction_input(
    message: Message,
    state: FSMContext,
    settings: Settings,
) -> None:
    parsed = parse_amount_and_comment(message.text or "")
    data = await state.get_data()

    if parsed is None:
        await reprompt_current_step(
            message, state, settings, detail=INVALID_AMOUNT_TEXT
        )
        return

    amount, comment = parsed
    tx_type = TransactionType(data["tx_type"])
    category_label = data["category_label"]
    pool = get_pool()

    await queries.ensure_user(pool, message.from_user.id)
    await queries.insert_transaction(
        pool,
        message.from_user.id,
        tx_type,
        category_label,
        amount,
        comment,
    )

    user_id = message.from_user.id
    text, keyboard = await build_main_menu_payload(user_id, settings)
    await replace_screen_from_message(
        message,
        text,
        reply_markup=keyboard,
        state=state,
        delete_user_message=True,
        keyboard_kind=KB_MAIN_MENU,
        **{MENU_SHOW_ADMIN_KEY: is_admin(user_id, settings.admin_ids)},
    )
    await state.set_state(None)
