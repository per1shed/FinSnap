from datetime import datetime, timedelta
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from bot.config import Settings
from bot.constants import TransactionType
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.chart_flow import (
    finish_chart_callback,
    hide_chart_building,
    show_chart_building_callback,
)
from bot.handlers.screen import (
    clear_wrong_input_notice,
    replace_screen_callback,
    send_screen,
)
from bot.services.screen_context import (
    KB_BACK_MENU,
    KB_STATS_KIND,
    KB_STATS_PERIOD,
    KB_STATS_TYPE,
    SCREEN_IS_PHOTO,
    tag_screen_step,
)
from bot.handlers.user_tz import resolve_user_tz
from bot.keyboards.inline import (
    CB_STATS,
    back_to_menu_keyboard,
    stats_kind_keyboard,
    stats_period_keyboard,
    stats_type_keyboard,
)
from bot.services.charts import build_category_pie, build_daily_histogram
from bot.texts.messages import (
    NO_EXPENSES_TEXT,
    NO_EXPENSES_MONTH_DAILY_TEXT,
    NO_INCOME_TEXT,
    NO_INCOME_MONTH_DAILY_TEXT,
    STATS_KIND_TEXT_EXPENSE,
    STATS_KIND_TEXT_INCOME,
    STATS_PERIOD_TEXT_EXPENSE,
    STATS_PERIOD_TEXT_INCOME,
    STATS_TYPE_TEXT,
)

router = Router(name="stats")

_PERIOD_TITLES = {
    (TransactionType.EXPENSE, "week"): "Расходы за неделю",
    (TransactionType.EXPENSE, "month"): "Расходы за месяц",
    (TransactionType.INCOME, "week"): "Доходы за неделю",
    (TransactionType.INCOME, "month"): "Доходы за месяц",
}


