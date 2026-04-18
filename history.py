from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_user_orders, get_order_by_id
from handlers.order import start_checkout_process
from menu_data import calculate_price
from handlers.menu import user_carts

router = Router()

def parse_order_items_to_cart(items_str: str) -> list:
    cart = []
    parts = [p.strip() for p in items_str.split(';') if p.strip()]
    for part in parts:
        if '(' in part and ')' in part:
            pizza = part.split('(')[0].strip()
            size = part.split('(')[1].split(')')[0].strip()
        else:
            pizza = part.split('+')[0].strip()
            size = "средний"
        toppings = []
        if '+' in part:
            toppings_str = part.split('+')[1].strip()
            if toppings_str and toppings_str != 'без начинок':
                toppings = [t.strip() for t in toppings_str.split(',')]
        price = calculate_price(pizza, size, toppings)
        cart.append({"pizza": pizza, "size": size, "toppings": toppings, "price": price})
    return cart

@router.message(F.text == "📋 Мои заказы")
async def show_history(message: Message):
    orders = get_user_orders(message.from_user.id, limit=5)
    if not orders:
        await message.answer("У вас пока нет заказов.")
        return
    for order in orders:
        text = (
            f"📦 Заказ №{order['order_id']} от {order['created_at'][:10]}\n"
            f"🍕 {order['items']}\n"
            f"💰 {order['total_price']}₽ | Статус: {order['status']}"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Повторить", callback_data=f"repeat_{order['order_id']}")
        builder.button(text="⭐ Оставить отзыв", callback_data=f"feedback_{order['order_id']}")
        builder.adjust(2)
        await message.answer(text, reply_markup=builder.as_markup())

@router.message(F.text == "🔄 Повторить заказ")
async def repeat_last_order(message: Message, state: FSMContext):
    orders = get_user_orders(message.from_user.id, limit=1)
    if not orders:
        await message.answer("Нет заказов для повтора.")
        return
    last = orders[0]
    cart = parse_order_items_to_cart(last['items'])
    user_carts[message.from_user.id] = cart
    await state.update_data(cart=cart, total_price=sum(item['price'] for item in cart))
    await start_checkout_process(message, message.from_user.id, state)

@router.callback_query(F.data.startswith("repeat_"))
async def repeat_order_callback(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])
    order = get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден")
        return
    cart = parse_order_items_to_cart(order['items'])
    user_carts[callback.from_user.id] = cart
    await state.update_data(cart=cart, total_price=sum(item['price'] for item in cart))
    await callback.message.answer("🔄 Повторяем ваш заказ...")
    await start_checkout_process(callback.message, callback.from_user.id, state)
    await callback.answer()

@router.callback_query(F.data.startswith("feedback_"))
async def feedback_from_history(callback: CallbackQuery, state: FSMContext):
    from handlers.feedback import ask_rating
    await ask_rating(callback.message, state)
    await callback.answer()