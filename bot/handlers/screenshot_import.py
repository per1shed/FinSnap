"""Импорт операций со скриншота банка (Tesseract OCR, без ИИ)."""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import TransactionType
from bot.db import queries
from bot.db.pool import get_pool
from bot.handlers.fsm_reprompt import show_fsm_step_callback
from bot.handlers.menu_helpers import show_main_menu
from bot.handlers.screen import (
    clear_wrong_input_notice,
    delete_message_safe,
    replace_screen_from_message,
)
from bot.keyboards.inline import (
    CB_IMPORT,
    IMPORT_CANCEL,
    IMPORT_CONFIRM_PREFIX,
    import_prompt_keyboard,
    import_review_keyboard,
)
from bot.services.screen_context import KB_IMPORT_PROMPT, KB_IMPORT_REVIEW
from bot.services.screenshot_import import DraftTransaction, extract_transactions_from_image
from bot.states.import_screen import ImportStates
from bot.texts.import_screen import (
    IMPORT_EMPTY,
    IMPORT_PROCESSING,
    IMPORT_TOO_MANY,
    format_review_screen,
    import_prompt_text,
)

router = Router(name="screenshot_import")

IMPORT_DRAFTS_KEY = "import_drafts"
IMPORT_RAW_OCR_KEY = "import_raw_ocr"
IMPORT_HINT_TYPE_KEY = "import_hint_type"


def _hint_from_data(data: dict) -> TransactionType | None:
    raw = data.get(IMPORT_HINT_TYPE_KEY)
    if not raw:
        return None
    try:
        return TransactionType(raw)
    except ValueError:
        return None


async def _download_largest_photo(bot: Bot, message: Message) -> bytes | None:
    photos = message.photo
    if not photos:
        return None
    photo = photos[-1]
    file = await bot.get_file(photo.file_id)
    if file.file_path is None:
        return None
    buffer = await bot.download_file(file.file_path)
    return buffer.read()


def _drafts_from_state(data: dict) -> list[DraftTransaction]:
    raw = data.get(IMPORT_DRAFTS_KEY) or []
    return [DraftTransaction.from_state_dict(item) for item in raw]


async def _store_drafts(state: FSMContext, drafts: list[DraftTransaction]) -> None:
    await state.update_data(
        **{IMPORT_DRAFTS_KEY: [d.to_state_dict() for d in drafts]}
    )


async def _start_import_flow(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    hint: TransactionType | None,
) -> None:
    label = None
    if hint == TransactionType.EXPENSE:
        label = "расходы"
    elif hint == TransactionType.INCOME:
        label = "доходы"

    await state.set_state(ImportStates.waiting_photo)
    await state.update_data(
        **{
            IMPORT_DRAFTS_KEY: [],
            IMPORT_RAW_OCR_KEY: None,
            IMPORT_HINT_TYPE_KEY: hint.value if hint else None,
        }
    )
    await show_fsm_step_callback(
        callback,
        state,
        import_prompt_text(tx_label=label),
        reply_markup=import_prompt_keyboard(),
        keyboard_kind=KB_IMPORT_PROMPT,
    )


@router.callback_query(F.data == CB_IMPORT)
async def start_import(callback: CallbackQuery, state: FSMContext) -> None:
    await _start_import_flow(callback, state, hint=None)


