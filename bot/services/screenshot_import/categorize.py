from bot.constants import EXPENSE_CATEGORIES, INCOME_CATEGORIES, TransactionType

_EXPENSE_HINTS: list[tuple[tuple[str, ...], str]] = [
    (
        (
            "продукт",
            "магнит",
            "пятероч",
            "пятёроч",
            "перекрест",
            "перекрёст",
            "ашан",
            "lenta",
            "лента",
            "дикси",
            "вкусвилл",
            "ozon fresh",
            "монетка",
            "metro c",
            "metro c&c",
            "метро cc",
            "самокат",
            "сбермаркет",
            "fix price",
            "spar",
            "spar ",
        ),
        "groceries",
    ),
    (
        (
            "кафе",
            "ресторан",
            "coffee",
            "starbucks",
            "макдоналд",
            "kfc",
            "burger",
            "додо",
            "доставка еды",
            "яндекс еда",
        ),
        "cafe",
    ),
    (
        (
            "такси",
            "uber",
            "яндекс go",
            "yandex go",
            "такси ",
            "автобус",
            "бензин",
            "азс",
            "транспорт",
            "каршер",
            "ситимобил",
            "заправ",
        ),
        "transport",
    ),
    (
        ("жкх", "аренд", "квартир", "ипотек", "коммунал", "электро", "водокан"),
        "housing",
    ),
    (
        (
            "кино",
            "театр",
            "игр",
            "steam",
            "подписк",
            "netflix",
            "spotify",
            "ozon",
            "wildberries",
            "wb ",
            "lamoda",
            "маркет",
            "vk музык",
            "vk music",
            "музык",
        ),
        "entertainment",
    ),
]

_INCOME_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("зарплат", "аванс", "оклад", "payroll"), "salary"),
    (("фриланс", "freelance", "проект", "гонорар"), "freelance"),
]


def _norm(text: str) -> str:
    return text.lower().replace("ё", "е")


def guess_category(tx_type: TransactionType, description: str) -> str:
    text = _norm(description)
    hints = _INCOME_HINTS if tx_type == TransactionType.INCOME else _EXPENSE_HINTS
    mapping = INCOME_CATEGORIES if tx_type == TransactionType.INCOME else EXPENSE_CATEGORIES

    for keywords, key in hints:
        if any(k in text for k in keywords):
            return mapping[key]

    return mapping["other"]
