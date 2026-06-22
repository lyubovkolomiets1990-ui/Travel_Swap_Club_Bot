from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import (
    get_user, get_match, get_review, create_review,
    get_both_reviews, get_user_rating, get_active_trips,
    get_liked_users, add_like, remove_like,
)

router = Router()


class ReviewFSM(StatesGroup):
    cleanliness    = State()
    communication  = State()
    rule_following = State()
    overall        = State()
    comment        = State()


# ── Допоміжні ────────────────────────────────────────────────────────────────

def star_keyboard(crit_name: str, step: str) -> object:
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text="⭐️" * i, callback_data=f"rate_{step}_{i}")
    kb.adjust(1)
    return kb.as_markup()


CRITERIA_LABELS = {
    "cleanliness":    "🧹 Чистота",
    "communication":  "💬 Комунікація",
    "rule_following": "📋 Дотримання правил",
    "overall":        "✨ Загальне враження",
}

STEPS = ["cleanliness", "communication", "rule_following", "overall"]


async def get_partner_telegram_id(match, my_user_db_id: int) -> int | None:
    """Повертає telegram_id партнера по матчу"""
    trips = await get_active_trips()
    trip_map = {t["id"]: t for t in trips}

    for trip_id in (match["trip_id_1"], match["trip_id_2"]):
        trip = trip_map.get(trip_id)
        if trip and trip["user_id"] != my_user_db_id:
            return trip["telegram_id"]
    return None


# ── Запуск відгуку (викликається з matches.py після підтвердження) ────────────

async def send_review_request(bot, match_id: int, telegram_id: int, partner_name: str):
    """Надсилає запит на відгук після завершення обміну"""
    kb = InlineKeyboardBuilder()
    kb.button(text="⭐️ Залишити відгук", callback_data=f"start_review_{match_id}")
    kb.button(text="Пізніше",            callback_data="review_later")
    kb.adjust(1)
    await bot.send_message(
        telegram_id,
        f"🏠 Ваш обмін з *{partner_name}* завершено!\n\n"
        "Будь ласка, залиште відгук — це допомагає спільноті 🙏\n\n"
        "_Ваша оцінка буде схована до того моменту, поки партнер теж не залишить свою._",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )


# ── Старт відгуку ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("start_review_"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    match_id = int(callback.data.split("_")[2])
    user = await get_user(callback.from_user.id)

    existing = await get_review(match_id, user["id"])
    if existing:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Ви вже залишили відгук для цього обміну ✅", show_alert=True)
        return

    await state.update_data(match_id=match_id, reviewer_db_id=user["id"])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "📝 *Оцініть хоста за 4 критеріями*\n\n"
        "🧹 *Чистота*\nЧи було житло чисте і охайне при заселенні?",
        parse_mode="Markdown",
        reply_markup=star_keyboard("Чистота", "cleanliness"),
    )
    await state.set_state(ReviewFSM.cleanliness)
    await callback.answer()


# ── Кроки оцінки ─────────────────────────────────────────────────────────────

@router.callback_query(ReviewFSM.cleanliness, F.data.startswith("rate_cleanliness_"))
async def rate_cleanliness(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[2])
    await state.update_data(cleanliness=val)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"{'⭐️' * val} — збережено!\n\n"
        "💬 *Комунікація*\nШвидкість і якість відповідей?",
        parse_mode="Markdown",
        reply_markup=star_keyboard("Комунікація", "communication"),
    )
    await state.set_state(ReviewFSM.communication)
    await callback.answer()


@router.callback_query(ReviewFSM.communication, F.data.startswith("rate_communication_"))
async def rate_communication(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[2])
    await state.update_data(communication=val)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"{'⭐️' * val} — збережено!\n\n"
        "📋 *Дотримання правил*\nЧи дотримувались правил будинку і домовленостей?",
        parse_mode="Markdown",
        reply_markup=star_keyboard("Правила", "rule_following"),
    )
    await state.set_state(ReviewFSM.rule_following)
    await callback.answer()


@router.callback_query(ReviewFSM.rule_following, F.data.startswith("rate_rule_following_"))
async def rate_rule_following(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[2])
    await state.update_data(rule_following=val)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"{'⭐️' * val} — збережено!\n\n"
        "✨ *Загальне враження*\nЧи рекомендували б цього хоста іншим?",
        parse_mode="Markdown",
        reply_markup=star_keyboard("Враження", "overall"),
    )
    await state.set_state(ReviewFSM.overall)
    await callback.answer()


@router.callback_query(ReviewFSM.overall, F.data.startswith("rate_overall_"))
async def rate_overall(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.split("_")[2])
    await state.update_data(overall=val)
    await callback.message.edit_reply_markup(reply_markup=None)

    kb = InlineKeyboardBuilder()
    kb.button(text="Пропустити коментар", callback_data="skip_comment")
    await callback.message.answer(
        f"{'⭐️' * val} — збережено!\n\n"
        "💬 *Коментар* (необов'язково)\n"
        "Напишіть кілька слів або натисніть «Пропустити»:",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )
    await state.set_state(ReviewFSM.comment)
    await callback.answer()


@router.message(ReviewFSM.comment)
async def review_comment_text(message: Message, state: FSMContext, bot):
    await _finish_review(message, state, bot, comment=message.text.strip())


@router.callback_query(ReviewFSM.comment, F.data == "skip_comment")
async def review_skip_comment(callback: CallbackQuery, state: FSMContext, bot):
    await callback.message.edit_reply_markup(reply_markup=None)
    await _finish_review(callback.message, state, bot, comment="", tg_id=callback.from_user.id)
    await callback.answer()


