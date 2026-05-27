GOAL_TITLE_PROMPT = (
    "Создание цели\n\n"
    "Введите название, например:\n"
    "<code>Квартира</code> или <code>Отпуск</code>"
)

GOAL_TARGET_PROMPT = (
    "Цель: <b>{title}</b>\n\n"
    "Введите сумму, которую нужно накопить.\n"
    "Пример: <code>1500000</code>"
)

GOAL_DEPOSIT_PROMPT = (
    "Пополнение цели <b>{title}</b>\n\n"
    "Введите сумму, которую откладываете.\n"
    "Пример: <code>10000</code>"
)

INVALID_GOAL_AMOUNT_TEXT = (
    "Не удалось распознать сумму.\n"
    "Введите положительное число, например: <code>50000</code>"
)

GOAL_TITLE_TOO_SHORT = "Название слишком короткое. Введите хотя бы 2 символа."

GOAL_LIMIT_REACHED = (
    "Достигнут лимит активных целей ({limit}). "
    "Завершите или удалите старую цель."
)

GOAL_CREATED_TEXT = "Цель «<b>{title}</b>» создана. Цель: <b>{target}</b>"

GOAL_DELETED_TEXT = "Цель удалена."

GOAL_DELETE_CONFIRM_TEXT = (
    "Удалить цель «<b>{title}</b>»?\n\n"
    "Это действие нельзя отменить."
)

GOAL_COMPLETED_TEXT = (
    "🎉 Поздравляем! Цель «<b>{title}</b>» достигнута!\n"
    "Накоплено: <b>{saved}</b>"
)
