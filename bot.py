import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
import db
import start as start_handler
import trip as trip_handler
import matches as matches_handler
import reviews as reviews_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start",  description="🏠 Головне меню"),
        BotCommand(command="trip",   description="✈️ Додати поїздку"),
        BotCommand(command="saved",  description="❤️ Збережені хости"),
        BotCommand(command="rating", description="📊 Мій рейтинг"),
        BotCommand(command="help",   description="❓ Допомога"),
    ])


async def main():
    logger.info("🚀 Запуск Travel Swap Club Bot...")
    await db.init_db()

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_handler.router)
    dp.include_router(trip_handler.router)
    dp.include_router(matches_handler.router)
    dp.include_router(reviews_handler.router)

    await set_commands(bot)
    me = await bot.get_me()
    logger.info(f"✅ Бот запущено: @{me.username}")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
