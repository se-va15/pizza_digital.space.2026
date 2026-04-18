from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards import (
    send_menu_with_photos, size_keyboard, toppings_keyboard,
    cart_actions_keyboard, cart_management_keyboard, confirm_clear_cart_keyboard
)
from menu_data import calculate_price
from states import OrderStates

router = Router()
user_carts = {}  # {user_id: [{"pizza": ..., "size": ..., "toppings": [...], "price": ...}, ...]}

def get_cart(user_id: int) -> list:
    if user_id not in user_carts:
        user_carts[user_id] = []
    return user_carts[user_id]

def clear_cart(user_id: int):
    user_carts[user_id] = []

@router.message(F.text == "🍕 Меню")
async def show_menu(message: Message):
    await send_menu_with_photos(message)

# Выбор пиццы
@router.callback_query(F.data.startswith("pizza_"))
async def choose_pizza(callback: CallbackQuery, state: FSMContext):
    pizza_name = callback.data.split("_")[1]
    await state.update_data(current_pizza=pizza_name, current_toppings=[])
    await callback.message.edit_text(
        f"Вы выбрали: {pizza_name}\nТеперь выберите размер:",
        reply_markup=size_keyboard(pizza_name)
    )
    await callback.answer()

# Выбор размера
@router.callback_query(F.data.startswith("size_"))
async def choose_size(callback: CallbackQuery, state: FSMContext):
    _, pizza_name, size = callback.data.split("_")
    await state.update_data(current_size=size)
    data = await state.get_data()
    toppings = data.get("current_toppings", [])
    await callback.message.edit_text(
        f"🍕 {pizza_name} ({size})\n\nДобавьте начинки (можно несколько):",
        reply_markup=toppings_keyboard(toppings)
    )
    await callback.answer()

# Переключение начинок
@router.callback_query(F.data.startswith("topping_"))
async def toggle_topping(callback: CallbackQuery, state: FSMContext):
    topping = callback.data.split("_")[1]
    data = await state.get_data()
    toppings = data.get("current_toppings", [])
    if topping in toppings:
        toppings.remove(topping)
        await callback.answer(f"❌ {topping} убрана")
    else:
        toppings.append(topping)
        await callback.answer(f"✅ {topping} добавлена")
    await state.update_data(current_toppings=toppings)
    await callback.message.edit_reply_markup(reply_markup=toppings_keyboard(toppings))

# Завершение выбора начинок → добавление позиции в корзину
@router.callback_query(F.data == "toppings_done")
async def toppings_done(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    pizza = data["current_pizza"]
    size = data["current_size"]
    toppings = data.get("current_toppings", [])
    price = calculate_price(pizza, size, toppings)

    cart = get_cart(user_id)
    cart.append({
        "pizza": pizza,
        "size": size,
        "toppings": toppings,
        "price": price
    })

    # Очищаем временные данные о текущей позиции
    await state.update_data(current_pizza=None, current_size=None, current_toppings=[])

    # Сообщение о добавлении и предложение действий
    text = f"✅ {pizza} ({size}) добавлена в корзину!\nСумма позиции: {price}₽\n\nЧто дальше?"
    await callback.message.edit_text(text, reply_markup=cart_actions_keyboard())
    await state.set_state(OrderStates.managing_cart)
    await callback.answer()