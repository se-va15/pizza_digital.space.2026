from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import get_pending_order, cancel_order_if_possible
from config import OWNER_ID

router = Router()

@router.message(F.text == "❌ Отменить заказ")
async def cancel_order_handler(message: Message, bot: Bot, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("🚫 Оформление заказа отменено.")
        return

    user_id = message.from_user.id
    order = get_pending_order(user_id)
    if not order:
        await message.answer("❓ У вас нет активных заказов для отмены.")
        return

    order_id = order['order_id']
    success, msg = cancel_order_if_possible(order_id)
    if success:
        await message.answer(f"✅ Заказ №{order_id} отменён.")
        await bot.send_message(
            OWNER_ID,
            f"❌ Заказ №{order_id} отменён пользователем @{message.from_user.username or message.from_user.first_name}"
        )
    else:
        await message.answer(f"⚠️ {msg}")

@router.callback_query(F.data == "cancel_order")
async def cancel_inline(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🚫 Оформление заказа отменено.")
    await callback.answer()