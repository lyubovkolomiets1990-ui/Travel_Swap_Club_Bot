from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import get_user, get_active_trips, get_user_trips, add_like, get_liked_users, remove_like, create_match, get_existing_match

router = Router()


async def get_all_other_trips(my_telegram_id: int) -> list:
    """Всі активні поїздки крім моїх"""
    all_trips = await get_active_trips()
    return [t for t in all_trips if t["telegram_id"] != my_telegram_id]


def trip_card_text(trip) -> str:
    from matcher import TRAVELER_TYPES, LOOKING_FOR_LABELS
    tt = TRAVELER_TYPES.get(trip.get("traveler_type", "anyone"), "🌍")
    lf = LOOKING_FOR_LABELS.get(trip.get("looking_for", "anyone"), "🌍 Будь-кого")
    return (
        f"👤 *{trip['name']}*\n"
        f"🏠 Живе: {trip['home_city']}, {trip['home_country']}\n"
        f"✈️ Їде до: {trip['destination_city']}, {trip['destination_country']}\n"
        f"📅 {trip['date_from']} — {trip['date_to']}\n"
        f"🧳 Тип: {tt}  ·  🔍 Шукає: {lf}\n"
        f"🏡 Житло: {trip['home_description'] or 'не вказано'}"
    )


def browse_kb(trip_id: int, owner_tg: int, current_idx: int, total: int) -> object:
    kb = InlineKeyboardBuilder()
    kb.button(text="❤️ Лайк",      callback_data=f"browse_like_{trip_id}_{owner_tg}_{current_idx}")
    kb.button(text="👎 Пропустити", callback_data=f"browse_skip_{current_idx}")
    if current_idx + 1 < total:
        kb.button(text=f"➡️ Далі ({current_idx+1}/{total})", callback_data=f"browse_next_{current_idx + 1}")
    kb.adjust(2)
    return kb.as_markup()


# ── /browse — переглянути всіх ───────────────────────────────────────────────

@router.message(Command("browse"))
async def cmd_browse(message: Message):
    await show_browse(message.from_user.id, message, 0)


@router.callback_query(F.data == "browse_start")
async def browse_start(callback: CallbackQuery):
    await callback.message.answer("🔍 Шукаю мандрівників...")
    await show_browse(callback.from_user.id, callback.message, 0)
    await callback.answer()


async def show_browse(my_tg_id: int, message: Message, idx: int):
    trips = await get_all_other_trips(my_tg_id)
    if not trips:
        await message.answer(
            "😔 Поки що немає інших мандрівників.\n"
            "Поверніться пізніше — база росте щодня! 🌱"
        )
        return

    if idx >= len(trips):
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Переглянути знову", callback_data="browse_start")
        await message.answer(
            "✅ Ви переглянули всіх мандрівників!\n"
            "Повертайтесь коли з'являться нові 🔔",
            reply_markup=kb.as_markup(),
        )
        return

    trip = trips[idx]
    text = trip_card_text(trip)
    kb = browse_kb(trip["id"], trip["telegram_id"], idx, len(trips))

    # Надсилаємо фото якщо є
    photos = [p for p in (trip.get("home_photos") or "").split(",") if p]
    if photos:
        await message.answer_photo(
            photo=photos[0],
            caption=text,
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)


