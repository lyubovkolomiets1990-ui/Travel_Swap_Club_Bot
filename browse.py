from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import difflib

from db import (get_user, get_active_trips, get_user_trips,
                add_like, get_liked_users, remove_like,
                create_match, get_existing_match,
                mark_viewed, get_viewed_ids, get_user_rating,
                get_reviews_for_user)

router = Router()


def fuzzy_city_match(query: str, candidate: str) -> bool:
    """Збіг або точний підрядок, або схожість 72%+ (різні варіанти написання)"""
    query = query.strip().lower()
    candidate = candidate.strip().lower()
    if not query or not candidate:
        return False
    if query in candidate:
        return True
    ratio = difflib.SequenceMatcher(None, query, candidate).ratio()
    return ratio >= 0.72


class AskQuestion(StatesGroup):
    waiting_question = State()


class FindHomeCity(StatesGroup):
    waiting_city_name = State()



async def get_browse_cards(my_telegram_id: int, skip_viewed: bool = True,
                           sort_by_rating: bool = False, filter_city: str = None,
                           filter_home_city: str = None) -> list:
    """Показуємо тільки повні профілі — є місто, опис і фото.
    skip_viewed=True приховує тих, кого вже лайкнули/скіпнули раніше.
    sort_by_rating=True сортує від найвищого рейтингу до найнижчого.
    filter_city — показує тільки тих, хто ЇДЕ саме в це місто.
    filter_home_city — показує тільки тих, хто ЖИВЕ саме в цьому місті."""
    all_trips = await get_active_trips()
    viewed_ids = await get_viewed_ids(my_telegram_id) if skip_viewed else set()
    seen_users = set()
    cards = []
    city_query = filter_city.strip().lower() if filter_city else None
    home_city_query = filter_home_city.strip().lower() if filter_home_city else None
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
        is_verified = ("verification_status" not in trip_keys) or trip["verification_status"] == "verified"
        if not (has_city and has_desc and has_photo and is_verified):
            continue
        if city_query:
            dest_city = (trip["destination_city"] or "").strip().lower()
            if not fuzzy_city_match(city_query, dest_city):
                continue
        if home_city_query:
            home_city = (trip["home_city"] or "").strip().lower()
            if not fuzzy_city_match(home_city_query, home_city):
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
    from matcher import TRAVELER_TYPES, LOOKING_FOR_LABELS, format_looking_for_labels
    tt = TRAVELER_TYPES.get(trip.get("traveler_type", "anyone"), "будь-хто")
    lf = format_looking_for_labels(trip.get("looking_for", "anyone"))
    pets = ""
    if trip.get("has_pets"):
        info = trip.get("pets_info") or "є"
        pets = "🐾 Тварини: " + info + "\n"
    extra = ""
    extra_info = trip.get("extra_info")
    if extra_info and extra_info not in ("", "None"):
        extra = "ℹ️ Інше: " + extra_info + "\n"
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
        "🏠 Живе: " + home_city + ", " + home_country + "\n"
        "✈️ Їде до: *" + dest_city + ", " + dest_country + "*\n"
        "📅 Дати: " + (date_from + (" - " + date_to if date_to else "")) + "\n"
        + pets + extra +
        "📝 Житло: " + desc
    )


def browse_kb(trip: dict, idx: int, total: int):
    kb = InlineKeyboardBuilder()
    tid = trip["id"]
    tg = trip["telegram_id"]
    uid = trip.get("user_id") or 0
    kb.button(text="❤️ Лайк", callback_data="bl_" + str(tid) + "_" + str(tg) + "_" + str(idx))
    kb.button(text="❓ Запитати", callback_data="bq_" + str(tg) + "_" + str(idx))
    kb.button(text="📝 Відгуки", callback_data="brev_" + str(uid) + "_" + str(idx))
    kb.button(text="👎 Далі", callback_data="bs_" + str(idx))
    kb.adjust(2, 1, 1)
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


@router.message(Command("find_to_me"))
async def cmd_find_to_me(message: Message):
    me = await get_user(message.from_user.id)
    if not me or not me["home_city"]:
        await message.answer(
            "😔 Спочатку вкажіть своє місто проживання в профілі — "
            "через «🏠 Змінити профіль»."
        )
        return
    my_city = me["home_city"]
    await message.answer(
        "🔍 Шукаю, хто хоче приїхати у *" + my_city + "*...",
        parse_mode="Markdown",
    )
    await show_browse(message, message.from_user.id, 0, filter_city=my_city)


