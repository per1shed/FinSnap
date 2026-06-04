from bot.constants import TransactionType
from bot.services.screenshot_import.models import DraftTransaction
from bot.services.screenshot_import.ocr import extract_ocr_result
from bot.services.screenshot_import.parser import parse_transactions_combined


def extract_transactions_from_image(
    image_bytes: bytes,
    *,
    hint: TransactionType | None = None,
) -> tuple[list[DraftTransaction], str]:
    """
    OCR (несколько проходов) + разбор.
    hint — если пользователь зашёл через «Расход»/«Доход», помогает угадать тип.
    """
    ocr = extract_ocr_result(image_bytes)
    drafts = parse_transactions_combined(
        list(ocr.lines),
        ocr.raw_text,
        hint=hint,
    )
    if hint is not None:
        drafts = _apply_hint_filter(drafts, hint)
    debug_text = "\n".join(ocr.lines) if ocr.lines else ocr.raw_text
    return drafts, debug_text


def _apply_hint_filter(
    drafts: list[DraftTransaction], hint: TransactionType
) -> list[DraftTransaction]:
    """Если пользователь выбрал «Расход»/«Доход», оставляем подходящие операции."""
    filtered = [d for d in drafts if d.tx_type == hint]
    return filtered if filtered else drafts
