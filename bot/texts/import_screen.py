from decimal import Decimal

from bot.constants import TransactionType
from bot.services.screenshot_import.models import DraftTransaction
from bot.texts.messages import format_money

def import_prompt_text(*, tx_label: str | None = None) -> str:
    kind = f" ({tx_label})" if tx_label else ""
    return (
        f"📷 <b>Загрузить скриншот{kind}</b>\n\n"
        "Отправьте <b>фото</b> скрина истории операций из банковского приложения.\n\n"
        "Советы для лучшего распознавания:\n"
        "• полный экран списка, без обрезки\n"
        "• суммы в <b>₽</b> и названия магазинов видны целиком\n"
        "• светлая или тёмная тема — обе подходят\n\n"
        "Перед записью вы проверите список."
    )


IMPORT_PROMPT = import_prompt_text()

IMPORT_PROCESSING = "⏳ Разбираю скрин, подождите…"

IMPORT_EMPTY = (
    "Не удалось найти операции на скрине.\n\n"
    "Попробуйте:\n"
    "• другой скрин — экран <b>истории операций</b>, не карточка счёта\n"
    "• увеличить масштаб / отправить как <b>файл</b> (не сжатое превью)\n"
    "• убедиться, что видны суммы с <b>₽</b>"
)

IMPORT_TOO_MANY = "На скрине слишком много операций. Запишем первые 15 — проверьте список."


def format_review_screen(drafts: list[DraftTransaction]) -> str:
    total_expense = sum(
        d.amount for d in drafts if d.tx_type == TransactionType.EXPENSE
    )
    total_income = sum(
        d.amount for d in drafts if d.tx_type == TransactionType.INCOME
    )

    lines = [
        "📷 <b>Проверьте операции</b>",
        f"Найдено: <b>{len(drafts)}</b>",
    ]
    if total_expense > 0 or total_income > 0:
        lines.append("")
        lines.append("<b>Итого:</b>")
        if total_expense > 0:
            lines.append(f"➖ Расходы: <b>{format_money(total_expense)}</b>")
        if total_income > 0:
            lines.append(f"➕ Доходы: <b>{format_money(total_income)}</b>")
    lines.append("")

    for i, d in enumerate(drafts, start=1):
        if d.tx_type == TransactionType.INCOME:
            kind = "Доход"
            sign = "➕"
        else:
            kind = "Расход"
            sign = "➖"
        lines.append(f"{i}. {sign} <b>{format_money(d.amount)}</b> — {kind}")
        lines.append(f"   {_escape(d.comment)}")
        if d.bank_category:
            lines.append(f"   <i>{_escape(d.bank_category)}</i>")
        lines.append(f"   Категория в боте: {_escape(d.category)}")
        lines.append("")
    lines.append("Если всё верно — нажмите «Записать».")
    return "\n".join(lines)


def format_saved_summary(count: int, total_expense: Decimal, total_income: Decimal) -> str:
    parts = [f"✅ Записано операций: <b>{count}</b>"]
    if total_expense > 0:
        parts.append(f"Расходы: <b>{format_money(total_expense)}</b>")
    if total_income > 0:
        parts.append(f"Доходы: <b>{format_money(total_income)}</b>")
    return "\n".join(parts)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