@router.callback_query(F.data == "browse_find_to_me")
async def browse_find_to_me(callback: CallbackQuery):
    me = await get_user(callback.from_user.id)
    await callback.answer()
    if not me or not me["home_city"]:
        await callback.message.answer(
            "😔 Спочатку вкажіть своє місто проживання в профілі — "
            "через «🏠 Змінити профіль»."
        )
        return
    my_city = me["home_city"]
    await callback.message.answer(
        "🔍 Шукаю, хто хоче приїхати у *" + my_city + "*...",
        parse_mode="Markdown",
    )
    await show_browse(callback.message, callback.from_user.id, 0, filter_city=my_city)


@router.message(Command("find_home"))
async def cmd_find_home(message: Message, state: FSMContext):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        city = parts[1].strip()
        await message.answer("🔍 Шукаю, хто живе в «" + city + "»...")
        await show_browse(message, message.from_user.id, 0, filter_home_city=city)
        return
    await message.answer(
        "🏠 *В яке місто ви хочете поїхати?*\n\n"
        "_Напишіть назву міста — покажу тих, хто там живе: наприклад, Пафос_",
        parse_mode="Markdown",
    )
    await state.set_state(FindHomeCity.waiting_city_name)


@router.message(FindHomeCity.waiting_city_name)
async def find_home_city_input(message: Message, state: FSMContext):
    city = message.text.strip()
    await state.clear()
    await message.answer("🔍 Шукаю, хто живе в «" + city + "»...")
    await show_browse(message, message.from_user.id, 0, filter_home_city=city)


@router.callback_query(F.data == "browse_find_home")
async def browse_find_home(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🏠 *В яке місто ви хочете поїхати?*\n\n"
        "_Напишіть назву міста — покажу тих, хто там живе: наприклад, Пафос_",
        parse_mode="Markdown",
    )
    await state.set_state(FindHomeCity.waiting_city_name)
    await callback.answer()


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


async def show_browse(message: Message, my_tg_id: int, idx: int, sort_by_rating: bool = False,
                       filter_city: str = None, filter_home_city: str = None):
    cards = await get_browse_cards(my_tg_id, sort_by_rating=sort_by_rating,
                                    filter_city=filter_city, filter_home_city=filter_home_city)
    if not cards:
        kb = InlineKeyboardBuilder()
        if filter_home_city:
            kb.button(text="🔍 Переглянути всіх", callback_data="browse_start")
            await message.answer(
                "😔 Поки що ніхто не живе в «" + filter_home_city + "».\n\n"
                "Спробуйте інше місто або перегляньте всіх мандрівників:",
                reply_markup=kb.as_markup(),
            )
        elif filter_city:
            kb.button(text="🔍 Переглянути всіх", callback_data="browse_start")
            await message.answer(
                "😔 Поки що ніхто не їде в «" + filter_city + "».\n\n"
                "Спробуйте інше місто або перегляньте всіх мандрівників:",
                reply_markup=kb.as_markup(),
            )
        else:
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

    # Перевіряємо чи в людини є власна поїздка — без неї матч буде неповноцінним
    my_trips_check = await get_user_trips(my_tg_id)
    if not my_trips_check:
        kb_redirect = InlineKeyboardBuilder()
        kb_redirect.button(text="✈️ Додати поїздку", callback_data="add_trip")
        kb_redirect.button(text="🔍 Переглянути далі", callback_data="bcont_" + str(idx))
        kb_redirect.adjust(1)
        await callback.answer(
            "Щоб лайкати — додайте спочатку свою поїздку 👇",
            show_alert=True,
        )
        await callback.message.answer(
            "✈️ *Перш ніж лайкати — додайте свою поїздку!*\n\n"
            "Без поїздки матч не буде повноцінним: ви не зможете "
            "залишити відгук після обміну.\n\n"
            "Це займає 1 хвилину — куди їдете і коли 👇",
            parse_mode="Markdown",
            reply_markup=kb_redirect.as_markup(),
        )
        return

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
        await callback.message.answer(
            "❤️ Лайк зараховано! Якщо буде взаємний інтерес — повідомимо вас 🔔"
        )
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
        kb_end = InlineKeyboardBuilder()
        kb_end.button(text="🔄 Почати спочатку", callback_data="browse_reset")
        await callback.message.answer(
            "✅ Ви переглянули всіх нових мандрівників!\n"
            "Повертайтесь пізніше — база росте щодня 🌱",
            reply_markup=kb_end.as_markup(),
        )


