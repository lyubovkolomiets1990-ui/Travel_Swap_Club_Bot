from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import re

from db import get_user, create_trip, get_user_trips
from matcher import find_matches, save_match, TRAVELER_TYPES, LOOKING_FOR_LABELS

router = Router()
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


class AddTrip(StatesGroup):
    waiting_dest_city    = State()
    waiting_dest_country = State()
    waiting_dates_choice = State()   # є дати чи ще планую
    waiting_date_from    = State()
    waiting_date_to      = State()
    waiting_guests       = State()
    waiting_my_type      = State()   # хто я (тип мандрівника)
    waiting_looking_for  = State()   # кого шукаю у своє житло


# ── Клавіатури ───────────────────────────────────────────────────────────────

def traveler_type_kb() -> object:
    kb = InlineKeyboardBuilder()
    for key, label in TRAVELER_TYPES.items():
        kb.button(text=label, callback_data=f"mytype_{key}")
    kb.adjust(2)
    return kb.as_markup()


def looking_for_kb() -> object:
    kb = InlineKeyboardBuilder()
    for key, label in LOOKING_FOR_LABELS.items():
        kb.button(text=label, callback_data=f"lookfor_{key}")
    kb.adjust(2)
    return kb.as_markup()


def format_trip(trip) -> str:
    lf = LOOKING_FOR_LABELS.get(trip.get("looking_for", "anyone"), "🌍 Будь-кого")
    tt = TRAVELER_TYPES.get(trip.get("traveler_type", "anyone"), "🌍 Будь-хто")
    return (
        f"✈️ {trip['destination_city']}, {trip['destination_country']}\n"
        f"📅 {trip['date_from']} — {trip['date_to']}\n"
        f"👥 Гостей: {trip['guests_count']} · Я: {tt}\n"
        f"🔍 Шукаю: {lf}"
    )


# ── Старт ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "add_trip")
async def add_trip_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if not user or not user["home_city"]:
        await callback.message.answer("⚠️ Спочатку налаштуйте профіль через /start")
        await callback.answer()
        return

    await callback.message.answer(
        "✈️ *Куди ви їдете?*\n\nВведіть місто призначення:",
        parse_mode="Markdown",
    )
    await state.set_state(AddTrip.waiting_dest_city)
    await callback.answer()


# ── Кроки FSM ────────────────────────────────────────────────────────────────

@router.message(AddTrip.waiting_dest_city)
async def step_dest_city(message: Message, state: FSMContext):
    await state.update_data(dest_city=message.text.strip())
    await message.answer("🌍 *В якій країні?*", parse_mode="Markdown")
    await state.set_state(AddTrip.waiting_dest_country)


@router.message(AddTrip.waiting_dest_country)
async def step_dest_country(message: Message, state: FSMContext):
    await state.update_data(dest_country=message.text.strip())
    await message.answer(
        "📅 *Дата виїзду?*\nФормат: ДД.ММ.РРРР  (_наприклад: 10.08.2025_)",
        parse_mode="Markdown",
    )
    await state.set_state(AddTrip.waiting_date_from)


@router.message(AddTrip.waiting_date_from)
async def step_date_from(message: Message, state: FSMContext):
    if not DATE_RE.match(message.text.strip()):
        await message.answer("❌ Невірний формат. Введіть як ДД.ММ.РРРР")
        return
    await state.update_data(date_from=message.text.strip())
    await message.answer("📅 *Дата повернення?*\nФормат: ДД.ММ.РРРР", parse_mode="Markdown")
    await state.set_state(AddTrip.waiting_date_to)


@router.message(AddTrip.waiting_date_to)
async def step_date_to(message: Message, state: FSMContext):
    if not DATE_RE.match(message.text.strip()):
        await message.answer("❌ Невірний формат. Введіть як ДД.ММ.РРРР")
        return
    await state.update_data(date_to=message.text.strip())
    await message.answer(
        "👥 *Скільки гостей ви можете прийняти?*\nВведіть число (1–10):",
        parse_mode="Markdown",
    )
    await state.set_state(AddTrip.waiting_guests)


@router.message(AddTrip.waiting_guests)
async def step_guests(message: Message, state: FSMContext):
    try:
        guests = int(message.text.strip())
        if not 1 <= guests <= 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введіть число від 1 до 10")
        return

    await state.update_data(guests=guests)
    await message.answer(
        "🧳 *Хто ви як мандрівник?*\n\nОберіть свій тип — так інші зрозуміють, хто до них їде:",
        parse_mode="Markdown",
        reply_markup=traveler_type_kb(),
    )
    await state.set_state(AddTrip.waiting_my_type)


@router.callback_query(AddTrip.waiting_my_type, F.data.startswith("mytype_"))
async def step_my_type(callback: CallbackQuery, state: FSMContext):
    traveler_type = callback.data.split("_", 1)[1]
    await state.update_data(traveler_type=traveler_type)
    await callback.message.edit_reply_markup(reply_markup=None)

    label = TRAVELER_TYPES.get(traveler_type, "")
    await callback.message.answer(
        f"Ви: *{label}* ✅\n\n"
        "🔍 *Кого шукаєте для обміну?*\n\nХто може жити у вашому домі поки ви подорожуєте?",
        parse_mode="Markdown",
        reply_markup=looking_for_kb(),
    )
    await state.set_state(AddTrip.waiting_looking_for)
    await callback.answer()


