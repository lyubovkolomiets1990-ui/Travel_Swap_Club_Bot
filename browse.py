from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import (get_user, get_active_trips, get_user_trips,
                add_like, get_liked_users, remove_like,
                create_match, get_existing_match,
                mark_viewed, get_viewed_ids, get_user_rating)

router = Router()


class AskQuestion(StatesGroup):
    waiting_question = State()



async def get_browse_cards(my_telegram_id: int, skip_viewed: bool = True,
                           sort_by_rating: bool = False) -> list:
    """Показуємо тільки повні профілі — є місто, опис і фото.
    skip_viewed=True приховує тих, кого вже лайкнули/скіпнули раніше.
    sort_by_rating=True сортує від найвищого рейтингу до найнижчого."""
    all_trips = await get_active_trips()
    viewed_ids = await get_viewed_ids(my_telegram_id) if skip_viewed else set()
    seen_users = set()
    cards = []
    for trip in all_trips:
        tg_id = trip["telegram_id"]
        if tg_id == my_telegram_id:
            continue
        if tg_id in seen_users:
            continue
        if tg_id in viewed_ids:
            continue
        trip_keys = trip.keys()
        has_city  = ("home_city" in trip_keys and trip["home_city"]) and trip["home_city"] not in ("", "None")
        has_desc  = ("home_description" in trip_keys and trip["home_description"]) and trip["home_description"] not in ("", "None")
        has_photo = ("home_photos" in trip_keys and trip["home_photos"]) and trip["home_photos"] not in ("", "None")
        if not (has_city and has_desc and has_photo):
            continue
        seen_users.add(tg_id)
        cards.append(dict(trip))

    if sort_by_rating:
        for card in cards:
            rating = await get_user_rating(card["user_id"])
            card["_avg_rating"] = rating.get("average", 0) if rating else 0
            card["_review_count"] = rating.get("total", 0) if rating else 0
        # Спочатку ті у кого є відгуки і вищий рейтинг, потім без відгуків
        cards.sort(key=lambda c: (c["_review_count"] > 0, c["_avg_rating"]), reverse=True)

    return cards


async def trip_card_text(trip: dict) -> str:
    from matcher import TRAVELER_TYPES, LOOKING_FOR_LABELS
    tt = TRAVELER_TYPES.get(trip.get("traveler_type", "anyone"), "будь-хто")
    lf = LOOKING_FOR_LABELS.get(trip.get("looking_for", "anyone"), "будь-кого")
    pets = ""
    if trip.get("has_pets"):
        info = trip.get("pets_info") or "є"
        pets = "Тварини: " + info + "\n"
    name = trip.get("name", "")
    home_city = trip.get("home_city", "")
    home_country = trip.get("home_country", "")
    dest_city = trip.get("destination_city", "")
    dest_country = trip.get("destination_country", "")
    date_from_raw = trip.get("date_from", "") or ""
    date_to_raw = trip.get("date_to", "") or ""
    if date_from_raw == "гнучко" or not date_from_raw:
        date_from = "гнучкі дати"
        date_to = ""
    else:
        date_from = date_from_raw
        date_to = date_to_raw
    desc = trip.get("home_description") or "опис не вказано"

    rating_line = ""
    user_id = trip.get("user_id")
    if user_id:
        rating = await get_user_rating(user_id)
        if rating and rating.get("total"):
            stars = "⭐️" * round(rating["average"])
            rating_line = "Рейтинг: " + str(rating["average"]) + " " + stars + " (" + str(rating["total"]) + " відгуків)\n"

    return (
        "*" + name + "*\n"
        + rating_line +
        "Живе: " + home_city + ", " + home_country + "\n"
        "Їде до: *" + dest_city + ", " + dest_country + "*\n"
        "Дати: " + (date_from + (" - " + date_to if date_to else "")) + "\n"
        + pets +
        "Житло: " + desc
    )


def browse_kb(trip: dict, idx: int, total: int):
    kb = InlineKeyboardBuilder()
    tid = trip["id"]
    tg = trip["telegram_id"]
    kb.button(text="❤️ Лайк", callback_data="bl_" + str(tid) + "_" + str(tg) + "_" + str(idx))
    kb.button(text="❓ Запитати", callback_data="bq_" + str(tg) + "_" + str(idx))
    kb.button(text="👎 Далі", callback_data="bs_" + str(idx))
    kb.adjust(2, 1)
    return kb.as_markup()