@router.callback_query(F.data.startswith("bcont_"))
async def browse_continue(callback: CallbackQuery):
    idx = int(callback.data.split("_")[1])
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


@router.callback_query(F.data.startswith("brev_"))
async def browse_show_reviews(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_db_id = int(parts[1])
    await callback.answer()

    reviews = await get_reviews_for_user(user_db_id)
    if not reviews:
        await callback.message.answer("📝 У цієї людини ще немає відгуків.")
        return

    lines = [f"📝 *Відгуки* ({len(reviews)}):\n"]
    for rev in reviews[:10]:
        stars = "⭐️" * round(rev["overall"])
        line = f"{stars} *{rev['reviewer_name']}*"
        if rev["comment"]:
            line += f"\n_{rev['comment']}_"
        lines.append(line)

    await callback.message.answer("\n\n".join(lines), parse_mode="Markdown")


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
            extra = user["extra_info"] if "extra_info" in user.keys() else ""
            extra_line = ("ℹ️ Інше: " + extra + "\n") if extra else ""
            await callback.message.answer(
                "*" + name + "*\n" +
                "🏠 Живе: " + city + ", " + country + "\n" +
                "📝 Житло: " + desc + "\n" +
                extra_line + "\n" +
                "_Ця людина ще не додала активну поїздку_",
                parse_mode="Markdown",
            )
        else:
            await callback.message.answer("Профіль не знайдено")


async def _send_match(bot, message, me, them, my_tg_id, owner_tg):
    my_trips = await get_user_trips(my_tg_id)
    their_trips = await get_user_trips(owner_tg)
    match_id = None
    if my_trips and their_trips:
        existing = await get_existing_match(my_trips[0]["id"], their_trips[0]["id"])
        if existing:
            match_id = existing["id"] if hasattr(existing, "keys") else existing
        else:
            match_id = await create_match(my_trips[0]["id"], their_trips[0]["id"])

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
        "Після перевірки — сміливо пишіть!\n\n"
        "👉 *Після обміну будь ласка залиште відгук — це дуже важливо* 👈\n"
        "Відгуки допомагають усій спільноті обирати надійних партнерів."
    )

    kb1 = InlineKeyboardBuilder()
    try:
        chat = await bot.get_chat(owner_tg)
        if chat.username:
            kb1.button(text="Написати " + them_name, url="t.me/" + chat.username)
    except Exception:
        pass
    if match_id:
        kb1.button(text="⭐️ Залишити відгук", callback_data="start_review_" + str(match_id))
        kb1.button(text="❌ Не домовились — шукати далі", callback_data="cancel_match_" + str(match_id))
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
    if match_id:
        kb2.button(text="⭐️ Залишити відгук", callback_data="start_review_" + str(match_id))
        kb2.button(text="❌ Не домовились — шукати далі", callback_data="cancel_match_" + str(match_id))
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

    # Прибираємо кнопку одразу, щоб не можна було натиснути кілька разів
    await callback.message.edit_reply_markup(reply_markup=None)

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


@router.callback_query(F.data.startswith("cancel_match_"))
async def cancel_match(callback: CallbackQuery):
    import db as _db
    match_id = int(callback.data.split("_")[2])
    await _db.update_match_status(match_id, "cancelled")
    await callback.message.edit_reply_markup(reply_markup=None)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Переглянути інших", callback_data="browse_start")
    await callback.message.answer(
        "Зрозуміло — іноді обмін не складається, і це нормально.\n\n"
        "Можете продовжити пошук іншого партнера 👇",
        reply_markup=kb.as_markup(),
    )
    await callback.answer("Матч закрито")


@router.callback_query(F.data == "safety_ok")
async def safety_ok(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Удачі з обміном!")