@router.callback_query(AddTrip.waiting_looking_for, F.data.startswith("lookfor_"))
async def step_looking_for(callback: CallbackQuery, state: FSMContext, bot):
    looking_for = callback.data.split("_", 1)[1]
    await state.update_data(looking_for=looking_for)
    await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    user = await get_user(callback.from_user.id)
    await state.clear()

    lf_label = LOOKING_FOR_LABELS.get(looking_for, "")
    tt_label = TRAVELER_TYPES.get(data["traveler_type"], "")

    # Зберігаємо поїздку
    trip_id = await create_trip(
        user["id"],
        data["dest_city"],
        data["dest_country"],
        data["date_from"],
        data["date_to"],
        data["guests"],
        looking_for=looking_for,
        traveler_type=data["traveler_type"],
    )

    await callback.message.answer(
        f"✅ *Поїздку додано!*\n\n"
        f"✈️ {data['dest_city']}, {data['dest_country']}\n"
        f"📅 {data['date_from']} — {data['date_to']}\n"
        f"👥 Гостей: {data['guests']}\n"
        f"🧳 Ви: {tt_label}\n"
        f"🔍 Шукаєте: {lf_label}\n\n"
        "🔎 Шукаю матчі...",
        parse_mode="Markdown",
    )

    # Шукаємо матчі
    new_trip = {
        "id":                  trip_id,
        "destination_city":    data["dest_city"],
        "destination_country": data["dest_country"],
        "date_from":           data["date_from"],
        "date_to":             data["date_to"],
        "home_city":           user["home_city"],
        "home_country":        user["home_country"],
        "looking_for":         looking_for,
        "traveler_type":       data["traveler_type"],
    }

    found = await find_matches(new_trip)

    if not found:
        await callback.message.answer(
            "😔 Поки що матчів за вашими фільтрами не знайдено.\n"
            "Ми повідомимо вас, щойно хтось підходящий з'явиться! 🔔"
        )
        await callback.answer()
        return

    for match_trip in found:
        match_id = await save_match(trip_id, match_trip["id"])
        tt = TRAVELER_TYPES.get(match_trip.get("traveler_type", "anyone"), "")
        lf = LOOKING_FOR_LABELS.get(match_trip.get("looking_for", "anyone"), "")

        # Для поточного користувача
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Прийняти",          callback_data=f"accept_{match_id}_1")
        kb.button(text=f"❤️ Зберегти",         callback_data=f"like_{match_trip['telegram_id']}")
        kb.button(text="❌ Відхилити",          callback_data=f"decline_{match_id}")
        kb.adjust(2)

        await callback.message.answer(
            f"🎉 *Знайдено матч!*\n\n"
            f"👤 *{match_trip['name']}* з {match_trip['home_city']}, {match_trip['home_country']}\n"
            f"✈️ Їде до: {match_trip['destination_city']}, {match_trip['destination_country']}\n"
            f"📅 {match_trip['date_from']} — {match_trip['date_to']}\n"
            f"🧳 Тип: {tt}  ·  🔍 Шукає: {lf}\n"
            f"🏠 Житло: {match_trip['home_description'] or 'опис не вказано'}\n\n"
            "Хочете обмінятись?",
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
        )

        # Для іншого користувача
        kb2 = InlineKeyboardBuilder()
        kb2.button(text="✅ Прийняти",  callback_data=f"accept_{match_id}_2")
        kb2.button(text="❤️ Зберегти", callback_data=f"like_{callback.from_user.id}")
        kb2.button(text="❌ Відхилити", callback_data=f"decline_{match_id}")
        kb2.adjust(2)

        my_tt = TRAVELER_TYPES.get(data["traveler_type"], "")
        my_lf = LOOKING_FOR_LABELS.get(looking_for, "")

        try:
            await bot.send_message(
                match_trip["telegram_id"],
                f"🎉 *Новий матч за вашими фільтрами!*\n\n"
                f"👤 *{user['name']}* з {user['home_city']}, {user['home_country']}\n"
                f"✈️ Їде до: {data['dest_city']}, {data['dest_country']}\n"
                f"📅 {data['date_from']} — {data['date_to']}\n"
                f"🧳 Тип: {my_tt}  ·  🔍 Шукає: {my_lf}\n"
                f"🏠 Житло: {user['home_description'] or 'опис не вказано'}\n\n"
                "Хочете обмінятись?",
                parse_mode="Markdown",
                reply_markup=kb2.as_markup(),
            )
        except Exception:
            pass

    await callback.answer()


# ── Мої поїздки ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_trips")
async def my_trips(callback: CallbackQuery):
    trips = await get_user_trips(callback.from_user.id)
    if not trips:
        kb = InlineKeyboardBuilder()
        kb.button(text="✈️ Додати поїздку", callback_data="add_trip")
        await callback.message.answer(
            "У вас ще немає активних поїздок.",
            reply_markup=kb.as_markup(),
        )
        await callback.answer()
        return

    text = "📋 *Ваші активні поїздки:*\n\n"
    for i, trip in enumerate(trips, 1):
        text += f"{i}. {format_trip(trip)}\n\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати ще поїздку", callback_data="add_trip")
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb.as_markup())
    await callback.answer()
