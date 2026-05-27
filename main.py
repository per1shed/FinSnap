"""Запуск бота: python main.py (то же, что python -m bot.main)."""
from bot.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
