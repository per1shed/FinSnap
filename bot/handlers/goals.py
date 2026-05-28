from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message

from bot.config import Settings
from bot.db import goals_queries
from bot.db.goals_queries import FinancialGoal
from bot.db.pool import get_pool
from bot.handlers.fsm_reprompt import (
    KB_TEXT_CANCEL,
    reprompt_current_step,
    show_fsm_step_callback,
    show_fsm_step_message,
)
from bot.keyboards.inline import cancel_keyboard
from bot.handlers.chart_flow import (
    finish_chart_callback,
    hide_chart_building,
    show_chart_building_callback,
    show_chart_building_message,
)
from bot.handlers.screen import (
    SCREEN_CHAT_ID_KEY,
    SCREEN_MESSAGE_ID_KEY,
    clear_wrong_input_notice,
    delete_message_safe,
    delete_stored_screen,
    replace_screen_callback,
    replace_screen_from_message,
)
from bot.keyboards.inline import (
    CB_GOAL_LIST,
    CB_GOAL_NEW,
    CB_GOALS,
    goal_delete_confirm_keyboard,
    goal_detail_keyboard,
    goals_list_keyboard,
)
from bot.services.charts import build_goal_progress_pie, build_goals_overview_pie
from bot.services.screen_context import KB_GOALS_LIST, SCREEN_IS_PHOTO, tag_screen_step
from bot.services.goals_format import format_goal_caption, format_goals_list_caption
from bot.services.parser import parse_amount_only
from bot.states.goal import GoalStates
from bot.texts.goals import (
    GOAL_COMPLETED_TEXT,
    GOAL_CREATED_TEXT,
    GOAL_DEPOSIT_PROMPT,
    GOAL_DELETE_CONFIRM_TEXT,
    GOAL_DELETED_TEXT,
    GOAL_LIMIT_REACHED,
    GOAL_TARGET_PROMPT,
    GOAL_TITLE_PROMPT,
    GOAL_TITLE_TOO_SHORT,
    INVALID_GOAL_AMOUNT_TEXT,
)
from bot.texts.messages import CHART_BUILDING_TEXT, format_money

router = Router(name="goals")


async def _store_photo_screen(state: FSMContext | None, message: Message) -> None:
    if state is None:
        return
    await state.update_data(
        **{
            SCREEN_CHAT_ID_KEY: message.chat.id,
            SCREEN_MESSAGE_ID_KEY: message.message_id,
        }
    )


async def _send_goal_photo(
    bot,
    chat_id: int,
    goal: FinancialGoal,
    *,
    reply_markup: InlineKeyboardMarkup | None,
    state: FSMContext | None,
    header: str = "",
    waiting: Message | None = None,
) -> Message:
    await clear_wrong_input_notice(bot, state)
    if waiting is None:
        waiting = await bot.send_message(chat_id, CHART_BUILDING_TEXT)
        if state is not None:
            await state.update_data(
                screen_chat_id=waiting.chat.id,
                screen_message_id=waiting.message_id,
            )

    chart = build_goal_progress_pie(
        goal.saved_amount, goal.target_amount, goal.title
    )
    photo = BufferedInputFile(chart.read(), filename=f"goal_{goal.id}.png")

    sent = await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=format_goal_caption(goal, header=header),
        reply_markup=reply_markup,
    )
    await hide_chart_building(waiting)
    await _store_photo_screen(state, sent)
    return sent


