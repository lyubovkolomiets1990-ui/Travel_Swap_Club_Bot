from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import (get_user, get_active_trips, get_user_trips,
                add_like, get_liked_users, remove_like,
                create_match, get_existing_match)

router = Router()


async def get_browse_cards(my_telegram_id: int) -> list:
    """
    Повертає унікальні картки для перегляду —
    по одній на користувача (остання активна поїздка).
    Не показує власні поїздки.
    """
    all_trips = await get_active_trips()
    seen_users = set()
    cards = []
    for trip in all_trips:
        tg_id = trip["telegram_id"]
        if tg_id == my_telegram_id:
            continue
        if tg_id in seen_users:
            continue
        seen_users.add(tg_id)
        cards.append(dict(trip))
    return cards


def trip_card_text(trip: dict) -> str:
    from matcher import TRAVELER_TYPES, LOOKING_FOR_LABELS
    tt = TRAVELER_TYPES.get(trip.get("traveler_type", "anyone"), "🌍 Будь-хто")
    lf = LOOKING_FOR_LABELS.get(trip.get("looking_for", "anyone"), "🌍 Будь-кого")
    pets = ""
    if trip.get("has_pets"):
        info = trip.get("pets_info") or "є"
        pets = f"🐾 Тварини: {info}\n"
    return (
        f"👤 *{trip['name']}*\n"
        f"🏠 Живе: {trip['home_city']}, {trip['home_country']}\n"
        f"✈️ Їде до: *{trip['destination_city']}, {trip['destination_country']}*\n"
        f"📅 {trip['date_from']} — {trip['date_to']}\n"
        f"🧳 {tt}  ·  🔍 {lf}\n"
        f"{pets}"
        f"🏡 {trip['home_description'] or 'опис не вказано'}"
    )


def browse_kb(trip: dict, idx: int, total: int) -> object:
    kb = InlineKeyboardBuilder()
    kb.button(text="❤️ Лайк",      callback_data=f"bl_{trip['id']}_{trip['telegram_id']}_{idx}")
    kb.button(text="👎 Далі",       callback_data=f"bs_{idx}")
    kb.adjust(2)
    return kb.as_markup()