# ── Лайк ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("browse_like_"))
async def browse_like(callback: CallbackQuery, bot):
    parts = callback.data.split("_")
    # browse_like_{trip_id}_{owner_tg}_{current_idx}
    trip_id    = int(parts[2])
    owner_tg   = int(parts[3])
    current_idx = int(parts[4])

    my_tg_id = callback.from_user.id
    me = await get_user(my_tg_id)
    them = await get_user(owner_tg)

    # Зберігаємо лайк
    await add_like(my_tg_id, owner_tg)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("❤️ Лайк!")

    # Перевіряємо чи вони вже лайкнули нас
    their_likes = await get_liked_users(owner_tg)
    their_liked_ids = [u["telegram_id"] for u in their_likes]

    if my_tg_id in their_liked_ids:
        # 🎉 Mutual like — матч!
        # Знаходимо їхню поїздку і мою
        my_trips = await get_user_trips(my_tg_id)
        their_trips = await get_user_trips(owner_tg)

        if my_trips and their_trips:
            existing = await get_existing_match(my_trips[0]["id"], their_trips[0]["id"])
            if not existing:
                await create_match(my_trips[0]["id"], their_trips[0]["id"])

        # Повідомляємо обох
        match_text_me = (
            f"🎊 *Взаємний лайк — це МАТЧ!*\n\n"
            f"👤 {them['name'] if them else 'Мандрівник'}\n"
            f"🏠 {them['home_city'] if them else ''}, {them['home_country'] if them else ''}\n\n"
            "📱 Напишіть одне одному і домовляйтесь про обмін!"
        )
        match_text_them = (
            f"🎊 *Взаємний лайк — це МАТЧ!*\n\n"
            f"👤 {me['name'] if me else 'Мандрівник'}\n"
            f"🏠 {me['home_city'] if me else ''}, {me['home_country'] if me else ''}\n\n"
            "📱 Напишіть одне одному і домовляйтесь про обмін!"
        )

        kb_contact = InlineKeyboardBuilder()
        try:
            chat = await bot.get_chat(owner_tg)
            if chat.username:
                kb_contact.button(text=f"✉️ Написати {them['name'] if them else ''}", url=f"t.me/{chat.username}")
        except Exception:
            pass

        await callback.message.answer(match_text_me, parse_mode="Markdown",
                                       reply_markup=kb_contact.as_markup() if kb_contact.export() else None)

        kb_contact2 = InlineKeyboardBuilder()
        try:
            chat2 = await bot.get_chat(my_tg_id)
            if chat2.username:
                kb_contact2.button(text=f"✉️ Написати {me['name'] if me else ''}", url=f"t.me/{chat2.username}")
        except Exception:
            pass

        try:
            await bot.send_message(owner_tg, match_text_them, parse_mode="Markdown",
                                   reply_markup=kb_contact2.as_markup() if kb_contact2.export() else None)
        except Exception:
            pass
    else:
        # Повідомляємо іншого що хтось лайкнув
        try:
            kb_notify = InlineKeyboardBuilder()
            kb_notify.button(text="👀 Переглянути профіль", callback_data="browse_start")
            await bot.send_message(
                owner_tg,
                f"❤️ *{me['name'] if me else 'Хтось'}* лайкнув ваш профіль!\n\n"
                f"🏠 {me['home_city'] if me else ''}, {me['home_country'] if me else ''}\n\n"
                "Якщо вам теж цікаво — зайдіть і лайкніть у відповідь 👇",
                parse_mode="Markdown",
                reply_markup=kb_notify.as_markup(),
            )
        except Exception:
            pass

    # Показуємо наступну картку
    trips = await get_all_other_trips(my_tg_id)
    next_idx = current_idx + 1
    if next_idx < len(trips):
        trip = trips[next_idx]
        text = trip_card_text(trip)
        kb = browse_kb(trip["id"], trip["telegram_id"], next_idx, len(trips))
        photos = [p for p in (trip.get("home_photos") or "").split(",") if p]
        if photos:
            await callback.message.answer_photo(photo=photos[0], caption=text,
                                                 parse_mode="Markdown", reply_markup=kb)
        else:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await callback.message.answer("✅ Ви переглянули всіх! Повертайтесь пізніше 🔔")


# ── Пропустити ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("browse_skip_"))
async def browse_skip(callback: CallbackQuery):
    current_idx = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("👎 Пропущено")

    trips = await get_all_other_trips(callback.from_user.id)
    next_idx = current_idx + 1
    if next_idx < len(trips):
        trip = trips[next_idx]
        text = trip_card_text(trip)
        kb = browse_kb(trip["id"], trip["telegram_id"], next_idx, len(trips))
        photos = [p for p in (trip.get("home_photos") or "").split(",") if p]
        if photos:
            await callback.message.answer_photo(photo=photos[0], caption=text,
                                                 parse_mode="Markdown", reply_markup=kb)
        else:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await callback.message.answer("✅ Ви переглянули всіх! Повертайтесь пізніше 🔔")


# ── Наступна картка ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("browse_next_"))
async def browse_next(callback: CallbackQuery):
    idx = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await show_browse(callback.from_user.id, callback.message, idx)
