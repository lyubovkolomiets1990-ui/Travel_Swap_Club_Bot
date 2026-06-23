from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import get_user, create_user, update_user_home, delete_user_profile, get_all_known_cities
from config import ADMIN_IDS, VERIFICATION_CHANNEL_ID
import difflib

router = Router()


class OnboardingFSM(StatesGroup):
    waiting_agreement = State()


class RejectReason(StatesGroup):
    waiting_reason = State()


class RegisterHome(StatesGroup):
    waiting_country       = State()
    waiting_city          = State()
    waiting_city_confirm  = State()
    waiting_description   = State()
    waiting_photos        = State()
    waiting_pets          = State()
    waiting_pets_info     = State()
    waiting_extra_info    = State()


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати поїздку",   callback_data="add_trip")
    kb.button(text="📋 Мої поїздки",      callback_data="my_trips")
    kb.button(text="🔍 Переглянути всіх", callback_data="browse_start")
    kb.button(text="⭐️ Топ за рейтингом",  callback_data="browse_top")
    kb.button(text="🏠 Куди я хочу поїхати", callback_data="browse_find_home")
    kb.button(text="📥 Хто їде до мене",     callback_data="browse_find_to_me")
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
            "📥 *Хто їде до мене* — дивіться, хто хоче приїхати у ваше місто\n"
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
            "🏠 *Куди я хочу поїхати* — шукайте, хто живе саме там, куди ви хочете поїхати\n"
            "📥 *Хто їде до мене* — дивіться, хто хоче приїхати у ваше місто\n"
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
    await _ask_extra_info(callback.message, state)


@router.message(RegisterHome.waiting_pets_info)
async def pets_info(message: Message, state: FSMContext):
    await state.update_data(pets_info=message.text.strip())
    await _ask_extra_info(message, state)


