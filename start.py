from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import get_user, create_user, update_user_home

router = Router()


class RegisterHome(StatesGroup):
    waiting_city        = State()
    waiting_country     = State()
    waiting_description = State()


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати поїздку",  callback_data="add_trip")
    kb.button(text="📋 Мої поїздки",     callback_data="my_trips")
    kb.button(text="❤️ Збережені",       callback_data="my_saved")
    kb.button(text="📊 Мій рейтинг",     callback_data="my_rating")
    kb.button(text="🏠 Змінити профіль", callback_data="edit_profile")
    kb.adjust(2)
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)

    if user and user["home_city"]:
        await message.answer(
            f"👋 З поверненням, *{user['name']}*!\n\n"
            f"🏠 Ваше житло: {user['home_city']}, {user['home_country']}\n\n"
            "Що бажаєте зробити?",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
    else:
        if not user:
            await create_user(message.from_user.id, message.from_user.first_name)
        await message.answer(
           "🏡 *Ласкаво просимо до Travel Swap Club Bot!*\n\n"
            "Обмінюйтесь житлом з мандрівниками по всьому світу 🌍\n"
            "Ви їдете до Барселони - хтось із Барселони приїде до вас!\n\n"
            "Для початку розкажіть де ви живете.\n\n"
            "📍 *В якому місті?*",
            parse_mode="Markdown",
        )
        await state.set_state(RegisterHome.waiting_city)


@router.message(Command("trip"))
async def cmd_trip(message: Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder as IKB
    kb = IKB()
    kb.button(text="✈️ Додати поїздку", callback_data="add_trip")
    await message.answer("Натисніть щоб додати нову поїздку:", reply_markup=kb.as_markup())


@router.message(Command("saved"))
async def cmd_saved(message: Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder as IKB
    kb = IKB()
    kb.button(text="❤️ Переглянути збережених", callback_data="my_saved")
    await message.answer("Ваші збережені хости:", reply_markup=kb.as_markup())


@router.message(Command("rating"))
async def cmd_rating(message: Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder as IKB
    kb = IKB()
    kb.button(text="📊 Переглянути рейтинг", callback_data="my_rating")
    await message.answer("Ваш рейтинг хоста:", reply_markup=kb.as_markup())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 *Як користуватись ботом:*\n\n"
        "1️⃣ /start — налаштувати профіль і описати житло\n"
        "2️⃣ /trip — додати поїздку (куди, коли, хто ви)\n"
        "3️⃣ Бот знайде людей що їдуть у ваш бік\n"
        "4️⃣ Прийміть матч — і спілкуйтесь напряму!\n"
        "5️⃣ Після обміну залиште відгук ⭐️\n\n"
        "❓ Питання? Пишіть @your\\_support",
        parse_mode="Markdown",
    )


# ── Реєстрація ───────────────────────────────────────────────────────────────

@router.message(RegisterHome.waiting_city)
async def home_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer("🌍 *В якій країні?* (наприклад: Кіпр, Іспанія, Україна)", parse_mode="Markdown")
    await state.set_state(RegisterHome.waiting_country)


@router.message(RegisterHome.waiting_country)
async def home_country(message: Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer(
        "📝 *Опишіть своє житло:*\n"
        "Скільки кімнат, що поруч, Wi-Fi, особливості?\n\n"
        "_Наприклад: 2-кімн. квартира біля моря, Айя-Напа. Балкон, Wi-Fi, паркінг._",
        parse_mode="Markdown",
    )
    await state.set_state(RegisterHome.waiting_description)


@router.message(RegisterHome.waiting_description)
async def home_description(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_user_home(
        message.from_user.id,
        data["city"], data["country"], message.text.strip(),
    )
    await state.clear()

    kb = InlineKeyboardBuilder()
    kb.button(text="✈️ Додати першу поїздку", callback_data="add_trip")

    await message.answer(
        f"✅ *Профіль збережено!*\n\n"
        f"🏠 {data['city']}, {data['country']}\n"
        f"📝 {message.text.strip()}\n\n"
        "Тепер додайте поїздку, щоб почати шукати матчі!",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📍 *В якому місті ви живете?*", parse_mode="Markdown")
    await state.set_state(RegisterHome.waiting_city)
    await callback.answer()