# ── Збереження і сліпий відгук ───────────────────────────────────────────────

async def _finish_review(message: Message, state: FSMContext, bot, comment: str, tg_id: int = None):
    data = await state.get_data()
    await state.clear()

    match_id       = data["match_id"]
    reviewer_db_id = data["reviewer_db_id"]
    match          = await get_match(match_id)

    # Знаходимо reviewee (партнер)
    trips = await get_active_trips()
    trip_map = {t["id"]: t for t in trips}
    reviewee_db_id = None
    for trip_id in (match["trip_id_1"], match["trip_id_2"]):
        trip = trip_map.get(trip_id)
        if trip and trip["user_id"] != reviewer_db_id:
            reviewee_db_id = trip["user_id"]
            partner_tg_id  = trip["telegram_id"]
            partner_name   = trip["name"]
            break

    if not reviewee_db_id:
        await message.answer("⚠️ Не вдалось знайти партнера. Спробуйте пізніше.")
        return

    await create_review(
        match_id, reviewer_db_id, reviewee_db_id,
        data["cleanliness"], data["communication"],
        data["rule_following"], data["overall"], comment,
    )

    avg = round((data["cleanliness"] + data["communication"] +
                 data["rule_following"] + data["overall"]) / 4, 1)

    await message.answer(
        f"✅ *Відгук збережено!* Дякуємо 🙏\n\n"
        f"Ваша оцінка: *{avg}* ⭐️\n\n"
        "_Оцінки стануть видимі після того, як партнер теж залишить свій відгук._",
        parse_mode="Markdown",
    )

    # Перевіряємо чи обидва залишили — якщо так, відкриваємо оцінки
    all_reviews = await get_both_reviews(match_id)
    if len(all_reviews) >= 2:
        for rev in all_reviews:
            target_tg = partner_tg_id if rev["reviewer_id"] == reviewer_db_id else (tg_id or message.chat.id)
            rating = await get_user_rating(rev["reviewee_id"])
            try:
                await bot.send_message(
                    target_tg,
                    f"🎊 *Обидва відгуки готові!*\n\n"
                    f"Ваш підсумковий рейтинг:\n\n"
                    f"🧹 Чистота: *{rating.get('cleanliness','—')}* ⭐️\n"
                    f"💬 Комунікація: *{rating.get('communication','—')}* ⭐️\n"
                    f"📋 Дотримання правил: *{rating.get('rule_following','—')}* ⭐️\n"
                    f"✨ Загальне враження: *{rating.get('overall','—')}* ⭐️\n\n"
                    f"📊 Середній рейтинг: *{rating.get('average','—')}* · {rating.get('total',0)} відгуків",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


@router.callback_query(F.data == "review_later")
async def review_later(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "⏰ Нагадаємо через 2 дні. Відгук можна залишити протягом 7 днів після обміну."
    )
    await callback.answer()


# ── Мій рейтинг ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_rating")
async def my_rating(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    rating = await get_user_rating(user["id"])

    if not rating:
        await callback.message.answer(
            "📊 У вас ще немає відгуків.\n"
            "Рейтинг з'явиться після першого завершеного обміну!"
        )
        await callback.answer()
        return

    def bar(score: float) -> str:
        filled = round(score)
        return "⭐️" * filled + "☆" * (5 - filled)

    await callback.message.answer(
        f"📊 *Ваш рейтинг хоста*\n\n"
        f"🧹 Чистота\n{bar(rating['cleanliness'])} {rating['cleanliness']}\n\n"
        f"💬 Комунікація\n{bar(rating['communication'])} {rating['communication']}\n\n"
        f"📋 Дотримання правил\n{bar(rating['rule_following'])} {rating['rule_following']}\n\n"
        f"✨ Загальне враження\n{bar(rating['overall'])} {rating['overall']}\n\n"
        f"─────────────────\n"
        f"📈 Середнє: *{rating['average']}* · {rating['total']} відгуків",
        parse_mode="Markdown",
    )
    await callback.answer()


# ── Збережені (лайки) ────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_saved")
async def my_saved(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    liked = await get_liked_users(callback.from_user.id)
    if not liked:
        await callback.message.answer(
            "❤️ Збережених хостів ще немає.\n"
            "Натисніть ♡ на картці матчу, щоб зберегти!"
        )
        await callback.answer()
        return

    text = "❤️ *Збережені хости:*\n\n"
    kb = InlineKeyboardBuilder()
    for u in liked:
        rating = await get_user_rating(u["id"])
        stars = f"⭐️ {rating['average']}" if rating else "немає відгуків"
        text += f"👤 *{u['name']}* — {u['home_city']}, {u['home_country']} · {stars}\n"
        kb.button(text="👀 " + u["name"], callback_data="view_user_" + str(u["telegram_id"]))
    kb.adjust(1)

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("like_"))
async def toggle_like(callback: CallbackQuery):
    to_tg_id = int(callback.data.split("_")[1])
    from_tg_id = callback.from_user.id

    liked = await get_liked_users(from_tg_id)
    liked_ids = [u["telegram_id"] for u in liked]

    if to_tg_id in liked_ids:
        await remove_like(from_tg_id, to_tg_id)
        await callback.answer("Видалено зі збережених", show_alert=False)
    else:
        await add_like(from_tg_id, to_tg_id)
        await callback.answer("❤️ Збережено!", show_alert=False)
