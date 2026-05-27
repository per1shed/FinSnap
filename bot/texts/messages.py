from decimal import Decimal

MONTH_NAMES_RU = (
    "",
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)


def format_money(amount: Decimal) -> str:
    quantized = amount.quantize(Decimal("0.01"))
    text = f"{quantized:,.2f}".replace(",", " ")
    if text.endswith(".00"):
        text = text[:-3]
    return f"{text} ₽"


def main_menu_text(
    income: Decimal,
    expense: Decimal,
    month: int,
    year: int,
    total_balance: Decimal,
    goals_hint: str = "",
) -> str:
    month_balance = income - expense
    month_name = MONTH_NAMES_RU[month]
    return (
        f"💸<b>FinSnap</b> — учёт финансов\n\n"
        f"Период: <b>{month_name} {year}</b>\n"
        f"Доходы: <b>{format_money(income)}</b>\n"
        f"Расходы: <b>{format_money(expense)}</b>\n"
        f"Баланс месяца: <b>{format_money(month_balance)}</b>\n\n"
        f"💵Общий баланс: <b>{format_money(total_balance)}</b>"
        f"{goals_hint}"
    )


def category_prompt(tx_label: str, category_label: str) -> str:
    return (
        f"Категория: <b>{category_label}</b>\n\n"
        f"Введите сумму и комментарий одним сообщением.\n"
        f"Пример: <code>450 такси</code>"
    )


WRONG_INPUT_NOTICE = (
    "⛔️ Сейчас такой ввод не ожидался. Повторите попытку."
)

WRONG_INPUT_NEED_TEXT = "Нужно отправить текстовое сообщение."


def wrong_input_notice_text(*, detail: str | None = None) -> str:
    """Только предупреждение — отдельным сообщением, без текста экрана."""
    if detail:
        return f"{WRONG_INPUT_NOTICE}\n\n{detail}"
    return WRONG_INPUT_NOTICE


INVALID_AMOUNT_TEXT = (
    "Не удалось распознать сумму.\n"
    "Введите число в начале, например: <code>450 такси</code>"
)

NO_EXPENSES_TEXT = "За выбранный период расходов нет — диаграмма не построена."

STATS_TYPE_TEXT = "Что строим?"

STATS_PERIOD_TEXT_EXPENSE = "Выберите период для диаграммы расходов:"
STATS_PERIOD_TEXT_INCOME = "Выберите период для диаграммы доходов:"

STATS_KIND_TEXT_EXPENSE = "Выберите тип графика для расходов:"
STATS_KIND_TEXT_INCOME = "Выберите тип графика для доходов:"

CHART_BUILDING_TEXT = "⏳ Подождите, диаграмма строится..."

NO_INCOME_TEXT = "За выбранный период доходов нет — диаграмма не построена."

NO_EXPENSES_MONTH_DAILY_TEXT = "В текущем месяце расходов нет — гистограмма не построена."
NO_INCOME_MONTH_DAILY_TEXT = "В текущем месяце доходов нет — гистограмма не построена."

TIMEZONE_PROMPT = (
    "Добро пожаловать в <b>FinSnap</b>!\n\n"
    "Сколько сейчас <b>часов</b> у вас? (только час, без минут)\n\n"
    "Введите число от <code>0</code> до <code>23</code>\n"
    "Пример: <code>14</code>"
)


def timezone_change_prompt(current_offset_label: str | None = None) -> str:
    current_line = ""
    if current_offset_label:
        current_line = f"Сейчас: <b>{current_offset_label}</b>\n\n"
    return (
        f"🕐 <b>Смена часового пояса</b>\n\n"
        f"{current_line}"
        "Сколько сейчас <b>часов</b> у вас? (только час, без минут)\n\n"
        "Введите число от <code>0</code> до <code>23</code>\n"
        "Пример: <code>14</code>"
    )

WELCOME_TEXT = (
    "👋 <b>Добро пожаловать в FinSnap!</b>\n\n"
    "Кратко о возможностях бота:\n\n"
    "📋 <b>Главное меню</b>\n"
    "Доходы и расходы за текущий месяц, баланс месяца и "
    "💵общий баланс за всё время.\n\n"
    "➖ <b>Расход</b> и ➕ <b>Доход</b>\n"
    "Выберите категорию и отправьте сумму с комментарием одним сообщением.\n"
    "Пример: <code>450 такси</code>\n\n"
    "📊 <b>Статистика</b>\n"
    "Круговые диаграммы по категориям (неделя / месяц) и гистограмма "
    "по дням текущего месяца — для расходов и доходов.\n\n"
    "🎯 <b>Финансовые цели</b>\n"
    "Создавайте цели, пополняйте накопления и смотрите прогресс на диаграммах.\n\n"
    "Все действия — через кнопки под сообщениями. "
    "Бот показывает один актуальный экран за раз.\n\n"
    "Нажмите кнопку ниже, чтобы открыть меню."
)


def welcome_screen_text(*, timezone_note: str = "") -> str:
    if timezone_note:
        return f"{timezone_note}\n\n{WELCOME_TEXT}"
    return WELCOME_TEXT

INVALID_TIME_TEXT = (
    "Не удалось распознать час.\n"
    "Введите число от <code>0</code> до <code>23</code>, например: <code>9</code> или <code>21</code>"
)
