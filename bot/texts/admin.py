ADMIN_ACCESS_DENIED = "Нет доступа."

ADMIN_USERS_SEARCH_PROMPT = (
    "🔍 <b>Поиск пользователя</b>\n\n"
    "Отправьте <b>ID</b> (число) или <b>username</b> без @ или с @.\n"
    "Пример: <code>123456789</code> или <code>ivanov</code>"
)

ADMIN_USER_NOT_FOUND = "Пользователь не найден. Проверьте ID или username."

ADMIN_INVALID_SEARCH = (
    "Не удалось распознать запрос.\n"
    "Введите числовой ID или username."
)

ADMIN_BROADCAST_PROMPT = (
    "📢 <b>Рассылка</b>\n\n"
    "Отправьте текст сообщения для всех пользователей.\n"
    "Поддерживается разметка <b>HTML</b> (как в Telegram).\n\n"
    "У получателей будет одна зелёная кнопка «Понятно» — "
    "после нажатия сообщение рассылки исчезнет, "
    "останется их предыдущий экран бота."
)

ADMIN_BROADCAST_EMPTY = "Текст рассылки не может быть пустым."

ADMIN_BROADCAST_PREVIEW_HEADER = "📢 <b>Предпросмотр рассылки</b>\n\n"

ADMIN_BROADCAST_PREVIEW_FOOTER = (
    "\n\n—\n"
    "Получателей: <b>{count}</b>\n"
    "Отправить?"
)

ADMIN_BROADCAST_RESULT = (
    "📢 <b>Рассылка завершена</b>\n\n"
    "Доставлено: <b>{ok}</b>\n"
    "Не доставлено: <b>{fail}</b>"
)
