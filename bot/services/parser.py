import re
from decimal import Decimal, InvalidOperation

_AMOUNT_RE = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*(.*)\s*$",
    re.DOTALL,
)


def parse_amount_and_comment(text: str) -> tuple[Decimal, str] | None:
    match = _AMOUNT_RE.match(text.strip())
    if not match:
        return None

    raw_amount, comment = match.group(1), match.group(2).strip()
    normalized = raw_amount.replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None

    if amount <= 0:
        return None

    return amount, comment


def parse_amount_only(text: str) -> Decimal | None:
    parsed = parse_amount_and_comment(text)
    if parsed is None:
        return None
    return parsed[0]