async def _send_goals_list_photo(
    target: Message | CallbackQuery,
    goals: list[FinancialGoal],
    keyboard: InlineKeyboardMarkup,
    state: FSMContext | None,
) -> None:
    callback: CallbackQuery | None = None
    if isinstance(target, CallbackQuery):
        callback = target
        bot = target.bot
        chat_id = target.message.chat.id
        waiting = await show_chart_building_callback(target, state)
    else:
        bot = target.bot
        chat_id = target.chat.id
        waiting = await show_chart_building_message(target, state)

    chart = build_goals_overview_pie(goals)
    photo = BufferedInputFile(chart.read(), filename="goals_overview.png")

    sent = await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=format_goals_list_caption(goals),
        reply_markup=keyboard,
    )
    await hide_chart_building(waiting)
    if callback is not None:
        await finish_chart_callback(callback)
    await _store_photo_screen(state, sent)
    if state is not None:
        await tag_screen_step(
            state,
            format_goals_list_caption(goals),
            reply_markup=keyboard,
            keyboard_kind=KB_GOALS_LIST,
            **{SCREEN_IS_PHOTO: True},
        )


async def _show_goals_list(
    target: Message | CallbackQuery, state: FSMContext, user_id: int
) -> None:
    pool = get_pool()
    goals = await goals_queries.list_active_goals(pool, user_id)
    keyboard = goals_list_keyboard(goals)

    if not goals:
        text = format_goals_list_caption(goals)
        if isinstance(target, CallbackQuery):
            await replace_screen_callback(
                target,
                text,
                reply_markup=keyboard,
                state=state,
                keyboard_kind=KB_GOALS_LIST,
            )
        else:
            await replace_screen_from_message(
                target,
                text,
                reply_markup=keyboard,
                state=state,
                keyboard_kind=KB_GOALS_LIST,
            )
        return

    await _send_goals_list_photo(target, goals, keyboard, state)


async def _show_goal_detail(
    callback: CallbackQuery, state: FSMContext, goal_id: int, user_id: int
) -> None:
    pool = get_pool()
    goal = await goals_queries.get_goal(pool, goal_id, user_id)
    if goal is None:
        await callback.answer("Цель не найдена", show_alert=True)
        return

    waiting = await show_chart_building_callback(callback, state)

    await _send_goal_photo(
        callback.bot,
        callback.message.chat.id,
        goal,
        reply_markup=goal_detail_keyboard(goal.id, goal.is_completed),
        state=state,
        waiting=waiting,
    )
    await finish_chart_callback(callback)