async def send_card(message: Message, trip: dict, idx: int, total: int):
    text = await trip_card_text(trip)
    kb = browse_kb(trip, idx, total)
    counter = "_" + str(idx + 1) + " з " + str(total) + "_"
    photos = [p for p in (trip.get("home_photos") or "").split(",") if p]
    if photos:
        await message.answer_photo(
            photo=photos[0],
            caption=text + "\n\n" + counter,
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        await message.answer(
            text + "\n\n" + counter,
            parse_mode="Markdown",
            reply_markup=kb,
        )


@router.message(Command("browse"))
async def cmd_browse(message: Message):
    await show_browse(message, message.from_user.id, 0)


@router.message(Command("top"))
async def cmd_top(message: Message):
    await message.answer("⭐️ Шукаю мандрівників з найвищим рейтингом...")
    await show_browse(message, message.from_user.id, 0, sort_by_rating=True)


@router.callback_query(F.data == "browse_top")
async def browse_top(callback: CallbackQuery):
    await callback.message.answer("⭐️ Шукаю мандрівників з найвищим рейтингом...")
    await show_browse(callback.message, callback.from_user.id, 0, sort_by_rating=True)
    await callback.answer()


@router.callback_query(F.data == "browse_start")
async def browse_start(callback: CallbackQuery):
    await callback.message.answer("Шукаю мандрівників...")
    await show_browse(callback.message, callback.from_user.id, 0)
    await callback.answer()


@router.callback_query(F.data == "browse_reset")
async def browse_reset(callback: CallbackQuery):
    """Переглянути всіх знову — включно з раніше скіпнутими"""
    import db as _db
    async with _db.aiosqlite.connect(_db.DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM browse_views WHERE viewer_telegram_id=?",
            (callback.from_user.id,),
        )
        await conn.commit()
    await callback.message.answer("🔄 Список оновлено — показую всіх знову!")
    await show_browse(callback.message, callback.from_user.id, 0)
    await callback.answer()


async def show_browse(message: Message, my_tg_id: int, idx: int, sort_by_rating: bool = False):
    cards = await get_browse_cards(my_tg_id, sort_by_rating=sort_by_rating)
    if not cards:
        kb = InlineKeyboardBuilder()
        kb.button(text="Додати свою поїздку", callback_data="add_trip")
        await message.answer(
            "Поки що немає інших мандрівників з активними поїздками.\n\n"
            "Додайте свою поїздку — і як тільки хтось з'явиться, ви побачите їх тут!",
            reply_markup=kb.as_markup(),

        )
        return

    # Якщо сортуємо за рейтингом і ще ніхто не отримав відгуків
    if sort_by_rating:
        any_rated = any(c.get("_review_count", 0) > 0 for c in cards)
        if not any_rated:
            kb = InlineKeyboardBuilder()
            kb.button(text="🔍 Переглянути всіх", callback_data="browse_start")
            await message.answer(
                "⭐️ *Поки що немає відгуків*\n\n"
                "Жоден мандрівник ще не отримав рейтинг — спільнота тільки починає рости!\n\n"
                "Щойно з'являться перші обміни і відгуки — тут покажемо тих, "
                "у кого найвищий рейтинг 🏆\n\n"
                "А поки можете переглянути всіх мандрівників:",
                parse_mode="Markdown",
                reply_markup=kb.as_markup(),
            )
            return

    if idx >= len(cards):
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Почати спочатку", callback_data="browse_reset")
        await message.answer(
            "✅ Ви переглянули всіх нових мандрівників!\n"
            "Повертайтесь пізніше — база росте щодня 🌱\n\n"
            "Або почніть спочатку щоб ще раз побачити тих, кого скіпнули:",
            reply_markup=kb.as_markup(),
        )
        return
    await send_card(message, cards[idx], idx, len(cards))


@router.callback_query(F.data.startswith("bl_"))
async def browse_like(callback: CallbackQuery, bot):
    parts = callback.data.split("_")
    owner_tg = int(parts[2])
    idx = int(parts[3])
    my_tg_id = callback.from_user.id

    me = await get_user(my_tg_id)
    them = await get_user(owner_tg)

    await add_like(my_tg_id, owner_tg)
    await mark_viewed(my_tg_id, owner_tg)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Лайк!")

    their_likes = await get_liked_users(owner_tg)
    their_liked_ids = [u["telegram_id"] for u in their_likes]

    if my_tg_id in their_liked_ids:
        await _send_match(bot, callback.message, me, them, my_tg_id, owner_tg)
    else:
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="Подивитись профіль", callback_data="view_user_" + str(my_tg_id))
            me_name = me["name"] if me else "Хтось"
            me_city = me["home_city"] if me else ""
            me_country = me["home_country"] if me else ""
            await bot.send_message(
                owner_tg,
                "*" + me_name + "* лайкнув вас!\n\n"
                "Живе: " + me_city + ", " + me_country + "\n\n"
                "Якщо вам теж цікаво — подивіться профіль і лайкніть у відповідь",
                parse_mode="Markdown",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass

    cards = await get_browse_cards(my_tg_id)
    next_idx = idx + 1
    if next_idx < len(cards):
        await send_card(callback.message, cards[next_idx], next_idx, len(cards))
    else:
        await callback.message.answer("Ви переглянули всіх! Повертайтесь пізніше")


@router.callback_query(F.data.startswith("bs_"))
async def browse_skip(callback: CallbackQuery):
    idx = int(callback.data.split("_")[1])
    cards_before = await get_browse_cards(callback.from_user.id)
    if idx < len(cards_before):
        skipped_tg = cards_before[idx]["telegram_id"]
        await mark_viewed(callback.from_user.id, skipped_tg)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    cards = await get_browse_cards(callback.from_user.id)
    next_idx = idx + 1
    if next_idx < len(cards):
        await send_card(callback.message, cards[next_idx], next_idx, len(cards))
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Почати спочатку", callback_data="browse_reset")
        await callback.message.answer(
            "✅ Ви переглянули всіх нових мандрівників!\n"
            "Повертайтесь пізніше — база росте щодня 🌱",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("view_user_"))
async def view_specific_user(callback: CallbackQuery):
    target_tg_id = int(callback.data.split("_")[2])
    my_tg_id = callback.from_user.id

    cards = await get_browse_cards(my_tg_id, skip_viewed=False)
    target_card = None
    target_idx = 0
    for i, card in enumerate(cards):
        if card["telegram_id"] == target_tg_id:
            target_card = card
            target_idx = i
            break

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

    if target_card:
        await send_card(callback.message, target_card, target_idx, len(cards))
    else:
        user = await get_user(target_tg_id)
        if user:
            name = user["name"] or ""
            city = user["home_city"] or ""
            country = user["home_country"] or ""
            desc = user["home_description"] or "опис не вказано"
            await callback.message.answer(
                "*" + name + "*\n" +
                "Живе: " + city + ", " + country + "\n" +
                "Житло: " + desc + "\n\n" +
                "_Ця людина ще не додала активну поїздку_",
                parse_mode="Markdown",
            )
        else:
            await callback.message.answer("Профіль не знайдено")


async def _send_match(bot, message, me, them, my_tg_id, owner_tg):
    my_trips = await get_user_trips(my_tg_id)
    their_trips = await get_user_trips(owner_tg)
    if my_trips and their_trips:
        existing = await get_existing_match(my_trips[0]["id"], their_trips[0]["id"])
        if not existing:
            await create_match(my_trips[0]["id"], their_trips[0]["id"])

    them_name = them["name"] if them else "Мандрівник"
    them_city = them["home_city"] if them else ""
    them_country = them["home_country"] if them else ""
    me_name = me["name"] if me else "Мандрівник"
    me_city = me["home_city"] if me else ""
    me_country = me["home_country"] if me else ""

    safety = (
        "Взаємний лайк — це МАТЧ!\n\n"
        "Ваш партнер: *{name}* з {city}, {country}\n\n"
        "Перед тим як писати — рекомендуємо:\n\n"
        "1. Відеодзвінок — познайомтесь наживо\n"
        "2. Документи на житло — договір або право власності\n"
        "3. Особисті документи — паспорт або ID\n"
        "4. Домовляйтесь письмово\n\n"
        "Після перевірки — сміливо пишіть!"
    )

    kb1 = InlineKeyboardBuilder()
    try:
        chat = await bot.get_chat(owner_tg)
        if chat.username:
            kb1.button(text="Написати " + them_name, url="t.me/" + chat.username)
    except Exception:
        pass
    kb1.button(text="Зрозуміло!", callback_data="safety_ok")
    kb1.adjust(1)

    await message.answer(
        safety.format(name=them_name, city=them_city, country=them_country),
        parse_mode="Markdown",
        reply_markup=kb1.as_markup(),
    )

    kb2 = InlineKeyboardBuilder()
    try:
        chat2 = await bot.get_chat(my_tg_id)
        if chat2.username:
            kb2.button(text="Написати " + me_name, url="t.me/" + chat2.username)
    except Exception:
        pass
    kb2.button(text="Зрозуміло!", callback_data="safety_ok")
    kb2.adjust(1)

    try:
        await bot.send_message(
            owner_tg,
            safety.format(name=me_name, city=me_city, country=me_country),
            parse_mode="Markdown",
            reply_markup=kb2.as_markup(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("bq_"))
async def ask_question_start(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    target_tg = int(parts[1])
    idx = int(parts[2])

    them = await get_user(target_tg)
    name = them["name"] if them else "ця людина"

    await state.update_data(target_tg=target_tg, card_idx=idx)
    await callback.message.answer(
        "❓ *Напишіть ваше питання для " + name + "*\n\n"
        "_Питання надійде анонімно — ваш контакт не буде розкрито, "
        "доки ви самі не вирішите написати напряму._",
        parse_mode="Markdown",
    )
    await state.set_state(AskQuestion.waiting_question)
    await callback.answer()


@router.message(AskQuestion.waiting_question)
async def ask_question_send(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    target_tg = data.get("target_tg")
    await state.clear()

    me = await get_user(message.from_user.id)
    me_name = me["name"] if me else "Мандрівник"

    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Відповісти", callback_data="answer_" + str(message.from_user.id))
    kb.adjust(1)

    try:
        await bot.send_message(
            target_tg,
            "❓ *Анонімне питання від " + me_name + ":*\n\n" +
            "\"" + message.text.strip() + "\"\n\n" +
            "_Хочете відповісти? Натисніть кнопку нижче — це відкриє приватний чат._",
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
        )
        await message.answer("✅ Питання надіслано! Очікуйте відповідь 🙏")
    except Exception:
        await message.answer("😔 Не вдалось надіслати питання. Спробуйте пізніше.")


@router.callback_query(F.data.startswith("answer_"))
async def answer_question(callback: CallbackQuery, bot):
    asker_tg = int(callback.data.split("_")[1])
    me = await get_user(callback.from_user.id)
    me_name = me["name"] if me else "Хтось"

    safety_note = (
        "\n\n─────────────────\n"
        "🛡️ *Перед тим як писати — рекомендуємо:*\n"
        "1. Відеодзвінок перед обміном\n"
        "2. Документи на житло\n"
        "3. Особисті документи (паспорт/ID)\n"
        "4. Домовляйтесь письмово в чаті"
    )

    kb = InlineKeyboardBuilder()
    try:
        chat = await bot.get_chat(callback.from_user.id)
        if chat.username:
            kb.button(text="✉️ Відкрити чат з " + me_name, url="t.me/" + chat.username)
    except Exception:
        pass

    try:
        await bot.send_message(
            asker_tg,
            me_name + " готовий(-а) відповісти на ваше питання! 👇" + safety_note,
            parse_mode="Markdown",
            reply_markup=kb.as_markup() if kb.export() else None,
        )
        await callback.answer("Повідомлено! Партнер може написати вам напряму.")
    except Exception:
        await callback.answer("Не вдалось надіслати", show_alert=True)


@router.callback_query(F.data == "safety_ok")
async def safety_ok(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Удачі з обміном!")