@router.callback_query(F.data == IMPORT_CANCEL)
async def cancel_import(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    current = await state.get_state()
    if current not in (
        ImportStates.waiting_photo.state,
        ImportStates.reviewing.state,
    ):
        await callback.answer()
        return
    await clear_wrong_input_notice(callback.bot, state)
    await callback.answer()
    await state.set_state(None)
    await state.update_data(
        **{IMPORT_DRAFTS_KEY: [], IMPORT_RAW_OCR_KEY: None, IMPORT_HINT_TYPE_KEY: None}
    )
    await show_main_menu(callback, settings, state)


async def _process_import_image_bytes(
    message: Message,
    state: FSMContext,
    settings: Settings,
    image_bytes: bytes | None,
) -> None:
    await delete_message_safe(message)
    data = await state.get_data()
    hint = _hint_from_data(data)

    if not image_bytes:
        await replace_screen_from_message(
            message,
            "Не удалось загрузить фото. Попробуйте ещё раз.",
            reply_markup=import_prompt_keyboard(),
            state=state,
            keyboard_kind=KB_IMPORT_PROMPT,
        )
        return

    waiting = await replace_screen_from_message(
        message,
        IMPORT_PROCESSING,
        state=state,
        tag_step=False,
    )

    try:
        drafts, raw_text = extract_transactions_from_image(image_bytes, hint=hint)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception("screenshot import failed: %s", exc)
        await delete_message_safe(waiting)
        await replace_screen_from_message(
            message,
            "Ошибка распознавания. Пересоберите бота (Tesseract) или попробуйте другое фото.",
            reply_markup=import_prompt_keyboard(),
            state=state,
            keyboard_kind=KB_IMPORT_PROMPT,
        )
        return

    await delete_message_safe(waiting)
    await state.update_data(**{IMPORT_RAW_OCR_KEY: (raw_text or "")[:3000]})

    if not drafts:
        await replace_screen_from_message(
            message,
            IMPORT_EMPTY,
            reply_markup=import_prompt_keyboard(),
            state=state,
            keyboard_kind=KB_IMPORT_PROMPT,
        )
        return

    note = f"\n\n{IMPORT_TOO_MANY}" if len(drafts) >= 15 else ""

    await state.set_state(ImportStates.reviewing)
    await _store_drafts(state, drafts)
    await state.update_data(import_review_count=len(drafts))

    text = format_review_screen(drafts) + note
    await replace_screen_from_message(
        message,
        text,
        reply_markup=import_review_keyboard(len(drafts)),
        state=state,
        keyboard_kind=KB_IMPORT_REVIEW,
    )


@router.message(ImportStates.waiting_photo, F.photo)
async def process_import_photo(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    image_bytes = await _download_largest_photo(message.bot, message)
    await _process_import_image_bytes(message, state, settings, image_bytes)


@router.message(ImportStates.waiting_photo, F.document)
async def process_import_document(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    doc = message.document
    if doc is None or doc.mime_type is None or not doc.mime_type.startswith("image/"):
        await delete_message_safe(message)
        data = await state.get_data()
        hint = _hint_from_data(data)
        label = "расходы" if hint == TransactionType.EXPENSE else "доходы" if hint == TransactionType.INCOME else None
        await replace_screen_from_message(
            message,
            f"{import_prompt_text(tx_label=label)}\n\n⛔️ Отправьте <b>фото</b> или изображение (PNG/JPG).",
            reply_markup=import_prompt_keyboard(),
            state=state,
            keyboard_kind=KB_IMPORT_PROMPT,
        )
        return
    file = await message.bot.get_file(doc.file_id)
    if file.file_path is None:
        image_bytes = None
    else:
        buffer = await message.bot.download_file(file.file_path)
        image_bytes = buffer.read()
    await _process_import_image_bytes(message, state, settings, image_bytes)


@router.message(ImportStates.waiting_photo)
async def import_waiting_non_photo(message: Message, state: FSMContext) -> None:
    await delete_message_safe(message)
    data = await state.get_data()
    hint = _hint_from_data(data)
    label = "расходы" if hint == TransactionType.EXPENSE else "доходы" if hint == TransactionType.INCOME else None
    await replace_screen_from_message(
        message,
        f"{import_prompt_text(tx_label=label)}\n\n⛔️ Нужно отправить <b>фото</b> скрина.",
        reply_markup=import_prompt_keyboard(),
        state=state,
        keyboard_kind=KB_IMPORT_PROMPT,
    )


@router.callback_query(
    ImportStates.reviewing, F.data.startswith(IMPORT_CONFIRM_PREFIX)
)
async def confirm_import(
    callback: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    data = await state.get_data()
    drafts = _drafts_from_state(data)
    if not drafts:
        await callback.answer("Список пуст", show_alert=True)
        return

    pool = get_pool()
    user_id = callback.from_user.id
    await queries.ensure_user(pool, user_id)

    for draft in drafts:
        await queries.insert_transaction(
            pool,
            user_id,
            draft.tx_type,
            draft.category,
            draft.amount,
            draft.comment,
        )

    await state.set_state(None)
    await state.update_data(
        **{IMPORT_DRAFTS_KEY: [], IMPORT_RAW_OCR_KEY: None, IMPORT_HINT_TYPE_KEY: None}
    )
    await callback.answer(f"Записано операций: {len(drafts)}", show_alert=True)
    await show_main_menu(callback, settings, state)


@router.message(ImportStates.reviewing)
async def import_review_unexpected(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    drafts = _drafts_from_state(data)
    if not drafts:
        await state.set_state(ImportStates.waiting_photo)
        hint = _hint_from_data(data)
        label = "расходы" if hint == TransactionType.EXPENSE else "доходы" if hint == TransactionType.INCOME else None
        await replace_screen_from_message(
            message,
            import_prompt_text(tx_label=label),
            reply_markup=import_prompt_keyboard(),
            state=state,
            keyboard_kind=KB_IMPORT_PROMPT,
            delete_user_message=True,
        )
        return

    await delete_message_safe(message)
    await replace_screen_from_message(
        message,
        format_review_screen(drafts) + "\n\n⛔️ Используйте кнопки ниже.",
        reply_markup=import_review_keyboard(len(drafts)),
        state=state,
        keyboard_kind=KB_IMPORT_REVIEW,
    )
