from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS
from db import get_user

router = Router()

SUPPORT_ID = 8863917988  # @TravelSwapSupport


class SupportFSM(StatesGroup):
    waiting_message = State()


# ── Кнопка "Написати в підтримку" ────────────────────────────────────────────

@router.callback_query(F.data == "contact_support")
async def contact_support_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "✍️ *Напишіть ваше питання*\n\n"
        "_Опишіть що сталось — ми відповімо якнайшвидше_",
        parse_mode="Markdown",
    )
    await state.set_state(SupportFSM.waiting_message)


@router.message(SupportFSM.waiting_message)
async def support_message_received(message: Message, state: FSMContext, bot):
    await state.clear()

    user = await get_user(message.from_user.id)
    name = user["name"] if user else message.from_user.first_name
    city = f"{user['home_city']}, {user['home_country']}" if user and user["home_city"] else "—"
    tg_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "немає username"

    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Відповісти", callback_data=f"support_reply_{tg_id}")
    kb.adjust(1)

    try:
        await bot.send_message(
            SUPPORT_ID,
            f"📩 *Нове звернення в підтримку*\n\n"
            f"👤 {name}\n"
            f"🏠 {city}\n"
            f"📱 {username}\n"
            f"🆔 {tg_id}\n\n"
            f"💬 *Питання:*\n{message.text}",
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
        )
        await message.answer(
            "✅ *Питання надіслано!*\n\n"
            "Ми відповімо вам найближчим часом 🙏",
            parse_mode="Markdown",
        )
    except Exception:
        await message.answer(
            "😔 Не вдалось надіслати питання. Напишіть напряму: @TravelSwapSupport"
        )


# ── Відповідь від підтримки ───────────────────────────────────────────────────

class SupportReplyFSM(StatesGroup):
    waiting_reply = State()


@router.callback_query(F.data.startswith("support_reply_"))
async def support_reply_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != SUPPORT_ID and callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    target_id = int(callback.data.split("_")[2])
    await state.update_data(reply_target_id=target_id)
    await callback.answer()
    await callback.message.answer(
        "✍️ Напишіть відповідь користувачу:",
    )
    await state.set_state(SupportReplyFSM.waiting_reply)


@router.message(SupportReplyFSM.waiting_reply)
async def support_reply_send(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    target_id = data["reply_target_id"]
    await state.clear()

    try:
        await bot.send_message(
            target_id,
            f"💬 *Відповідь від підтримки Travel Swap Club:*\n\n"
            f"{message.text}",
            parse_mode="Markdown",
        )
        await message.answer("✅ Відповідь надіслано!")
    except Exception:
        await message.answer("😔 Не вдалось надіслати відповідь — користувач міг заблокувати бота.")
