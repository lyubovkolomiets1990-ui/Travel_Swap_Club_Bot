from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_match, update_match_status, get_active_trips, get_user

router = Router()

# Зберігаємо хто вже прийняв матч: {match_id: set of sides}
accepted_sides: dict[int, set] = {}


async def get_trip_user_telegram_id(trip_id: int) -> int | None:
    """Отримує telegram_id власника поїздки"""
    trips = await get_active_trips()
    for trip in trips:
        if trip["id"] == trip_id:
            return trip["telegram_id"]
    return None


@router.callback_query(F.data.startswith("accept_"))
async def accept_match(callback: CallbackQuery, bot):
    parts = callback.data.split("_")
    match_id = int(parts[1])
    side = int(parts[2])  # 1 або 2

    match = await get_match(match_id)
    if not match:
        await callback.answer("❌ Матч не знайдено", show_alert=True)
        return

    if match["status"] == "declined":
        await callback.answer("❌ Цей матч вже відхилено", show_alert=True)
        return

    if match["status"] == "accepted":
        await callback.answer("✅ Матч вже підтверджено!", show_alert=True)
        return

    # Запам'ятовуємо підтвердження
    if match_id not in accepted_sides:
        accepted_sides[match_id] = set()
    accepted_sides[match_id].add(side)

    await callback.message.edit_reply_markup(reply_markup=None)

    if len(accepted_sides[match_id]) < 2:
        # Чекаємо другого
        await callback.message.answer(
            "✅ *Ви прийняли пропозицію!*\n\n"
            "⏳ Чекаємо підтвердження від іншої сторони...",
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # Обидва прийняли!
    await update_match_status(match_id, "accepted")
    del accepted_sides[match_id]

    # Отримуємо дані обох учасників
    trip_1_telegram = await get_trip_user_telegram_id(match["trip_id_1"])
    trip_2_telegram = await get_trip_user_telegram_id(match["trip_id_2"])

    user_1 = await get_user(trip_1_telegram) if trip_1_telegram else None
    user_2 = await get_user(trip_2_telegram) if trip_2_telegram else None

    success_msg_1 = (
        f"🎊 *Матч підтверджено обома сторонами!*\n\n"
        f"Ваш партнер по обміну:\n"
        f"👤 {user_2['name'] if user_2 else 'Невідомо'}\n"
        f"🏠 {user_2['home_city']}, {user_2['home_country'] if user_2 else ''}\n\n"
        "📱 Напишіть одне одному і домовляйтесь!\n\n"
        f"Зв'язок: @{(await bot.get_chat(trip_2_telegram)).username or 'недоступний'}"
        if trip_2_telegram else ""
    )

    success_msg_2 = (
        f"🎊 *Матч підтверджено обома сторонами!*\n\n"
        f"Ваш партнер по обміну:\n"
        f"👤 {user_1['name'] if user_1 else 'Невідомо'}\n"
        f"🏠 {user_1['home_city']}, {user_1['home_country'] if user_1 else ''}\n\n"
        "📱 Напишіть одне одному і домовляйтесь!\n\n"
        f"Зв'язок: @{(await bot.get_chat(trip_1_telegram)).username or 'недоступний'}"
        if trip_1_telegram else ""
    )

    try:
        if trip_1_telegram:
            await bot.send_message(trip_1_telegram, success_msg_1, parse_mode="Markdown")
        if trip_2_telegram:
            await bot.send_message(trip_2_telegram, success_msg_2, parse_mode="Markdown")
    except Exception as e:
        print(f"Помилка надсилання: {e}")

    await callback.answer("🎊 Матч підтверджено!", show_alert=True)


@router.callback_query(F.data.startswith("decline_"))
async def decline_match(callback: CallbackQuery, bot):
    match_id = int(callback.data.split("_")[1])

    match = await get_match(match_id)
    if not match:
        await callback.answer("❌ Матч не знайдено", show_alert=True)
        return

    await update_match_status(match_id, "declined")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Пропозицію відхилено.")

    # Повідомити іншу сторону
    trip_1_tid = await get_trip_user_telegram_id(match["trip_id_1"])
    trip_2_tid = await get_trip_user_telegram_id(match["trip_id_2"])

    other_tid = trip_2_tid if callback.from_user.id == trip_1_tid else trip_1_tid
    if other_tid and other_tid != callback.from_user.id:
        try:
            await bot.send_message(
                other_tid,
                "😔 На жаль, інша сторона відхилила пропозицію обміну.\n"
                "Продовжуємо пошук матчів! 🔍",
            )
        except Exception:
            pass

    await callback.answer()
