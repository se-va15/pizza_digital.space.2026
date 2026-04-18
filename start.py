from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import add_user
from keyboards import main_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    add_user(user.id, user.username or "", user.first_name or "Гость")
    await message.answer(
        f"🍕 Добро пожаловать, {user.first_name or 'гость'}!\n\n"
        "Я помогу вам заказать вкусную пиццу с доставкой.\n"
        "Используйте кнопки меню для навигации.",
        reply_markup=main_keyboard()
    )