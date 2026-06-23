import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

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
        BotCommand(command="browse",   description="🔍 Переглянути мандрівників"),
        BotCommand(command="calendar", description="📅 Календар доступності"),
        BotCommand(command="top",      description="⭐️ Топ за рейтингом"),
        BotCommand(command="find_home", description="🏠 Куди я хочу поїхати"),
        BotCommand(command="find_to_me", description="📥 Хто їде до мене"),
        BotCommand(command="edit_profile", description="✏️ Змінити профіль"),
        BotCommand(command="delete_profile", description="🗑 Видалити профіль"),
        BotCommand(command="help",   description="❓ Допомога"),
    ])


async def main():
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        logger.error("❌ BOT_TOKEN не вказано! Додайте змінну у Railway → Variables")
        sys.exit(1)

    db_path = os.getenv("DB_PATH", "/data/home_exchange.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    import db
    import start as start_handler
    import trip as trip_handler
    import matches as matches_handler
    import reviews as reviews_handler
    import browse as browse_handler
    import calendar_avail as calendar_handler
    from reminders import run_reminders

    logger.info("🚀 Запуск Travel Swap Club Bot...")
    await db.init_db()

    bot = Bot(token=token)
    dp  = Dispatcher(storage=MemoryStorage())

    from ban_middleware import BanCheckMiddleware
    dp.update.outer_middleware(BanCheckMiddleware())

    dp.include_router(start_handler.router)
    dp.include_router(trip_handler.router)
    dp.include_router(matches_handler.router)
    dp.include_router(reviews_handler.router)
    dp.include_router(browse_handler.router)
    dp.include_router(calendar_handler.router)

    from db import init_calendar_table, init_views_table, init_bans_table
    await init_calendar_table()
    await init_views_table()
    await init_bans_table()
    asyncio.create_task(run_reminders(bot))
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