async def send_card(message: Message, trip: dict, idx: int, total: int):
    text = trip_card_text(trip)
    kb   = browse_kb(trip, idx, total)
    counter = f"_{idx + 1} з {total}_"
    photos = [p for p in (trip.get("home_photos") or "").split(",") if p]

    if photos:
        await message.answer_photo(
            photo=photos[0],
            caption=f"{text}\n\n{counter}",
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        await message.answer(
            f"{text}\n\n{counter}",
            parse_mode="Markdown",
            reply_markup=kb,
        )


# ── /browse ───────────────────────────────────────────────────────────────────

@router.message(Command("browse"))
async def cmd_browse(message: Message):
    await show_browse(message, message.from_user.id, 0)


@router.callback_query(F.data == "browse_start")
async def browse_start(callback: CallbackQuery):
    await callback.message.answer("🔍 Шукаю мандрівників...")
    await show_browse(callback.message, callback.from_user.id, 0)
    await callback.answer()


async def show_browse(message: Message, my_tg_id: int, idx: int):
    cards = await get_browse_cards(my_tg_id)

    if not cards:
        kb = InlineKeyboardBuilder()
        kb.button(text="✈️ Додати свою поїздку", callback_data="add_trip")
        await message.answer(
            "😔 Поки що немає інших мандрівників з активними поїздками.\n\n"
            "Додайте свою поїздку — і як тільки хтось з'явиться, "
            "ви побачите їх тут! 🔔",
            reply_markup=kb.as_markup(),
        )
        return

    if idx >= len(cards):
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Переглянути знову", callback_data="browse_start")
        await message.answer(
            f"✅ Ви переглянули всіх {len(cards)} мандрівників!\n"
            "Повертайтесь — база росте щодня 🌱",
            reply_markup=kb.as_markup(),
        )
        return

    await send_card(message, cards[idx], idx, len(cards))


# ── Лайк ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("bl_"))
async def browse_like(callback: CallbackQuery, bot):
    # bl_{trip_id}_{owner_tg}_{idx}
    _, trip_id, owner_tg, idx = callback.data.split("_", 3)
    owner_tg   = int(owner_tg)
    idx        = int(idx)
    my_tg_id   = callback.from_user.id

    me   = await get_user(my_tg_id)
    them = await get_user(owner_tg)

    await add_like(my_tg_id, owner_tg)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("❤️ Лайк!")

    # Перевіряємо mutual
    their_likes    = await get_liked_users(owner_tg)
    their_liked_ids = [u["telegram_id"] for u in their_likes]

    if my_tg_id in their_liked_ids:
        await _send_match(bot, callback.message, me, them, my_tg_id, owner_tg)
    else:
        # Повідомляємо іншого
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="👀 Подивитись", callback_data="browse_start")
            await bot.send_message(
                owner_tg,
                f"❤️ *{me['name'] if me else 'Хтось'}* лайкнув вас!\n\n"
                f"🏠 {me['home_city'] if me else ''}, {me['home_country'] if me else ''}\n\n"
                "Якщо вам теж цікаво — лайкніть у відповідь 👇",
                parse_mode="Markdown",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass

    # Наступна картка
    cards   = await get_browse_cards(my_tg_id)
    next_idx = idx + 1
    if next_idx < len(cards):
        await send_card(callback.message, cards[next_idx], next_idx, len(cards))
    else:
        await callback.message.answer("✅ Ви переглянули всіх! Повертайтесь пізніше 🔔")


# ── Пропустити ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("bs_"))
async def browse_skip(callback: CallbackQuery):
    idx = int(callback.data.split("_")[1])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

    cards    = await get_browse_cards(callback.from_user.id)
    next_idx = idx + 1
    if next_idx < len(cards):
        await send_card(callback.message, cards[next_idx], next_idx, len(cards))
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Переглянути знову", callback_data="browse_start")
        await callback.message.answer(
            "✅ Ви переглянули всіх мандрівників!\n"
            "Повертайтесь коли з'являться нові 🔔",
            reply_markup=kb.as_markup(),
        )


# ── Матч ─────────────────────────────────────────────────────────────────────

async def _send_match(bot, message: Message, me, them, my_tg_id: int, owner_tg: int):
    # Зберігаємо матч
    my_trips    = await get_user_trips(my_tg_id)
    their_trips = await get_user_trips(owner_tg)
    if my_trips and their_trips:
        existing = await get_existing_match(my_trips[0]["id"], their_trips[0]["id"])
        if not existing:
            await create_match(my_trips[0]["id"], their_trips[0]["id"])

    safety = (
        "🎊 *Взаємний лайк — це МАТЧ!*\n\n"
        f"👤 *{{name}}* з {{city}}, {{country}}\n\n"
        "─────────────────\n"
        "🛡️ *Перед тим як писати — рекомендуємо:*\n\n"
        "1️⃣ *Відеодзвінок* — познайомтесь наживо перед обміном\n"
        "2️⃣ *Документи на житло* — договір або право власності\n"
        "3️⃣ *Особисті документи* — паспорт або ID\n"
        "4️⃣ *Домовляйтесь письмово* — фіксуйте деталі в чаті\n"
        "─────────────────\n"
        "✅ Після перевірки — сміливо пишіть!"
    )

    # Повідомлення для мене
    kb1 = InlineKeyboardBuilder()
    try:
        chat = await bot.get_chat(owner_tg)
        if chat.username:
            kb1.button(text=f"✉️ Написати {them['name'] if them else ''}", url=f"t.me/{chat.username}")
    except Exception:
        pass
    kb1.button(text="📋 Зрозуміло!", callback_data="safety_ok")
    kb1.adjust(1)

    await message.answer(
        safety.format(
            name=them["name"] if them else "Мандрівник",
            city=them["home_city"] if them else "",
            country=them["home_country"] if them else "",
        ),
        parse_mode="Markdown",
        reply_markup=kb1.as_markup(),
    )

    # Повідомлення для партнера
    kb2 = InlineKeyboardBuilder()
    try:
        chat2 = await bot.get_chat(my_tg_id)
        if chat2.username:
            kb2.button(text=f"✉️ Написати {me['name'] if me else ''}", url=f"t.me/{chat2.username}")
    except Exception:
        pass
    kb2.button(text="📋 Зрозуміло!", callback_data="safety_ok")
    kb2.adjust(1)

    try:
        await bot.send_message(
            owner_tg,
            safety.format(
                name=me["name"] if me else "Мандрівник",
                city=me["home_city"] if me else "",
                country=me["home_country"] if me else "",
            ),
            parse_mode="Markdown",
            reply_markup=kb2.as_markup(),
        )
    except Exception:
        pass


@router.callback_query(F.data == "safety_ok")
async def safety_ok(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Удачі з обміном! 🏡")
