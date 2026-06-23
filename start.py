from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import get_user, create_user, update_user_home, delete_user_profile, get_all_known_cities
import difflib

router = Router()


class OnboardingFSM(StatesGroup):
    waiting_agreement = State()


class RegisterHome(StatesGroup):
    waiting_country       = State()
    waiting_city          = State()
    waiting_city_confirm  = State()
    waiting_description   = State()
    waiting_photos        = State()
    waiting_pets          = State()
    waiting_pets_info     = State()


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати поїздку",   callback_data="add_trip")
    kb.button(text="📋 Мої поїздки",      callback_data="my_trips")
    kb.button(text="🔍 Переглянути всіх", callback_data="browse_start")
    kb.button(text="⭐️ Топ за рейтингом",  callback_data="browse_top")
    kb.button(text="🔎 Знайти місто",       callback_data="browse_find")
    kb.button(text="🏠 Хто живе в...",       callback_data="browse_find_home")
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
            "🏡 *Travel Swap Club* — спільнота українців, які обмінюються "
            "житлом під час подорожей по всьому світу 🌍\n\n"
            "Коротко про можливості бота:\n\n"
            "🔍 *Переглянути всіх* — дивіться картки мандрівників і лайкайте тих, "
            "хто цікавий\n"
            "🔎 *Знайти місто* — шукайте конкретно тих, хто їде у потрібне вам місто\n"
            "⭐️ *Топ за рейтингом* — спочатку показує перевірених хостів із "
            "найвищими відгуками\n"
            "📅 *Календар* — позначайте місяці, коли ваше житло недоступне\n"
            "❤️ *Збережені* — список тих, кого ви лайкнули\n"
            "📊 *Мій рейтинг* — ваша репутація після завершених обмінів\n\n"
            "Якщо щось працює не так, як очікували, або знайшли помилку — "
            "напишіть нам, будь ласка, на @your\\_support 🙏 "
            "Ми зробимо все можливе щоб виправити якнайшвидше.",
            parse_mode="Markdown",
        )

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

        kb_welcome = InlineKeyboardBuilder()
        kb_welcome.button(text="🚀 Створити профіль", callback_data="start_onboarding")
        kb_welcome.adjust(1)

        await message.answer(
            "🏡 *Ласкаво просимо до Travel Swap Club!*\n\n"
            "Спільноти українців по всьому світу, які подорожують, знайомляться "
            "та обмінюються житлом без зайвих витрат на готелі 🌍💙💛\n\n"
            "Уявіть: поки ви відпочиваєте в іншій країні, хтось із нашої спільноти "
            "живе у вашій квартирі, а ви — у його. Безпечніше, дешевше та "
            "набагато цікавіше, ніж звичайна оренда.\n\n"
            "Що ви можете робити в боті:\n\n"
            "🔍 *Переглянути всіх* — знаходьте цікавих мандрівників та потенційні обміни\n"
            "🏙 *Знайти місто* — шукайте людей, які подорожують у потрібне вам місто\n"
            "🏠 *Хто живе в...* — шукайте, хто живе саме там, куди ви хочете поїхати\n"
            "⭐️ *Топ за рейтингом* — відкривайте профілі учасників з найкращими "
            "відгуками та високим рівнем довіри\n"
            "📅 *Календар подорожей* — позначайте дати, коли ваше житло доступне "
            "для обміну\n"
            "❤️ *Збережені* — усі користувачі, які вам сподобалися\n"
            "🤝 *Мої матчі* — взаємні вподобання та нові знайомства\n"
            "📊 *Мій рейтинг* — будуйте власну репутацію через успішні обміни "
            "та відгуки\n"
            "🛡 *Рекомендації та відгуки* — довіряйте перевіреним учасникам спільноти\n\n"
            "Travel Swap Club — це не просто обмін квартирами. Це спільнота людей, "
            "які відкривають світ, допомагають одне одному та подорожують як місцеві.\n\n"
            "Якщо у вас виникли питання або ви знайшли помилку — напишіть нам "
            "на @your\\_support 🙏\n\n"
            "Бажаємо вам приємних подорожей та вдалих матчів! ✈️🏡",
            parse_mode="Markdown",
            reply_markup=kb_welcome.as_markup(),
        )


# ── Кнопка "Створити профіль" → екран правил ──────────────────────────────────

