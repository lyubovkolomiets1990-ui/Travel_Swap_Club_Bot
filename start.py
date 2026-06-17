from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import get_user, create_user, update_user_home

router = Router()


class OnboardingFSM(StatesGroup):
    waiting_agreement = State()


class RegisterHome(StatesGroup):
    waiting_city_country = State()
    waiting_description  = State()
    waiting_photos       = State()
    waiting_pets         = State()
    waiting_pets_info    = State()


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати поїздку",   callback_data="add_trip")
    kb.button(text="📋 Мої поїздки",      callback_data="my_trips")
    kb.button(text="🔍 Переглянути всіх", callback_data="browse_start")
    kb.button(text="⭐️ Топ за рейтингом",  callback_data="browse_top")
    kb.button(text="📅 Мій календар",     callback_data="my_calendar")
    kb.button(text="❤️ Збережені",        callback_data="my_saved")
    kb.button(text="📊 Мій рейтинг",      callback_data="my_rating")
    kb.button(text="🏠 Змінити профіль",  callback_data="edit_profile")
    kb.adjust(2)
    return kb.as_markup()


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)

    if user and user["home_city"]:
        pets_line = f"🐾 Тварини: {user['pets_info'] or 'є'}\n" if user["has_pets"] else ""
        await message.answer(
            f"👋 З поверненням, *{user['name']}*!\n\n"
            f"🏠 {user['home_city']}, {user['home_country']}\n"
            f"{pets_line}\n"
            "Що бажаєте зробити?",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
    else:
        if not user:
            await create_user(message.from_user.id, message.from_user.first_name)

        kb = InlineKeyboardBuilder()
        kb.button(text="🚀 Поїхали!", callback_data="agree_and_start")
        kb.adjust(1)

        await message.answer(
            "🏡 *Перш ніж почати*\n\n"
            "Travel Swap Club — це спільнота людей які довіряють одне одному свої домівки.\n\n"
            "Ми допомагаємо знайти партнера для обміну, але фінальне рішення завжди за вами.\n\n"
            "Кілька простих правил:\n"
            "• Будьте чесні в описі свого житла\n"
            "• Перевіряйте партнера перед обміном\n"
            "• Домовляйтесь письмово в чаті\n"
            "• Поважайте чужий дім як свій\n\n"
            "Платформа не є стороною угоди між учасниками — ви домовляєтесь напряму.\n\n"
            "Готові? Тоді вперед — вас чекає світ відкритих дверей! 🌍",
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
        )
        await state.set_state(OnboardingFSM.waiting_agreement)


# ── Погодження ────────────────────────────────────────────────────────────────

@router.callback_query(OnboardingFSM.waiting_agreement, F.data == "agree_and_start")
async def agree_and_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("🎉 Чудово! Починаємо!")
    await callback.message.answer(
        "🏡 *Ласкаво просимо до Travel Swap Club!*\n\n"
        "Це платформа для обміну житлом між мандрівниками 🌍\n\n"
        "Наприклад: ви їдете до Барселони — хтось із Барселони приїде до вас.\n\n"
        "Давайте почнемо 👇\n\n"
        "📍 *Де ви зараз живете?*\n"
        "_Введіть місто і країну через кому: Айя-Напа, Кіпр_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_city_country)


# ── Крок 1: Місто і країна ────────────────────────────────────────────────────

@router.message(RegisterHome.waiting_city_country)
async def home_city_country(message: Message, state: FSMContext):
    text = message.text.strip()
    if "," in text:
        city, country = [x.strip() for x in text.split(",", 1)]
    else:
        city = text
        country = text
    await state.update_data(city=city, country=country)
    await message.answer(
        "📝 *Опишіть своє житло:*\n"
        "Скільки кімнат, що поруч, особливості?\n\n"
        "_Наприклад: будинок, 5 хв до моря, машина включена, паркінг_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_description)


# ── Крок 2: Опис ──────────────────────────────────────────────────────────────

@router.message(RegisterHome.waiting_description)
async def home_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer(
        "📸 *Надішліть фото вашого житла*\n\n"
        "Можна до 5 фото — гості побачать де житимуть.\n\n"
        "_Коли надішлете всі фото — натисніть «Готово»_",
        parse_mode="Markdown",
        reply_markup=_skip_kb("photos_done"),
    )
    await state.update_data(photos=[])
    await state.set_state(RegisterHome.waiting_photos)


# ── Крок 3: Фото ──────────────────────────────────────────────────────────────

@router.message(RegisterHome.waiting_photos, F.photo)
async def home_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    count = len(photos)
    if count >= 5:
        await message.answer("✅ 5 фото збережено!")
        await _ask_pets(message, state)
    else:
        await message.answer(
            f"✅ Фото {count}/5 збережено. Надішліть ще або натисніть «Готово»",
            reply_markup=_skip_kb("photos_done"),
        )


@router.callback_query(RegisterHome.waiting_photos, F.data == "photos_done")
async def photos_done(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _ask_pets(callback.message, state)


async def _ask_pets(message: Message, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, є тварини", callback_data="pets_yes")
    kb.button(text="❌ Ні",             callback_data="pets_no")
    kb.adjust(2)
    await message.answer(
        "🐾 *У вас є домашні тварини?*\n\n"
        "_Це важливо знати гостям заздалегідь_",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )
    await state.set_state(RegisterHome.waiting_pets)


# ── Крок 4: Тварини ───────────────────────────────────────────────────────────

@router.callback_query(RegisterHome.waiting_pets, F.data == "pets_yes")
async def pets_yes(callback: CallbackQuery, state: FSMContext):
    await state.update_data(has_pets=1)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🐶 *Розкажіть про тварин:*\n\n"
        "_Наприклад: 1 кіт, дуже лагідний_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_pets_info)
    await callback.answer()


@router.callback_query(RegisterHome.waiting_pets, F.data == "pets_no")
async def pets_no(callback: CallbackQuery, state: FSMContext):
    await state.update_data(has_pets=0, pets_info="")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _save_profile(callback.message, state)


@router.message(RegisterHome.waiting_pets_info)
async def pets_info(message: Message, state: FSMContext):
    await state.update_data(pets_info=message.text.strip())
    await _save_profile(message, state)


# ── Збереження профілю ────────────────────────────────────────────────────────

async def _save_profile(message: Message, state: FSMContext):
    data = await state.get_data()
    photos_str = ",".join(data.get("photos", []))
    has_pets  = data.get("has_pets", 0)
    pets_info = data.get("pets_info", "")

    await update_user_home(
        message.chat.id,
        data["city"], data["country"], data["description"],
        photos=photos_str, has_pets=has_pets, pets_info=pets_info,
    )
    await state.clear()

    photos_count = len([p for p in photos_str.split(",") if p])
    pets_line = f"🐾 Тварини: {pets_info}\n" if has_pets else ""

    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати першу поїздку", callback_data="add_trip")

    await message.answer(
        f"✅ *Профіль збережено!*\n\n"
        f"🏠 {data['city']}, {data['country']}\n"
        f"📝 {data['description']}\n"
        f"📸 Фото: {photos_count} шт.\n"
        f"{pets_line}\n"
        "Тепер додайте поїздку, щоб почати шукати матчі!",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )


# ── Допоміжні ─────────────────────────────────────────────────────────────────

def _skip_kb(callback_data: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data=callback_data)
    return kb.as_markup()


# ── Команди ───────────────────────────────────────────────────────────────────

@router.message(Command("trip"))
async def cmd_trip(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати поїздку", callback_data="add_trip")
    await message.answer("Натисніть щоб додати нову поїздку:", reply_markup=kb.as_markup())


@router.message(Command("saved"))
async def cmd_saved(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="❤️ Переглянути збережених", callback_data="my_saved")
    await message.answer("Ваші збережені хости:", reply_markup=kb.as_markup())


@router.message(Command("rating"))
async def cmd_rating(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Переглянути рейтинг", callback_data="my_rating")
    await message.answer("Ваш рейтинг хоста:", reply_markup=kb.as_markup())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 *Як користуватись ботом:*\n\n"
        "1️⃣ /start — налаштувати профіль і додати фото житла\n"
        "2️⃣ /browse — переглянути мандрівників і лайкати\n"
        "3️⃣ Взаємний лайк = матч 🎊\n"
        "4️⃣ /trip — додати свою поїздку\n"
        "5️⃣ /calendar — вказати коли житло доступне\n"
        "6️⃣ Після обміну залиште відгук ⭐️\n\n"
        "❓ Питання? Пишіть @your\\_support",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📍 *Де ви живете?*\nВведіть місто і країну через кому:\n_Наприклад: Айя-Напа, Кіпр_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_city_country)
    await callback.answer()