async def _ask_extra_info(message: Message, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Пропустити", callback_data="extra_info_skip")
    await message.answer(
        "ℹ️ *Щось ще варто знати?*\n\n"
        "Наприклад: машина включена в обмін, басейн, парковка, "
        "особливі умови чи побажання.\n\n"
        "_Можете пропустити, якщо нема що додати_",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )
    await state.set_state(RegisterHome.waiting_extra_info)


@router.message(RegisterHome.waiting_extra_info)
async def extra_info_text(message: Message, state: FSMContext, bot):
    await state.update_data(extra_info=message.text.strip())
    await _save_profile(message, state, bot)


@router.callback_query(RegisterHome.waiting_extra_info, F.data == "extra_info_skip")
async def extra_info_skip(callback: CallbackQuery, state: FSMContext, bot):
    await state.update_data(extra_info="")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _save_profile(callback.message, state, bot)


# ── Збереження профілю ────────────────────────────────────────────────────────

async def _save_profile(message: Message, state: FSMContext, bot=None):
    data = await state.get_data()
    photos_str = ",".join(data.get("photos", []))
    has_pets   = data.get("has_pets", 0)
    pets_info  = data.get("pets_info", "")
    extra_info = data.get("extra_info", "")
    editing_field = data.get("editing_field")

    # Якщо людина змінює фото або опис ПІСЛЯ того як вже була верифікована —
    # надсилаємо сповіщення в канал модерації про новий контент для перегляду.
    # Профіль залишається видимим (не блокуємо людину), просто даємо вам
    # можливість перевірити і заблокувати якщо щось не так.
    existing_user = await get_user(message.chat.id)
    was_already_verified = (
        editing_field in ("description", "photos")
        and existing_user is not None
        and "verification_status" in existing_user.keys()
        and existing_user["verification_status"] == "verified"
    )

    await update_user_home(
        message.chat.id,
        data["city"], data["country"], data["description"],
        photos=photos_str, has_pets=has_pets, pets_info=pets_info,
        extra_info=extra_info,
    )
    await state.clear()

    photos_count = len([p for p in photos_str.split(",") if p])
    pets_line = f"🐾 Тварини: {pets_info}\n" if has_pets else ""
    extra_line = f"ℹ️ Інше: {extra_info}\n" if extra_info else ""

    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати поїздку", callback_data="add_trip")

    closing_line = (
        "Ваш профіль на перегляді в модерації — оновлення вже надіслано! ✅"
        if was_already_verified else
        "Тепер додайте поїздку — і профіль одразу відправиться на верифікацію!"
    )

    await message.answer(
        f"✅ *Профіль збережено!*\n\n"
        f"🏠 {data['city']}, {data['country']}\n"
        f"📝 {data['description']}\n"
        f"📸 Фото: {photos_count} шт.\n"
        f"{pets_line}"
        f"{extra_line}\n"
        f"{closing_line}",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )

    # Сповіщаємо канал модерації, якщо вже верифікований профіль змінив фото/опис
    if was_already_verified and bot:
        await _notify_profile_changed(bot, message.chat.id, editing_field)


async def _notify_profile_changed(bot, telegram_id: int, changed_field: str):
    from aiogram.types import InputMediaPhoto

    user = await get_user(telegram_id)
    if not user:
        return

    field_label = "опис житла" if changed_field == "description" else "фото житла"
    photos = [p for p in (user["home_photos"] or "").split(",") if p]

    kb = InlineKeyboardBuilder()
    kb.button(text="👍 Все гаразд", callback_data="changes_ok_" + str(telegram_id))
    kb.button(text="❌ Відхилити зміни", callback_data="verify_reject_" + str(telegram_id))
    kb.button(text="🚫 Заблокувати назавжди", callback_data="verify_ban_" + str(telegram_id))
    kb.adjust(2, 1)

    caption = (
        f"✏️ *Користувач змінив {field_label}*\n\n"
        f"👤 {user['name']}\n"
        f"🏠 {user['home_city']}, {user['home_country']}\n"
        f"📝 {user['home_description']}\n\n"
        f"🆔 {telegram_id}"
    )

    targets = [VERIFICATION_CHANNEL_ID] if VERIFICATION_CHANNEL_ID else ADMIN_IDS

    for target_id in targets:
        try:
            if len(photos) > 1:
                media = [InputMediaPhoto(media=p) for p in photos[:10]]
                media[-1].caption = caption
                media[-1].parse_mode = "Markdown"
                await bot.send_media_group(target_id, media=media)
                await bot.send_message(target_id, "👆 Перевірте зміни:", reply_markup=kb.as_markup())
            elif len(photos) == 1:
                await bot.send_photo(
                    target_id, photo=photos[0], caption=caption,
                    parse_mode="Markdown", reply_markup=kb.as_markup(),
                )
            else:
                await bot.send_message(
                    target_id, caption,
                    parse_mode="Markdown", reply_markup=kb.as_markup(),
                )
        except Exception:
            pass


@router.callback_query(F.data.startswith("changes_ok_"))
async def changes_ok(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("👍 Прийнято")


async def _notify_admins_new_user(bot, telegram_id: int, trip: dict = None):
    from aiogram.types import InputMediaPhoto

    user = await get_user(telegram_id)
    if not user:
        return

    pets_line = f"🐾 Тварини: {user['pets_info']}\n" if user["has_pets"] else ""
    extra = user["extra_info"] if "extra_info" in user.keys() else ""
    extra_line = f"ℹ️ Інше: {extra}\n" if extra else ""
    photos = [p for p in (user["home_photos"] or "").split(",") if p]

    trip_line = ""
    if trip:
        trip_line = (
            f"\n✈️ *Поїздка:*\n"
            f"Куди: {trip['destination_city']}, {trip['destination_country']}\n"
            f"Дати: {trip['date_from']} — {trip['date_to']}\n"
            f"Гостей: {trip['guests_count']}\n"
        )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Верифікувати", callback_data="verify_approve_" + str(telegram_id))
    kb.button(text="❌ Відхилити", callback_data="verify_reject_" + str(telegram_id))
    kb.button(text="🚫 Заблокувати назавжди", callback_data="verify_ban_" + str(telegram_id))
    kb.adjust(2, 1)

    caption = (
        f"🆕 *Новий профіль на верифікацію*\n\n"
        f"👤 {user['name']}\n"
        f"🏠 Живе: {user['home_city']}, {user['home_country']}\n"
        f"📝 {user['home_description']}\n"
        f"{pets_line}"
        f"{extra_line}"
        f"{trip_line}\n"
        f"🆔 {telegram_id}"
    )

    targets = [VERIFICATION_CHANNEL_ID] if VERIFICATION_CHANNEL_ID else ADMIN_IDS

    for target_id in targets:
        try:
            if len(photos) > 1:
                # Альбом — підпис іде під останнім фото, кнопки окремим повідомленням після
                media = [InputMediaPhoto(media=p) for p in photos[:10]]
                media[-1].caption = caption
                media[-1].parse_mode = "Markdown"
                await bot.send_media_group(target_id, media=media)
                await bot.send_message(
                    target_id, "👆 Рішення по профілю вище:",
                    reply_markup=kb.as_markup(),
                )
            elif len(photos) == 1:
                await bot.send_photo(
                    target_id, photo=photos[0], caption=caption,
                    parse_mode="Markdown", reply_markup=kb.as_markup(),
                )
            else:
                await bot.send_message(
                    target_id, caption,
                    parse_mode="Markdown", reply_markup=kb.as_markup(),
                )
        except Exception:
            pass


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


@router.message(Command("edit_profile"))
async def cmd_edit_profile(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌍 Місто і країну",   callback_data="edit_location")
    kb.button(text="📝 Опис житла",       callback_data="edit_description")
    kb.button(text="📸 Фото",             callback_data="edit_photos")
    kb.button(text="🐾 Тварини",          callback_data="edit_pets")
    kb.button(text="ℹ️ Додаткову інфо",   callback_data="edit_extra")
    kb.adjust(1)
    await message.answer(
        "✏️ *Що бажаєте змінити?*",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )


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
        "✏️ /edit\\_profile — змінити опис, фото чи місто\n"
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


# ── Адмінська команда: видалення чужого профілю ───────────────────────────────

@router.message(Command("admin_delete"))
async def cmd_admin_delete(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return  # ігноруємо мовчки, не показуємо що команда існує

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer(
            "⚙️ *Адмінська команда*\n\n"
            "Використання: `/admin_delete TELEGRAM_ID`\n\n"
            "_Наприклад: /admin\\_delete 487287005_",
            parse_mode="Markdown",
        )
        return

    target_id = int(parts[1].strip())
    user = await get_user(target_id)

    if not user:
        await message.answer("😔 Користувача з таким telegram_id не знайдено в базі.")
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Так, видалити", callback_data="admin_confirm_delete_" + str(target_id))
    kb.button(text="Скасувати", callback_data="admin_cancel_delete")
    kb.adjust(1)
    await message.answer(
        f"⚠️ *Видалити профіль користувача?*\n\n"
        f"👤 {user['name']}\n"
        f"🏠 {user['home_city'] or '—'}, {user['home_country'] or '—'}\n"
        f"🆔 {target_id}\n\n"
        "Це видалить профіль, поїздки, лайки, відгуки — без можливості відновлення.",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("admin_confirm_delete_"))
async def admin_confirm_delete(callback: CallbackQuery, bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    target_id = int(callback.data.split("_")[3])
    await delete_user_profile(target_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Профіль видалено")
    await callback.message.answer(f"✅ Профіль користувача {target_id} видалено.")

    try:
        await bot.send_message(
            target_id,
            "ℹ️ Ваш профіль у Travel Swap Club було видалено адміністратором.\n\n"
            "Якщо вважаєте це помилкою — зв'яжіться з підтримкою @your\\_support.",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_cancel_delete")
async def admin_cancel_delete(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Скасовано")


# ── Блокування користувачів ───────────────────────────────────────────────────

@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer(
            "⚙️ Використання: `/ban TELEGRAM_ID [причина]`\n\n"
            "_Наприклад: /ban 487287005 шахрайський профіль_",
            parse_mode="Markdown",
        )
        return

    target_id = int(parts[1].strip())
    reason = parts[2].strip() if len(parts) > 2 else ""

    from db import ban_user
    await ban_user(target_id, reason)
    await delete_user_profile(target_id)

    await message.answer(
        f"🚫 Користувач {target_id} заблокований"
        + (f" (причина: {reason})" if reason else "")
        + ".\n\nПрофіль видалено, новий створити він не зможе."
    )


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer(
            "⚙️ Використання: `/unban TELEGRAM_ID`",
            parse_mode="Markdown",
        )
        return

    target_id = int(parts[1].strip())
    from db import unban_user
    await unban_user(target_id)
    await message.answer(
        f"✅ Користувача {target_id} розблоковано — може знову написати /start."
    )


@router.message(Command("banned_list"))
async def cmd_banned_list(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    from db import get_all_banned
    banned = await get_all_banned()
    if not banned:
        await message.answer("✅ Список блокувань порожній.")
        return

    text = "🚫 *Заблоковані користувачі:*\n\n"
    for b in banned:
        reason_text = f" — {b['reason']}" if b["reason"] else ""
        text += f"🆔 {b['telegram_id']}{reason_text}\n"
    await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data.startswith("verify_ban_"))
async def verify_ban(callback: CallbackQuery, bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    target_id = int(callback.data.split("_")[2])
    from db import ban_user
    await ban_user(target_id, "Заблоковано через модерацію верифікації")
    await delete_user_profile(target_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("🚫 Заблоковано назавжди")
    await callback.message.answer(f"🚫 Користувач {target_id} заблокований і видалений.")


# ── Верифікація нових профілів ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("verify_approve_"))
async def verify_approve(callback: CallbackQuery, bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    target_id = int(callback.data.split("_")[2])
    from db import set_verification_status
    await set_verification_status(target_id, "verified")

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Верифіковано!")

    try:
        await bot.send_message(
            target_id,
            "🎉 *Ваш профіль верифіковано!*\n\n"
            "Тепер його видно іншим мандрівникам у пошуку. "
            "Додайте поїздку, щоб почати шукати матчі! ✈️",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("verify_reject_"))
async def verify_reject(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    target_id = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Стандартне повідомлення", callback_data="reject_standard_" + str(target_id))
    kb.button(text="✍️ Написати свою причину", callback_data="reject_custom_" + str(target_id))
    kb.adjust(1)
    await callback.message.answer(
        "Як відхилити профіль?",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("reject_standard_"))
async def reject_standard(callback: CallbackQuery, bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    target_id = int(callback.data.split("_")[2])
    await _send_rejection(
        bot, target_id,
        "Перевірте, чи фото та опис відповідають правилам спільноти, "
        "і спробуйте оновити профіль через «🏠 Змінити профіль».",
    )
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("❌ Відхилено")
    await callback.message.answer(f"❌ Профіль {target_id} відхилено зі стандартним поясненням.")


@router.callback_query(F.data.startswith("reject_custom_"))
async def reject_custom_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    target_id = int(callback.data.split("_")[2])
    await state.update_data(reject_target_id=target_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await callback.message.answer(
        "✍️ *Напишіть причину відхилення*\n\n"
        "_Наприклад: «додайте фото житла зсередини» або "
        "«опис занадто короткий, розкажіть більше про умови обміну»_\n\n"
        "_Це повідомлення прийде користувачу від імені модерації_",
        parse_mode="Markdown",
    )
    await state.set_state(RejectReason.waiting_reason)


@router.message(RejectReason.waiting_reason)
async def reject_custom_send(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    target_id = data["reject_target_id"]
    reason = message.text.strip()
    await state.clear()

    await _send_rejection(bot, target_id, reason)
    await message.answer(f"❌ Профіль {target_id} відхилено з вашим поясненням.")


async def _send_rejection(bot, target_id: int, reason_text: str):
    from db import set_verification_status
    await set_verification_status(target_id, "rejected")
    try:
        await bot.send_message(
            target_id,
            f"😔 *Ваш профіль не пройшов верифікацію*\n\n"
            f"{reason_text}\n\n"
            "Питання? Пишіть @your\\_support",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@router.message(Command("pending"))
async def cmd_pending_verifications(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    from db import get_pending_verifications
    pending = await get_pending_verifications()

    if not pending:
        await message.answer("✅ Немає профілів що очікують верифікації.")
        return

    await message.answer(f"⏳ Очікують верифікації: {len(pending)}")

    for user in pending:
        pets_line = f"🐾 Тварини: {user['pets_info']}\n" if user["has_pets"] else ""
        photos = (user["home_photos"] or "").split(",") if user["home_photos"] else []

        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Верифікувати", callback_data="verify_approve_" + str(user["telegram_id"]))
        kb.button(text="❌ Відхилити", callback_data="verify_reject_" + str(user["telegram_id"]))
        kb.button(text="🚫 Заблокувати назавжди", callback_data="verify_ban_" + str(user["telegram_id"]))
        kb.adjust(2, 1)

        caption = (
            f"👤 {user['name']}\n"
            f"🏠 {user['home_city']}, {user['home_country']}\n"
            f"📝 {user['home_description']}\n"
            f"{pets_line}"
            f"🆔 {user['telegram_id']}"
        )

        try:
            if photos and photos[0]:
                await message.answer_photo(
                    photo=photos[0], caption=caption, reply_markup=kb.as_markup()
                )
            else:
                await message.answer(caption, reply_markup=kb.as_markup())
        except Exception:
            await message.answer(caption, reply_markup=kb.as_markup())


@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="🌍 Місто і країну",   callback_data="edit_location")
    kb.button(text="📝 Опис житла",       callback_data="edit_description")
    kb.button(text="📸 Фото",             callback_data="edit_photos")
    kb.button(text="🐾 Тварини",          callback_data="edit_pets")
    kb.button(text="ℹ️ Додаткову інфо",   callback_data="edit_extra")
    kb.adjust(1)
    await callback.message.answer(
        "✏️ *Що бажаєте змінити?*",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_location")
async def edit_location(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🌍 *В якій країні ви живете?*\n_Наприклад: Кіпр_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_country)
    await callback.answer()


@router.callback_query(F.data == "edit_description")
async def edit_description_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    await state.update_data(
        city=user["home_city"], country=user["home_country"],
        photos=(user["home_photos"] or "").split(",") if user["home_photos"] else [],
        has_pets=user["has_pets"], pets_info=user["pets_info"],
        extra_info=user["extra_info"] if "extra_info" in user.keys() else "",
        editing_field="description",
    )
    await callback.message.answer(
        "📝 *Новий опис житла:*\n\n"
        "_Наприклад: будинок, 5 хв до моря, машина включена, паркінг_",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_description)
    await callback.answer()


@router.callback_query(F.data == "edit_photos")
async def edit_photos_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    await state.update_data(
        city=user["home_city"], country=user["home_country"],
        description=user["home_description"],
        has_pets=user["has_pets"], pets_info=user["pets_info"],
        extra_info=user["extra_info"] if "extra_info" in user.keys() else "",
        photos=[],
        editing_field="photos",
    )
    await callback.message.answer(
        "📸 *Надішліть нові фото житла* (до 5 штук)\n\n"
        "_Старі фото буде замінено новими_",
        parse_mode="Markdown",
        reply_markup=_skip_kb("photos_done"),
    )
    await state.set_state(RegisterHome.waiting_photos)
    await callback.answer()


@router.callback_query(F.data == "edit_pets")
async def edit_pets_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    await state.update_data(
        city=user["home_city"], country=user["home_country"],
        description=user["home_description"],
        photos=(user["home_photos"] or "").split(",") if user["home_photos"] else [],
        extra_info=user["extra_info"] if "extra_info" in user.keys() else "",
        editing_field="pets",
    )
    await callback.answer()
    await _ask_pets(callback.message, state)


@router.callback_query(F.data == "edit_extra")
async def edit_extra_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    await state.update_data(
        city=user["home_city"], country=user["home_country"],
        description=user["home_description"],
        photos=(user["home_photos"] or "").split(",") if user["home_photos"] else [],
        has_pets=user["has_pets"], pets_info=user["pets_info"],
        editing_field="extra",
    )
    await callback.answer()
    await _ask_extra_info(callback.message, state)
