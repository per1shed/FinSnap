# FinSnap

Telegram-бот для учёта личных доходов и расходов (MVP).

## Стек

- Python 3.13, aiogram 3
- PostgreSQL 16, asyncpg
- Matplotlib (круговая диаграмма расходов)
- Docker Compose

## Быстрый старт

1. Создайте бота у [@BotFather](https://t.me/BotFather) и скопируйте токен.

2. В файле `.env` укажите `BOT_TOKEN`, надёжный `POSTGRES_PASSWORD` и при необходимости `ADMIN_IDS` (ваш Telegram user id, можно несколько через запятую).

3. Запуск:

```bash
docker compose up --build
```

## Локальная разработка без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Поднимите только базу в Docker (в `.env` должен быть `POSTGRES_HOST=localhost`):

```bash
docker compose up db -d
```

Запуск бота:

```bash
python main.py
```

При полном запуске через `docker compose up` хост `db` для бота задаётся автоматически в `docker-compose.yml`.

## Команды бота

- `/start` — главное меню: баланс, доходы и расходы за текущий календарный месяц
- Inline-кнопки: добавить расход/доход, статистика с диаграммой за неделю или месяц

Формат ввода операции: `сумма комментарий`, например `450 такси`.

## Структура

```
bot/
  main.py           — точка входа
  config.py         — настройки из .env
  db/               — схема и SQL-запросы
  handlers/         — обработчики Telegram
  keyboards/        — inline-клавиатуры
  services/         — парсер суммы, генерация графиков
```
