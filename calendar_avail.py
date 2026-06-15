"""
Календар доступності — коли житло відкрите/закрите для гостей
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db

router = Router()

MONTHS_UA = {
    1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень",
    5: "Травень", 6: "Червень", 7: "Липень", 8: "Серпень",
    9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень",
}


class CalendarFSM(StatesGroup):
    waiting_blocked_dates = State()
    waiting_reason        = State()


def months_kb() -> object:
    """Клавіатура вибору місяців"""
    from datetime import datetime
    kb = InlineKeyboardBuilder()
    current_month = datetime.now().month
    current_year  = datetime.now().year

    for i in range(12):
        month = ((current_month - 1 + i) % 12) + 1
        year  = current_year + ((current_month - 1 + i) // 12)
        kb.button(
            text=f"{MONTHS_UA[month]} {year}",
            callback_data=f"block_month_{month}_{year}",
        )
    kb.button(text="✅ Готово", callback_data="calendar_done")
    kb.adjust(2)
    return kb.as_markup()


@router.message(Command("calendar"))
async def cmd_calendar(message: Message):
    await show_calendar(message)


@router.callback_query(F.data == "my_calendar")
async def open_calendar(callback: CallbackQuery):
    await show_calendar(callback.message)
    await callback.answer()


async def show_calendar(message: Message):
    user = await db.get_user(message.chat.id)
    if not user:
        await message.answer("Спочатку зареєструйтесь через /start")
        return

    blocked = await db.get_blocked_months(message.chat.id)
    blocked_text = ""
    if blocked:
        blocked_text = "\n\n🚫 *Заблоковані місяці:*\n" + "\n".join(
            f"• {MONTHS_UA.get(int(b['month']), b['month'])} {b['year']}"
            + (f" — {b['reason']}" if b.get("reason") else "")
            for b in blocked
        )

    await message.answer(
        "📅 *Календар доступності*\n\n"
        "Вкажіть коли ваше житло *недоступне* для гостей.\n"
        "Наприклад: серпень — приїжджає сім'я, або грудень — самі вдома.\n\n"
        "Обираючи місяці нижче ви блокуєте їх від показу у пошуку."
        f"{blocked_text}",
        parse_mode="Markdown",
        reply_markup=months_kb(),
    )


@router.callback_query(F.data.startswith("block_month_"))
async def block_month(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    month = int(parts[2])
    year  = int(parts[3])

    await state.update_data(block_month=month, block_year=year)

    # Перевіряємо чи вже заблоковано
    blocked = await db.get_blocked_months(callback.from_user.id)
    already = any(int(b["month"]) == month and int(b["year"]) == year for b in blocked)

    if already:
        await db.unblock_month(callback.from_user.id, month, year)
        await callback.answer(f"✅ {MONTHS_UA[month]} {year} — розблоковано!", show_alert=False)
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="Пропустити причину", callback_data=f"block_confirm_{month}_{year}_")
        await callback.message.answer(
            f"🚫 Блокую *{MONTHS_UA[month]} {year}*\n\n"
            "Вкажіть причину (необов'язково) — гості це не побачать, лише для вас:\n"
            "_Наприклад: приїжджає сім'я, ремонт, сам вдома_",
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
        )
        await state.set_state(CalendarFSM.waiting_reason)
        await state.update_data(block_month=month, block_year=year)
    await callback.answer()


@router.message(CalendarFSM.waiting_reason)
async def block_reason_text(callback_or_msg, state: FSMContext):
    data = await state.get_data()
    reason = callback_or_msg.text.strip() if hasattr(callback_or_msg, "text") else ""
    await db.block_month(callback_or_msg.from_user.id, data["block_month"], data["block_year"], reason)
    await state.clear()
    await callback_or_msg.answer(
        f"✅ *{MONTHS_UA[data['block_month']]} {data['block_year']}* заблоковано!\n\n"
        "Гості не побачать ваше житло в цей місяць.",
        parse_mode="Markdown",
    )
    await show_calendar(callback_or_msg)


@router.callback_query(F.data.startswith("block_confirm_"))
async def block_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    month  = int(parts[2])
    year   = int(parts[3])
    reason = parts[4] if len(parts) > 4 else ""
    await db.block_month(callback.from_user.id, month, year, reason)
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(f"✅ {MONTHS_UA[month]} {year} заблоковано!", show_alert=False)
    await show_calendar(callback.message)


@router.callback_query(F.data == "calendar_done")
async def calendar_done(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Календар збережено!", show_alert=False)
    await callback.message.answer(
        "✅ *Календар оновлено!*\n\n"
        "Гості не будуть бачити ваше житло у заблоковані місяці.\n"
        "Змінити можна будь-коли через /calendar",
        parse_mode="Markdown",
    )
