from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import save_feedback
from states import FeedbackStates
from keyboards import rating_keyboard
from config import OWNER_ID

router = Router()

@router.message(F.text == "⭐ Оставить отзыв")
async def ask_rating(message: Message, state: FSMContext):
    await message.answer("Оцените нашу работу от 1 до 5:", reply_markup=rating_keyboard())
    await state.set_state(FeedbackStates.waiting_for_rating)

@router.callback_query(FeedbackStates.waiting_for_rating, F.data.startswith("rating_"))
async def get_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await callback.message.delete()
    await callback.message.answer(
        f"Спасибо за оценку {rating}⭐\nНапишите отзыв (или отправьте '-', чтобы пропустить):"
    )
    await state.set_state(FeedbackStates.waiting_for_comment)
    await callback.answer()

@router.message(FeedbackStates.waiting_for_comment)
async def get_feedback_comment(message: Message, state: FSMContext, bot: Bot):
    comment = message.text if message.text != "-" else ""
    data = await state.get_data()
    user_id = message.from_user.id
    save_feedback(user_id, data['rating'], comment)
    await message.answer("❤️ Спасибо за отзыв! Это помогает нам становиться лучше.")
    await bot.send_message(
        OWNER_ID,
        f"⭐ Новый отзыв:\n👤 @{message.from_user.username or message.from_user.first_name}\n"
        f"Оценка: {data['rating']}/5\nКомментарий: {comment or 'нет'}"
    )
    await state.clear()