"""
Нагадування — запускається як фонова задача в bot.py
Перевіряє кожні 12 годин і надсилає потрібні повідомлення
"""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

import db

logger = logging.getLogger(__name__)


async def run_reminders(bot: Bot):
    """Нескінченний цикл — перевірка кожні 12 годин"""
    while True:
        try:
            await check_all(bot)
        except Exception as e:
            logger.error(f"Помилка нагадувань: {e}")
        await asyncio.sleep(60 * 60 * 12)  # кожні 12 годин


async def check_all(bot: Bot):
    logger.info("🔔 Перевірка нагадувань...")
    await remind_upcoming_trips(bot)
    await remind_pending_reviews(bot)
    await remind_inactive_matches(bot)
    logger.info("✅ Нагадування перевірено")


async def remind_upcoming_trips(bot: Bot):
    """Нагадати за 3 дні до поїздки"""
    trips = await db.get_active_trips()
    today = datetime.now().date()
    fmt = "%d.%m.%Y"

    for trip in trips:
        try:
            date_from = datetime.strptime(trip["date_from"], fmt).date()
            days_left = (date_from - today).days
            if days_left == 3:
                await bot.send_message(
                    trip["telegram_id"],
                    f"✈️ *Нагадування про поїздку!*\n\n"
                    f"Через 3 дні ви їдете до "
                    f"*{trip['destination_city']}, {trip['destination_country']}*\n\n"
                    "📋 *Що варто зробити заздалегідь:*\n"
                    "• Підтвердити деталі з партнером по обміну\n"
                    "• Передати пароль від Wi-Fi і ключі\n"
                    "• Розповісти про правила будинку\n"
                    "• Залишити контакт сусіда або керуючого\n\n"
                    "Гарної поїздки! 🌍",
                    parse_mode="Markdown",
                )
        except Exception:
            pass


async def remind_pending_reviews(bot: Bot):
    """Нагадати залишити відгук через 3 дні після обміну"""
    trips = await db.get_active_trips()
    today = datetime.now().date()
    fmt = "%d.%m.%Y"

    for trip in trips:
        try:
            date_to = datetime.strptime(trip["date_to"], fmt).date()
            days_after = (today - date_to).days

            if days_after == 3:
                # Перевіряємо чи є матч і чи є відгук
                my_trips = await db.get_user_trips(trip["telegram_id"])
                for t in my_trips:
                    user = await db.get_user(trip["telegram_id"])
                    if not user:
                        continue
                    review = await db.get_review(t["id"], user["id"])
                    if not review:
                        from aiogram.utils.keyboard import InlineKeyboardBuilder
                        kb = InlineKeyboardBuilder()
                        kb.button(text="⭐️ Залишити відгук", callback_data=f"start_review_{t['id']}")
                        await bot.send_message(
                            trip["telegram_id"],
                            f"📝 *Як пройшов обмін?*\n\n"
                            f"Ви повернулись з поїздки до "
                            f"*{trip['destination_city']}*.\n\n"
                            "Будь ласка, залиште відгук про вашого партнера — "
                            "це допомагає спільноті обирати надійних хостів! 🙏",
                            parse_mode="Markdown",
                            reply_markup=kb.as_markup(),
                        )
        except Exception:
            pass


async def remind_inactive_matches(bot: Bot):
    """Нагадати якщо матч більше 7 днів без відповіді — лише ОДИН раз на матч,
    незалежно від того скільки разів бот перезапускався."""
    matches = await db.get_pending_matches()
    today = datetime.now()
    fmt = "%Y-%m-%d %H:%M:%S"

    for match in matches:
        try:
            # Якщо нагадування вже надсилалось для цього матчу — пропускаємо
            already_sent = match["reminder_sent"] if "reminder_sent" in match.keys() else 0
            if already_sent:
                continue

            created = datetime.strptime(match["created_at"][:19], fmt)
            days_waiting = (today - created).days

            if days_waiting >= 7:
                # Повідомляємо обох учасників
                trips = await db.get_active_trips()
                trip_map = {t["id"]: t for t in trips}

                for trip_id in (match["trip_id_1"], match["trip_id_2"]):
                    trip = trip_map.get(trip_id)
                    if trip:
                        from aiogram.utils.keyboard import InlineKeyboardBuilder
                        kb = InlineKeyboardBuilder()
                        kb.button(text="🔍 Переглянути матч", callback_data="browse_start")
                        try:
                            await bot.send_message(
                                trip["telegram_id"],
                                "⏰ *Нагадування про матч*\n\n"
                                "У вас є потенційний партнер по обміну який чекає відповіді "
                                "вже 7 днів.\n\n"
                                "Зайдіть і подивіться — можливо це ваш ідеальний варіант! 👀",
                                parse_mode="Markdown",
                                reply_markup=kb.as_markup(),
                            )
                        except Exception:
                            pass

                # Позначаємо що нагадування вже надіслано — більше не повторюватиметься
                await db.mark_reminder_sent(match["id"])
        except Exception:
            pass
