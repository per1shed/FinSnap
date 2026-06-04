"""Разбор операций из OCR-текста банковских скринов (без ИИ)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from bot.constants import TransactionType
from bot.services.screenshot_import.categorize import guess_category
from bot.services.screenshot_import.models import DraftTransaction
from bot.services.screenshot_import.ocr import _normalize_line as _normalize_ocr_line

# С копейками: 1 234,56 | 50 000,00 | 890,50
_NUM_DEC = (
    r"(?:\d{1,3}(?:[\s\u00a0]\d{3})+[.,]\d{2}"
    r"|\d{1,3}(?:[\s\u00a0]\d{3})*[.,]\d{2}"
    r"|\d+[.,]\d{2})"
)
# Целые рубли: 50 000 ₽ или 1000 ₽ / 1599 ₽
_NUM_INT = r"(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d{3,})"

_CURRENCY_SUFFIX = r"(?:₽|RUB|РУБ|®|P)(?:\s|$|[.,;@])"

_AMOUNT_WITH_CURRENCY = re.compile(
    rf"(?<![\d])([+\-−–]?\s*)(({_NUM_DEC})|({_NUM_INT}))\s*{_CURRENCY_SUFFIX}",
    re.IGNORECASE,
)

_AMOUNT_CURRENCY_FIRST = re.compile(
    rf"(?:₽|RUB)\s*([+\-−–]?)\s*(({_NUM_DEC})|({_NUM_INT}))",
    re.IGNORECASE,
)

_AMOUNT_SIGNED = re.compile(
    rf"(?<![\d])([+\-−–])\s*({_NUM_DEC})(?!\s*(?:%|₽|руб))",
    re.IGNORECASE,
)

# Минус слитно с числом: -1234,56 или -1 234,56
_AMOUNT_MINUS_GLUE = re.compile(
    rf"(?<![\d])([+\-−–])\s*({_NUM_DEC})\s*(?:{_CURRENCY_SUFFIX})?",
    re.IGNORECASE,
)

# OCR часто теряет ₽, но оставляет копейки
_AMOUNT_DECIMAL_TAIL = re.compile(
    rf"(?<![\d])([+\-−–]?\s*)(({_NUM_DEC}))(?:\s|$)",
    re.IGNORECASE,
)

# −1000P / 1000 ® (Tesseract вместо ₽)
_AMOUNT_P_SUFFIX = re.compile(
    rf"(?<![\d])([+\-−–])\s*(\d{{1,3}}(?:[\s\u00a0]\d{{3}})*|\d{{3,}})\s*P[@®]?",
    re.IGNORECASE,
)

_AMOUNT_P_SUFFIX_UNSIGNED = re.compile(
    rf"(?<![\d])(\d{{1,3}}(?:[\s\u00a0]\d{{3}})*|\d{{3,}})\s*P[@®]?",
    re.IGNORECASE,
)

_DATE_ONLY = re.compile(
    r"^\s*(?:\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?|\d{4}[./-]\d{2}[./-]\d{2})\s*$"
)
_TIME_ONLY = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*$")
_CARD_MASK = re.compile(r"\*{2,}|\b\d{4}\s*\d{4}\s*\d{4}\b")

_SKIP_SUBSTR = (
    "баланс",
    "остаток",
    "доступно",
    "итого",
    "всего",
    "кэшбэк",
    "cashback",
    "лимит",
    "на счет",
    "на счёт",
    "счет ·",
    "счёт ·",
    "история опера",
    "главная",
    "профиль",
    "фильтр",
    "поиск",
    "настрой",
    "уведомлен",
    "подробнее о",
    "мили ",
    "бонусы",
    "вчера",
    "сегодня",
    "январ",
    "феврал",
    "март",
    "апрел",
    "май",
    "июн",
    "июл",
    "август",
    "сентябр",
    "октябр",
    "ноябр",
    "декабр",
    "закрыть",
    "операции",
    "траты",
    "доходы",
    "рассроч",
    "покупок на сумму",
    "доступна рассроч",
    "счета и карты",
    "без переводов",
    "без'переводов",
)

_BANK_SUBTITLE_HINTS = (
    "переводы",
    "супермаркет",
    "цифровые",
    "дебетовая",
    "black",
    "платинум",
    "карта",
    "счет",
    "счёт",
    "→",
    "@",
)

_STRONG_INCOME = (
    "зачислен",
    "пополнен",
    "поступлен",
    "возврат",
    "зарплат",
    "аванс",
    "доход",
    "перевод от",
    "от ",
    "приход",
    "начислен",
    "выплат",
    "между своими счетами",
    "между счетами",
)

_STRONG_EXPENSE = (
    "списан",
    "покупк",
    "оплат",
    "снятие",
    "снят",
    "перевод на",
    "перевод в",
    "платёж",
    "платеж",
    "покупка",
    "оплата",
    "расход",
    "комисс",
    "подписк",
)

_MIN_AMOUNT = Decimal("1")
_MAX_AMOUNT = Decimal("99999999")

# Начало списка операций (после даты — не блок «Траты / Доходы» сверху)
_TRANSACTION_SECTION_MARKERS = frozenset(
    {"сегодня", "вчера", "позавчера"}
)

# 5 июня, 27 мая, 12 мая 2024
_MONTH_PREFIXES = (
    "январ",
    "феврал",
    "март",
    "апрел",
    "май",
    "мая",
    "июн",
    "июл",
    "август",
    "сентябр",
    "октябр",
    "ноябр",
    "декабр",
)
_DATE_HEADER_RU = re.compile(
    rf"^\s*\d{{1,2}}\s+(?:{'|'.join(_MONTH_PREFIXES)})\w*(?:\s+\d{{4}})?\s*$",
    re.IGNORECASE,
)


def _fix_ocr_digits_in_amount(raw: str) -> str:
    """Типичные ошибки OCR в числах."""
    s = raw.replace("O", "0").replace("o", "0").replace("О", "0")
    s = s.replace("l", "1").replace("I", "1").replace("|", "1")
    s = s.replace("S", "5").replace("B", "8")
    s = s.replace("\u00a0", " ").replace(" ", "")
    return s


def _parse_decimal(amount_str: str, sign_char: str) -> Decimal | None:
    cleaned = _fix_ocr_digits_in_amount(amount_str)
    cleaned = cleaned.replace(",", ".")
    if cleaned.count(".") > 1:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if value <= 0:
        return None
    if sign_char and sign_char in "-−–":
        return -value
    if sign_char == "+":
        return value
    return value


def _is_noise_line(line: str) -> bool:
    low = line.lower().strip()
    if len(low) < 2:
        return True
    if _DATE_ONLY.match(low) or _TIME_ONLY.match(low):
        return True
    if _CARD_MASK.search(line):
        return True
    if any(s in low for s in _SKIP_SUBSTR):
        return True
    # Только проценты / ставки
    if re.fullmatch(r"[\d\s.,+%\-−–]+", low) and "%" in low:
        return True
    return False


def _amount_groups(
    pattern: re.Pattern[str], match: re.Match[str]
) -> tuple[str, str]:
    if pattern in (
        _AMOUNT_SIGNED,
        _AMOUNT_MINUS_GLUE,
        _AMOUNT_P_SUFFIX,
    ):
        return match.group(1), match.group(2)
    if pattern == _AMOUNT_P_SUFFIX_UNSIGNED:
        return "", match.group(1)
    sign = (match.group(1) or "").strip()
    num = match.group(2)
    return sign, num


def _find_amount_in_line(line: str) -> tuple[Decimal, re.Match[str]] | None:
    candidates: list[tuple[int, int, Decimal, re.Match[str]]] = []

    for pattern in (
        _AMOUNT_WITH_CURRENCY,
        _AMOUNT_CURRENCY_FIRST,
        _AMOUNT_MINUS_GLUE,
        _AMOUNT_P_SUFFIX,
        _AMOUNT_P_SUFFIX_UNSIGNED,
        _AMOUNT_SIGNED,
        _AMOUNT_DECIMAL_TAIL,
    ):
        for match in pattern.finditer(line):
            sign, num = _amount_groups(pattern, match)
            signed = _parse_decimal(str(num), str(sign).strip())
            if signed is None:
                continue
            if abs(signed) < _MIN_AMOUNT or abs(signed) > _MAX_AMOUNT:
                continue
            blob = match.group(0).lower()
            has_currency = "₽" in match.group(0) or "руб" in blob or blob.rstrip().endswith("p")
            has_sign = bool(str(sign).strip())
            priority = 0
            if has_currency:
                priority += 100
            if has_sign:
                priority += 50
            if "," in str(num) or "." in str(num):
                priority += 20
            priority += match.start()
            candidates.append((priority, match.end(), signed, match))

    if not candidates:
        return None
    _, _, signed, match = max(candidates, key=lambda x: (x[0], x[1]))
    return signed, match


def _detect_type(
    line: str,
    amount_signed: Decimal,
    *,
    hint: TransactionType | None,
    context: str,
) -> TransactionType:
    blob = f"{context} {line}".lower()
    if amount_signed < 0:
        return TransactionType.EXPENSE
    if any(w in blob for w in _STRONG_INCOME):
        return TransactionType.INCOME
    if amount_signed > 0 and "между своими" in blob:
        return TransactionType.INCOME
    if any(w in blob for w in _STRONG_EXPENSE):
        return TransactionType.EXPENSE
    if "+" in line and amount_signed > 0:
        return TransactionType.INCOME
    if hint is not None and amount_signed > 0:
        return hint
    return TransactionType.EXPENSE


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def _clean_title(text: str) -> str:
    text = re.sub(r"^[\W\d]{1,5}", "", text.strip())
    text = re.sub(r"^[оО]\s+", "", text)
    text = re.sub(r"[\W_]+$", "", text)
    text = re.sub(r"\s+", " ", text).strip("·•|-— ,.")
    return text[:80]


def _letters_only(text: str) -> str:
    return re.sub(r"[^a-zа-яё]", "", text.lower().replace("ё", "е"))


def _distinct_amount_spans(line: str) -> list[tuple[int, int]]:
    """Уникальные позиции сумм в строке (без двойного счёта одним regex)."""
    spans: list[tuple[int, int]] = []
    for pattern in (
        _AMOUNT_WITH_CURRENCY,
        _AMOUNT_P_SUFFIX,
        _AMOUNT_P_SUFFIX_UNSIGNED,
        _AMOUNT_SIGNED,
        _AMOUNT_DECIMAL_TAIL,
    ):
        for match in pattern.finditer(line):
            start, end = match.start(), match.end()
            if any(not (end <= s or start >= e) for s, e in spans):
                continue
            spans.append((start, end))
    return spans


def _is_period_totals_line(line: str) -> bool:
    """Виджет «2647₽ 1200₽» или «Траты Доходы» — не отдельные операции."""
    low = line.lower()
    if "траты" in low and "доходы" in low:
        return True
    letters = _letters_only(line)
    spans = _distinct_amount_spans(line)
    if len(spans) >= 2 and len(letters) < 4:
        return True
    if spans and len(letters) < 4:
        return True
    return False


def _is_transaction_list_start(line: str) -> bool:
    """Заголовок группы операций: относительная дата, число.месяц или «5 июня»."""
    low = line.lower().strip().replace("ё", "е")
    if low in _TRANSACTION_SECTION_MARKERS:
        return True
    if re.fullmatch(r"(сегодня|вчера|позавчера)", low):
        return True
    if _DATE_ONLY.match(line):
        return True
    if _DATE_HEADER_RU.match(low):
        return True
    return False


def _has_merchant_title(line: str, match: re.Match[str]) -> bool:
    title = _title_from_amount_line(line, match)
    letters = _letters_only(title)
    return len(letters) >= 3


def _is_summary_amount_line(line: str, amount_signed: Decimal) -> bool:
    if _is_period_totals_line(line):
        return True
    low = line.lower()
    if any(s in low for s in ("рассроч", "покупок на сумму", "доступна")):
        return True
    if abs(amount_signed) >= Decimal("10000") and not any(
        c.isalpha() for c in _clean_title(line.split(str(int(abs(amount_signed))))[0])
    ):
        return True
    return False


def _is_bank_subtitle_line(line: str) -> bool:
    low = line.lower()
    if _find_amount_in_line(line) is not None:
        return False
    if any(h in low for h in _BANK_SUBTITLE_HINTS):
        return True
    # Строка категории банка без суммы: «Переводы Black», «Супермаркеты …»
    return bool(re.search(r"(перевод|супермаркет|цифров|карт|счет|счёт)", low))


def _is_header_or_promo_line(line: str) -> bool:
    if _is_noise_line(line):
        return True
    if _is_period_totals_line(line):
        return True
    low = line.lower()
    if re.fullmatch(r"[\d\s₽pр®@]+", low):
        return True
    if re.match(r"^\d{3,4}\s*₽", low) and ("трат" in low or "доход" in low):
        return True
    return False


def _title_from_amount_line(line: str, match: re.Match[str]) -> str:
    desc = line[: match.start()].strip()
    return _clean_title(desc)


def _make_draft(
    *,
    title: str | None,
    bank_category: str | None,
    line: str,
    amount_signed: Decimal,
    hint: TransactionType | None,
) -> DraftTransaction | None:
    merchant = title or "Операция"
    if len(merchant) < 2:
        return None
    if len(_letters_only(merchant)) < 3:
        return None
    if _is_noise_line(merchant):
        return None

    context = f"{merchant} {bank_category or ''} {line}"
    tx_type = _detect_type(line, amount_signed, hint=hint, context=context)
    category = guess_category(tx_type, f"{merchant} {bank_category or ''}")
    return DraftTransaction(
        amount=abs(amount_signed),
        tx_type=tx_type,
        comment=merchant,
        category=category,
        bank_category=(bank_category or "")[:60],
    )


def _dedupe_drafts(drafts: list[DraftTransaction]) -> list[DraftTransaction]:
    seen: set[tuple[str, str, str]] = set()
    out: list[DraftTransaction] = []
    for d in drafts:
        key = (str(d.amount), d.tx_type.value, d.comment.lower()[:50])
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def parse_transactions_from_lines(
    lines: list[str],
    *,
    hint: TransactionType | None = None,
) -> list[DraftTransaction]:
    """
    Разбор построчно (как в OCR): название → категория банка → строка с суммой.
    Игнорирует шапку экрана (виджет «Траты / Доходы»), разбор после заголовка даты.
    """
    drafts: list[DraftTransaction] = []
    pending_title: str | None = None
    awaiting_bank_idx: int | None = None
    in_transactions = False

    for raw in lines:
        line = _normalize_ocr_line(raw.strip())
        if not line:
            continue

        if _is_transaction_list_start(line):
            in_transactions = True
            pending_title = None
            awaiting_bank_idx = None
            continue

        found = _find_amount_in_line(line)

        if not in_transactions:
            if _is_header_or_promo_line(line):
                continue
            if found is None:
                continue
            amount_signed, match = found
            if _is_summary_amount_line(line, amount_signed):
                continue
            if not _has_merchant_title(line, match):
                continue
            in_transactions = True

        if _is_header_or_promo_line(line):
            pending_title = None
            awaiting_bank_idx = None
            continue

        if found is not None:
            amount_signed, match = found
            if _is_summary_amount_line(line, amount_signed):
                pending_title = None
                awaiting_bank_idx = None
                continue

            title_inline = _title_from_amount_line(line, match)
            if len(title_inline) >= 2:
                title = title_inline
            else:
                title = pending_title

            draft = _make_draft(
                title=title,
                bank_category=None,
                line=line,
                amount_signed=amount_signed,
                hint=hint,
            )
            if draft is not None:
                drafts.append(draft)
                awaiting_bank_idx = len(drafts) - 1
            pending_title = None
            continue

        if _is_bank_subtitle_line(line):
            bank = _clean_title(line)
            if awaiting_bank_idx is not None and not drafts[awaiting_bank_idx].bank_category:
                d = drafts[awaiting_bank_idx]
                drafts[awaiting_bank_idx] = DraftTransaction(
                    amount=d.amount,
                    tx_type=d.tx_type,
                    comment=d.comment,
                    category=guess_category(
                        d.tx_type, f"{d.comment} {bank}"
                    ),
                    bank_category=bank,
                )
                awaiting_bank_idx = None
            continue

        cleaned = _clean_title(line)
        if len(cleaned) >= 2:
            pending_title = cleaned

    return _dedupe_drafts(drafts)[:15]


def parse_transactions_combined(
    lines: list[str],
    raw_text: str,
    *,
    hint: TransactionType | None = None,
) -> list[DraftTransaction]:
    """Только структурированные строки OCR (без повторного разбора сырого текста)."""
    result = parse_transactions_from_lines(lines, hint=hint)
    if result:
        return result
    if not raw_text:
        return []
    fallback_lines = [
        _normalize_spaces(ln) for ln in raw_text.splitlines() if ln.strip()
    ]
    return parse_transactions_from_lines(fallback_lines, hint=hint)
