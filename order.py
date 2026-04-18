import yookassa
from yookassa import Payment
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import (
    OWNER_ID, DELIVERY_TIME, DISCOUNT_PERCENT,
    YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
)
from database import (
    get_user, update_user_phone, update_user_address,
    save_order, get_orders_count
)
from states import OrderStates
from menu_data import calculate_price
from keyboards import (
    phone_keyboard, payment_method_keyboard, main_keyboard, confirmation_keyboard,
    cart_actions_keyboard, cart_management_keyboard, confirm_clear_cart_keyboard,
    send_menu_with_photos
)
from handlers.menu import get_cart, clear_cart

yookassa.Configuration.account_id = YOOKASSA_SHOP_ID
yookassa.Configuration.secret_key = YOOKASSA_SECRET_KEY

router = Router()

def format_cart_items(cart: list) -> str:
    """Форматирует содержимое корзины в строку для сохранения в БД."""
    parts = []
    for item in cart:
        toppings_str = ", ".join(item['toppings']) if item['toppings'] else "без начинок"
        parts.append(f"{item['pizza']} ({item['size']}) + {toppings_str}")
    return "; ".join(parts)

# ---------- Обработчики управления корзиной (состояние managing_cart) ----------
@router.callback_query(OrderStates.managing_cart, F.data == "add_more")
async def add_more_pizza(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await send_menu_with_photos(callback.message)
    await callback.answer()

@router.callback_query(OrderStates.managing_cart, F.data == "view_cart")
async def view_cart(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cart = get_cart(user_id)
    if not cart:
        await callback.message.edit_text("🛒 Ваша корзина пуста.", reply_markup=cart_actions_keyboard())
        await callback.answer()
        return

    text = "🛒 **Ваша корзина:**\n\n"
    total = 0
    for idx, item in enumerate(cart):
        toppings_str = ", ".join(item['toppings']) if item['toppings'] else "без начинок"
        text += f"{idx+1}. {item['pizza']} ({item['size']}) – {item['price']}₽\n   ({toppings_str})\n"
        total += item['price']
    text += f"\n**Итого: {total}₽**"

    await callback.message.edit_text(
        text,
        reply_markup=cart_management_keyboard(cart),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(OrderStates.managing_cart, F.data.startswith("remove_"))
async def remove_item(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    idx = int(callback.data.split("_")[1])
    cart = get_cart(user_id)
    if 0 <= idx < len(cart):
        removed = cart.pop(idx)
        await callback.answer(f"Удалено: {removed['pizza']}")
    else:
        await callback.answer("Ошибка индекса")
    await view_cart(callback, state)

@router.callback_query(OrderStates.managing_cart, F.data == "clear_cart")
async def ask_clear_cart(callback: CallbackQuery):
    await callback.message.edit_text(
        "🗑️ Вы уверены, что хотите очистить корзину?",
        reply_markup=confirm_clear_cart_keyboard()
    )
    await callback.answer()

@router.callback_query(OrderStates.managing_cart, F.data == "clear_cart_confirm")
async def clear_cart_confirm(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    clear_cart(user_id)
    await callback.message.edit_text("🛒 Корзина очищена.", reply_markup=cart_actions_keyboard())
    await callback.answer()

@router.callback_query(OrderStates.managing_cart, F.data == "checkout")
async def checkout(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cart = get_cart(user_id)
    if not cart:
        await callback.answer("Корзина пуста!")
        return

    total = sum(item['price'] for item in cart)
    await state.update_data(cart=cart, total_price=total)
    await state.set_state(OrderStates.waiting_for_phone)

    await start_checkout_process(callback.message, user_id, state)
    await callback.answer()

async def start_checkout_process(message: Message, user_id: int, state: FSMContext):
    """Начинает оформление заказа: проверяет телефон и запрашивает адрес."""
    data = await state.get_data()
    total = data['total_price']
    cart = data['cart']

    orders_cnt = get_orders_count(user_id)
    discount = 0
    if (orders_cnt + 1) % 5 == 0:
        discount = total * DISCOUNT_PERCENT // 100
        total -= discount
        await state.update_data(discount=discount, total_price=total)

    text = f"🧾 Ваш заказ (позиций: {len(cart)}):\n"
    for item in cart:
        toppings_str = ", ".join(item['toppings']) if item['toppings'] else "без начинок"
        text += f"• {item['pizza']} ({item['size']}) – {item['price']}₽\n"
    text += f"\n💰 Сумма: {total}₽"
    if discount:
        text += f"\n🎉 Скидка {DISCOUNT_PERCENT}% за каждый 5-й заказ!"

    user = get_user(user_id)
    if not user or not user.get("phone"):
        text += "\n\n📞 Пожалуйста, поделитесь номером телефона для связи."
        await message.answer(text, reply_markup=phone_keyboard())
        await state.set_state(OrderStates.waiting_for_phone)
    else:
        text += "\n\n📍 Введите адрес доставки:"
        await message.answer(text)
        await state.set_state(OrderStates.waiting_for_address)

# ---------- Обработчики контактных данных ----------
@router.message(OrderStates.waiting_for_phone, F.contact)
async def get_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    user_id = message.from_user.id
    update_user_phone(user_id, phone)
    await message.answer("📍 Введите адрес доставки:", reply_markup=main_keyboard())
    await state.set_state(OrderStates.waiting_for_address)

@router.message(OrderStates.waiting_for_phone, F.text)
async def get_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    user_id = message.from_user.id
    update_user_phone(user_id, phone)
    await message.answer("📍 Введите адрес доставки:", reply_markup=main_keyboard())
    await state.set_state(OrderStates.waiting_for_address)

@router.message(OrderStates.waiting_for_address)
async def get_address(message: Message, state: FSMContext):
    address = message.text
    user_id = message.from_user.id
    update_user_address(user_id, address)
    await state.update_data(address=address)
    await message.answer(
        "💬 Добавьте комментарий к заказу (например, 'без соли', 'побольше сыра')\n"
        "Или напишите 'нет', чтобы пропустить:"
    )
    await state.set_state(OrderStates.waiting_for_comment)

@router.message(OrderStates.waiting_for_comment)
async def get_comment(message: Message, state: FSMContext):
    comment = message.text if message.text.lower() != "нет" else ""
    await state.update_data(comment=comment)

    data = await state.get_data()
    cart = data['cart']
    total = data['total_price']
    discount = data.get('discount', 0)

    text = "📋 **Проверьте ваш заказ:**\n\n"
    for item in cart:
        toppings_str = ", ".join(item['toppings']) if item['toppings'] else "без начинок"
        text += f"• {item['pizza']} ({item['size']}) – {item['price']}₽\n   _{toppings_str}_\n"
    text += f"\n💰 **Сумма: {total}₽**"
    if discount:
        text += f"\n🎉 Скидка {DISCOUNT_PERCENT}% за каждый 5-й заказ!"
    text += f"\n\n📍 Адрес: {data['address']}\n💬 Комментарий: {comment or 'нет'}\n\nВсё верно?"

    await message.answer(text, reply_markup=confirmation_keyboard(), parse_mode="Markdown")
    await state.set_state(OrderStates.waiting_for_confirmation)

# ---------- Подтверждение и оплата ----------
@router.callback_query(OrderStates.waiting_for_confirmation, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💳 Выберите способ оплаты:", reply_markup=payment_method_keyboard())
    await state.set_state(OrderStates.waiting_for_payment)
    await callback.answer()

@router.callback_query(OrderStates.waiting_for_confirmation, F.data == "edit_order")
async def edit_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🔄 Оформление заказа отменено. Начните заново из меню.")
    await callback.answer()

@router.callback_query(OrderStates.waiting_for_payment, F.data == "pay_cash")
async def process_cash_payment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = callback.from_user.id
    cart = data['cart']
    items_text = format_cart_items(cart)

    order_id = save_order(
        user_id, items_text, data['total_price'],
        data['address'], data.get('comment', ''), 'cash'
    )

    text = (
        f"✅ Заказ №{order_id} принят!\n\n"
        f"🕒 Ожидаемое время доставки: {DELIVERY_TIME} мин.\n"
        f"💰 Сумма: {data['total_price']}₽\n"
        f"💵 Оплата наличными курьеру"
    )
    await callback.message.answer(text)

    owner_text = (
        f"🆕 НОВЫЙ ЗАКАЗ №{order_id}\n"
        f"👤 Клиент: @{callback.from_user.username or callback.from_user.first_name}\n"
        f"📞 Телефон: {get_user(user_id)['phone']}\n"
        f"🍕 {items_text}\n"
        f"💰 Сумма: {data['total_price']}₽\n"
        f"📍 Адрес: {data['address']}\n"
        f"💬 Комментарий: {data.get('comment', 'нет')}\n"
        f"💵 Оплата наличными"
    )
    await bot.send_message(OWNER_ID, owner_text)
    await state.clear()
    await callback.answer()

@router.callback_query(OrderStates.waiting_for_payment, F.data == "pay_card")
async def process_card_payment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = callback.from_user.id
    cart = data['cart']
    items_text = format_cart_items(cart)

    try:
        payment = Payment.create({
            "amount": {
                "value": str(data['total_price']),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/your_bot"
            },
            "capture": True,
            "description": f"Заказ пиццы от пользователя {user_id}",
            "metadata": {"user_id": user_id}
        })
        payment_url = payment.confirmation.confirmation_url
    except Exception:
        payment_url = "https://example.com/payment (тестовая ссылка)"

    order_id = save_order(
        user_id, items_text, data['total_price'],
        data['address'], data.get('comment', ''), 'card'
    )

    text = (
        f"✅ Заказ №{order_id} принят!\n\n"
        f"💳 Для оплаты перейдите по ссылке:\n{payment_url}\n\n"
        f"🕒 Ожидаемое время доставки: {DELIVERY_TIME} мин.\n"
        f"💰 Сумма: {data['total_price']}₽"
    )
    await callback.message.answer(text, disable_web_page_preview=True)

    owner_text = (
        f"🆕 НОВЫЙ ЗАКАЗ №{order_id}\n"
        f"👤 Клиент: @{callback.from_user.username or callback.from_user.first_name}\n"
        f"📞 Телефон: {get_user(user_id)['phone']}\n"
        f"🍕 {items_text}\n"
        f"💰 Сумма: {data['total_price']}₽\n"
        f"📍 Адрес: {data['address']}\n"
        f"💬 Комментарий: {data.get('comment', 'нет')}\n"
        f"💳 Оплата картой (ожидание)"
    )
    await bot.send_message(OWNER_ID, owner_text)
    await state.clear()
    await callback.answer()