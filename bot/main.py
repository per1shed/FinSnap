import asyncio
import logging

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject

from bot.config import Settings, load_settings
from bot.db.pool import close_pool, get_pool, init_pool
from bot.services.user_profile import sync_user_profile
from bot.handlers import setup_routers
from bot.logging_setup import setup_logging

logger = setup_logging()


async def main() -> None:
    settings = load_settings()
    logger.info("⚙️ Загрузка настроек завершена (TZ=%s)", settings.timezone)

    await init_pool(settings)
    logger.info(
        "🗄️ Подключение к PostgreSQL: %s:%s/%s",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    class SettingsMiddleware(BaseMiddleware):
        def __init__(self, app_settings: Settings) -> None:
            self.app_settings = app_settings

        async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any],
        ) -> Any:
            data["settings"] = self.app_settings
            return await handler(event, data)

    class UserProfileMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any],
        ) -> Any:
            tg_user = data.get("event_from_user")
            if tg_user is not None:
                await sync_user_profile(get_pool(), tg_user)
            return await handler(event, data)

    dp.update.middleware(SettingsMiddleware(settings))
    dp.update.middleware(UserProfileMiddleware())
    dp.include_router(setup_routers())

    bot_info = await bot.get_me()
    logger.info(
        "🚀 Бот @%s (%s) начал работу — ожидаю сообщения",
        bot_info.username,
        bot_info.full_name,
    )

    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("⏹️ Получен сигнал остановки")
        raise
    finally:
        logger.info("🛑 Бот @%s завершил работу", bot_info.username)
        await bot.session.close()
        await close_pool()
        logger.info("🔌 Соединения закрыты, до встречи!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по Ctrl+C")
