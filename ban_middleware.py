"""
Middleware, що перевіряє чи користувач забанений, ще ДО того як
повідомлення чи callback потрапить у будь-який хендлер бота.
Забанені користувачі не можуть навіть пройти /start повторно.
"""
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

import db


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id is not None:
            banned = await db.is_banned(user_id)
            if banned:
                # Мовчки ігноруємо — забанений не отримує жодної відповіді,
                # не дізнається навіть чи бот працює
                return

        return await handler(event, data)