@router.callback_query(F.data == CB_GOALS)
@router.callback_query(F.data == CB_GOAL_LIST)
async def open_goals_list(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(None)
    await _show_goals_list(callback, state, callback.from_user.id)


@router.callback_query(F.data == CB_GOAL_NEW)
async def start_new_goal(callback: CallbackQuery, state: FSMContext) -> None:
    pool = get_pool()
    user_id = callback.from_user.id
    count = await goals_queries.count_active_goals(pool, user_id)
    if count >= goals_queries.MAX_ACTIVE_GOALS:
        await callback.answer(
            GOAL_LIMIT_REACHED.format(limit=goals_queries.MAX_ACTIVE_GOALS),
            show_alert=True,
        )
        return

    await state.set_state(GoalStates.waiting_title)
    await show_fsm_step_callback(
        callback,
        state,
        GOAL_TITLE_PROMPT,
        reply_markup=cancel_keyboard(),
        keyboard_kind=KB_TEXT_CANCEL,
    )


@router.message(GoalStates.waiting_title)
async def process_goal_title(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    title = (message.text or "").strip()
    if len(title) < 2:
        await reprompt_current_step(
            message, state, settings, detail=GOAL_TITLE_TOO_SHORT
        )
        return

    await state.update_data(goal_title=title)
    await state.set_state(GoalStates.waiting_target)
    await show_fsm_step_message(
        message,
        state,
        GOAL_TARGET_PROMPT.format(title=title),
        reply_markup=cancel_keyboard(),
        keyboard_kind=KB_TEXT_CANCEL,
        delete_user_message=True,
    )


@router.message(GoalStates.waiting_target)
async def process_goal_target(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    amount = parse_amount_only(message.text or "")
    if amount is None:
        await reprompt_current_step(
            message, state, settings, detail=INVALID_GOAL_AMOUNT_TEXT
        )
        return

    data = await state.get_data()
    title = data["goal_title"]
    pool = get_pool()
    user_id = message.from_user.id

    goal = await goals_queries.create_goal(pool, user_id, title, amount)
    await state.set_state(None)

    header = GOAL_CREATED_TEXT.format(
        title=goal.title,
        target=format_money(goal.target_amount),
    )
    waiting = await show_chart_building_message(
        message, state, delete_user_message=True
    )
    await _send_goal_photo(
        message.bot,
        message.chat.id,
        goal,
        reply_markup=goal_detail_keyboard(goal.id, goal.is_completed),
        state=state,
        header=header,
        waiting=waiting,
    )


@router.callback_query(F.data.startswith("goal:open:"))
async def open_goal(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(None)
    goal_id = int(callback.data.split(":")[-1])
    await _show_goal_detail(callback, state, goal_id, callback.from_user.id)


@router.callback_query(F.data.startswith("goal:deposit:"))
async def start_deposit(callback: CallbackQuery, state: FSMContext) -> None:
    goal_id = int(callback.data.split(":")[-1])
    pool = get_pool()
    goal = await goals_queries.get_goal(pool, goal_id, callback.from_user.id)
    if goal is None or goal.is_completed:
        await callback.answer("Цель недоступна", show_alert=True)
        return

    await state.set_state(GoalStates.waiting_deposit)
    await state.update_data(goal_id=goal_id, goal_title=goal.title)
    await show_fsm_step_callback(
        callback,
        state,
        GOAL_DEPOSIT_PROMPT.format(title=goal.title),
        reply_markup=cancel_keyboard(),
        keyboard_kind=KB_TEXT_CANCEL,
    )


@router.message(GoalStates.waiting_deposit)
async def process_deposit(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    amount = parse_amount_only(message.text or "")
    if amount is None:
        await reprompt_current_step(
            message, state, settings, detail=INVALID_GOAL_AMOUNT_TEXT
        )
        return

    data = await state.get_data()
    goal_id = data["goal_id"]
    pool = get_pool()
    user_id = message.from_user.id

    goal = await goals_queries.add_to_goal(pool, goal_id, user_id, amount)

    if goal is None:
        await reprompt_current_step(
            message, state, settings, detail="Не удалось пополнить цель."
        )
        return

    await state.set_state(None)

    header = ""
    if goal.is_completed:
        header = GOAL_COMPLETED_TEXT.format(
            title=goal.title, saved=format_money(goal.saved_amount)
        )

    waiting = await show_chart_building_message(
        message, state, delete_user_message=True
    )
    await _send_goal_photo(
        message.bot,
        message.chat.id,
        goal,
        reply_markup=goal_detail_keyboard(goal.id, goal.is_completed),
        state=state,
        header=header,
        waiting=waiting,
    )


@router.callback_query(F.data.regexp(r"^goal:delete:\d+$"))
async def ask_delete_goal(callback: CallbackQuery, state: FSMContext) -> None:
    goal_id = int(callback.data.split(":")[-1])
    pool = get_pool()
    goal = await goals_queries.get_goal(pool, goal_id, callback.from_user.id)
    if goal is None:
        await callback.answer("Цель не найдена", show_alert=True)
        return

    await state.set_state(None)
    await replace_screen_callback(
        callback,
        GOAL_DELETE_CONFIRM_TEXT.format(title=goal.title),
        reply_markup=goal_delete_confirm_keyboard(goal_id),
        state=state,
    )


@router.callback_query(F.data.startswith("goal:delete_confirm:"))
async def delete_goal_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
    goal_id = int(callback.data.split(":")[-1])
    pool = get_pool()
    deleted = await goals_queries.delete_goal(pool, goal_id, callback.from_user.id)
    if not deleted:
        await callback.answer("Цель не найдена", show_alert=True)
        return

    await state.set_state(None)
    await callback.answer(GOAL_DELETED_TEXT)
    await _show_goals_list(callback, state, callback.from_user.id)