@router.callback_query(F.data == "start_onboarding")
async def start_onboarding(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Поїхали!", callback_data="agree_and_start")
    kb.adjust(1)

    await callback.message.answer(
        "Перш ніж почати — кілька простих правил:\n\n"
        "• Будьте чесні в описі свого житла\n"
        "• Перевіряйте партнера перед обміном\n"
        "• Домовляйтесь письмово в чаті\n"
        "• Поважайте чужий дім як свій\n\n"
        "Платформа не є стороною угоди між учасниками — ви домовляєтесь напряму.\n\n"
        "Готові? Тоді вперед — вас чекає світ відкритих дверей! 🌍",
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
        "🌍 *В якій країні ви живете?*\n"
        "_Наприклад: Кіпр_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_country)


# ── Крок 1: Країна ────────────────────────────────────────────────────────────

@router.message(RegisterHome.waiting_country)
async def home_country(message: Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer(
        "🏙 *А в якому місті?*\n"
        "_Наприклад: Пафос_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_city)


# ── Крок 2: Місто ──────────────────────────────────────────────────────────────

@router.message(RegisterHome.waiting_city)
async def home_city(message: Message, state: FSMContext):
    typed_city = message.text.strip()

    known_cities = await get_all_known_cities()
    matches = difflib.get_close_matches(typed_city, known_cities, n=1, cutoff=0.72)

    if matches and matches[0].lower() != typed_city.lower():
        suggested = matches[0]
        await state.update_data(typed_city=typed_city, suggested_city=suggested)
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Так, це " + suggested, callback_data="city_use_suggested")
        kb.button(text="Ні, залишити «" + typed_city + "»", callback_data="city_keep_typed")
        kb.adjust(1)
        await message.answer(
            "🏙 Ви ввели: *" + typed_city + "*\n\n"
            "У базі вже є схоже місто: *" + suggested + "*\n"
            "Це воно ж, просто написано трохи інакше?",
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
        )
        await state.set_state(RegisterHome.waiting_city_confirm)
        return

    await _finish_city_step(message, state, typed_city)


async def _finish_city_step(message: Message, state: FSMContext, city: str):
    await state.update_data(city=city)
    await message.answer(
        "📝 *Опишіть своє житло:*\n"
        "Скільки кімнат, що поруч, особливості?\n\n"
        "_Наприклад: будинок, 5 хв до моря, машина включена, паркінг_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_description)


@router.callback_query(RegisterHome.waiting_city_confirm, F.data == "city_use_suggested")
async def city_use_suggested(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _finish_city_step(callback.message, state, data["suggested_city"])


@router.callback_query(RegisterHome.waiting_city_confirm, F.data == "city_keep_typed")
async def city_keep_typed(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _finish_city_step(callback.message, state, data["typed_city"])


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
        "🗑 /delete\\_profile — видалити профіль повністю\n\n"
        "❓ Питання? Пишіть @your\\_support",
        parse_mode="Markdown",
    )


@router.message(Command("delete_profile"))
async def cmd_delete_profile(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Так, видалити назавжди", callback_data="confirm_delete_profile")
    kb.button(text="Скасувати", callback_data="cancel_delete_profile")
    kb.adjust(1)
    await message.answer(
        "⚠️ *Ви впевнені, що хочете видалити профіль?*\n\n"
        "Будуть видалені без можливості відновлення:\n"
        "• Ваш профіль і фото житла\n"
        "• Усі ваші поїздки\n"
        "• Усі ваші лайки і матчі\n"
        "• Усі ваші відгуки\n\n"
        "Це безповоротна дія.",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "confirm_delete_profile")
async def confirm_delete_profile(callback: CallbackQuery, state: FSMContext):
    await delete_user_profile(callback.from_user.id)
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Профіль видалено")
    await callback.message.answer(
        "✅ Ваш профіль повністю видалено.\n\n"
        "Якщо захочете повернутись — просто напишіть /start знову 🙏"
    )


@router.callback_query(F.data == "cancel_delete_profile")
async def cancel_delete_profile(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Скасовано")
    await callback.message.answer("👍 Добре, профіль залишається без змін.")


@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🌍 *В якій країні ви живете?*\n_Наприклад: Кіпр_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_country)
    await callback.answer()