@router.callback_query(F.data == CB_STATS)
async def open_stats(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(None)
    await replace_screen_callback(
        callback,
        STATS_TYPE_TEXT,
        reply_markup=stats_type_keyboard(),
        state=state,
        keyboard_kind=KB_STATS_TYPE,
    )

@router.callback_query(F.data.in_({"stats_type:expense", "stats_type:income"}))
async def choose_stats_kind(callback: CallbackQuery, state: FSMContext) -> None:
    tx_type = (
        TransactionType.EXPENSE
        if callback.data.endswith("expense")
        else TransactionType.INCOME
    )
    await state.set_state(None)
    await state.update_data(stats_tx_type=tx_type.value)
    await replace_screen_callback(
        callback,
        STATS_KIND_TEXT_EXPENSE
        if tx_type == TransactionType.EXPENSE
        else STATS_KIND_TEXT_INCOME,
        reply_markup=stats_kind_keyboard(tx_type),
        state=state,
        keyboard_kind=KB_STATS_KIND,
    )


@router.callback_query(F.data.startswith("stats_kind:"))
async def choose_stats_period(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Неверная команда", show_alert=True)
        return

    _, tx_type_raw, kind = parts
    try:
        tx_type = TransactionType(tx_type_raw)
    except Exception:
        await callback.answer("Неверный тип", show_alert=True)
        return

    await state.set_state(None)
    await state.update_data(stats_tx_type=tx_type.value, stats_kind=kind)

    if kind == "daily":
        await send_daily_month_histogram(callback, tx_type, state, settings)
        return

    if kind != "pie":
        await callback.answer("Неверный график", show_alert=True)
        return

    await replace_screen_callback(
        callback,
        STATS_PERIOD_TEXT_EXPENSE
        if tx_type == TransactionType.EXPENSE
        else STATS_PERIOD_TEXT_INCOME,
        reply_markup=stats_period_keyboard(tx_type),
        state=state,
        keyboard_kind=KB_STATS_PERIOD,
    )


@router.callback_query(F.data.startswith("stats:"))
async def send_stats_chart(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Неверная команда", show_alert=True)
        return

    _, tx_type_raw, period = parts
    try:
        tx_type = TransactionType(tx_type_raw)
    except Exception:
        await callback.answer("Неверный тип", show_alert=True)
        return

    if period not in {"week", "month"}:
        await callback.answer("Неверный период", show_alert=True)
        return

    waiting = await show_chart_building_callback(callback, state)
    chat_id = waiting.chat.id

    pool = get_pool()
    user_id = callback.from_user.id
    user_tz = await resolve_user_tz(pool, user_id, settings)
    now = datetime.now(user_tz)
    rows = await queries.get_by_category(pool, user_id, tx_type, period, now, user_tz)

    if not rows:
        empty_text = (
            NO_EXPENSES_TEXT if tx_type == TransactionType.EXPENSE else NO_INCOME_TEXT
        )
        await send_screen(
            callback.bot,
            chat_id,
            empty_text,
            reply_markup=back_to_menu_keyboard(),
            state=state,
            keyboard_kind=KB_BACK_MENU,
        )
        await hide_chart_building(waiting)
        await finish_chart_callback(callback)
        return

    await clear_wrong_input_notice(callback.bot, state)
    title = _PERIOD_TITLES[(tx_type, period)]
    chart = build_category_pie(rows, title)
    filename = "expenses.png" if tx_type == TransactionType.EXPENSE else "income.png"
    photo = BufferedInputFile(chart.read(), filename=filename)

    sent = await callback.bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=title,
        reply_markup=back_to_menu_keyboard(),
    )
    await hide_chart_building(waiting)
    await finish_chart_callback(callback)
    await state.update_data(screen_chat_id=sent.chat.id, screen_message_id=sent.message_id)
    await tag_screen_step(
        state,
        title,
        reply_markup=back_to_menu_keyboard(),
        keyboard_kind=KB_BACK_MENU,
        **{SCREEN_IS_PHOTO: True},
    )


async def send_daily_month_histogram(
    callback: CallbackQuery,
    tx_type: TransactionType,
    state: FSMContext,
    settings: Settings,
) -> None:
    waiting = await show_chart_building_callback(callback, state)
    chat_id = waiting.chat.id

    pool = get_pool()
    user_id = callback.from_user.id
    user_tz = await resolve_user_tz(pool, user_id, settings)
    now = datetime.now(user_tz)
    daily = await queries.get_daily_totals_for_month(
        pool, user_id, tx_type, now, user_tz
    )

    # собрать полный список дней месяца с нулями
    local_now = now.astimezone(user_tz)
    start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
    if local_now.month == 12:
        next_month = local_now.replace(year=local_now.year + 1, month=1, day=1)
    else:
        next_month = local_now.replace(month=local_now.month + 1, day=1)
    end = next_month.date()

    by_day = {d: total for d, total in daily}
    days = []
    totals = []
    cur = start
    while cur < end:
        days.append(cur)
        totals.append(by_day.get(cur, Decimal("0")))
        cur = cur + timedelta(days=1)

    if all(t == 0 for t in totals):
        empty_text = (
            NO_EXPENSES_MONTH_DAILY_TEXT
            if tx_type == TransactionType.EXPENSE
            else NO_INCOME_MONTH_DAILY_TEXT
        )
        await send_screen(
            callback.bot,
            chat_id,
            empty_text,
            reply_markup=back_to_menu_keyboard(),
            state=state,
            keyboard_kind=KB_BACK_MENU,
        )
        await hide_chart_building(waiting)
        await finish_chart_callback(callback)
        return

    await clear_wrong_input_notice(callback.bot, state)
    title = "Траты по дням (месяц)" if tx_type == TransactionType.EXPENSE else "Доходы по дням (месяц)"
    chart = build_daily_histogram(days, totals, title)
    photo = BufferedInputFile(chart.read(), filename="daily.png")

    sent = await callback.bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=title,
        reply_markup=back_to_menu_keyboard(),
    )
    await hide_chart_building(waiting)
    await finish_chart_callback(callback)
    await state.update_data(screen_chat_id=sent.chat.id, screen_message_id=sent.message_id)
    await tag_screen_step(
        state,
        title,
        reply_markup=back_to_menu_keyboard(),
        keyboard_kind=KB_BACK_MENU,
        **{SCREEN_IS_PHOTO: True},
    )
