from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import is_admin, get_all_orders, update_order_status, get_order_by_id
from keyboards import admin_panel_keyboard, order_status_keyboard
from states import AdminStates

router = Router()

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели администратора.")
        return
    await show_admin_panel(message)

async def show_admin_panel(message: Message):
    text = (
        "🔧 Панель администратора\n\n"
        "Выберите действие или введите команду:\n"
        "/order <номер> — изменить статус заказа\n"
        "/close_admin — выйти из режима администратора"
    )
    await message.answer(text, reply_markup=admin_panel_keyboard())

@router.message(Command("close_admin"))
async def cmd_close_admin(message: Message):
    await message.answer("👋 Вы вышли из режима администратора. Для входа используйте /admin")

@router.callback_query(F.data == "admin_logout")
async def logout_admin(callback: CallbackQuery):
    await callback.message.edit_text("👋 Вы вышли из панели администратора.")
    await callback.answer()

@router.callback_query(F.data == "admin_find_order")
async def prompt_find_order(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔍 Введите команду:\n"
        "/order <номер_заказа>\n\n"
        "Например: /order 42"
    )
    await callback.answer()

@router.message(Command("order"))
async def cmd_order(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("📝 Использование: /order <номер_заказа>")
        return

    try:
        order_id = int(args[1])
    except ValueError:
        await message.answer("❌ Номер заказа должен быть числом.")
        return

    order = get_order_by_id(order_id)
    if not order:
        await message.answer(f"❌ Заказ №{order_id} не найден.")
        return

    await state.update_data(current_order_id=order_id)
    await show_order_status_editor(message, order)

async def show_order_status_editor(message: Message, order: dict):
    text = (
        f"📦 Заказ №{order['order_id']}\n"
        f"👤 Клиент ID: {order['user_id']}\n"
        f"🍕 {order['items']}\n"
        f"💰 Сумма: {order['total_price']}₽\n"
        f"📍 Адрес: {order['address']}\n"
        f"💬 Комментарий: {order['comment'] or 'нет'}\n"
        f"💳 Оплата: {order['payment_method']}\n"
        f"📌 Текущий статус: {order['status']}\n\n"
        f"Выберите новый статус:"
    )
    await message.answer(text, reply_markup=order_status_keyboard(order['order_id']))

@router.callback_query(F.data.startswith("admin_orders_"))
async def show_filtered_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return

    status = callback.data.split("_")[2]
    if status == "all":
        orders = get_all_orders()
        title = "Все заказы"
    else:
        orders = get_all_orders(status_filter=status)
        title = f"Заказы со статусом '{status}'"

    if not orders:
        await callback.message.edit_text(f"📭 {title}: нет заказов.")
        await callback.answer()
        return

    text = f"📋 {title}:\n\n"
    for o in orders[:10]:
        text += f"№{o['order_id']} – {o['items']} – {o['total_price']}₽ – {o['status']}\n"
    text += "\nЧтобы изменить статус конкретного заказа, используйте /order <номер>"

    await callback.message.edit_text(text)
    await callback.answer()

@router.callback_query(F.data.startswith("setstatus_"))
async def change_status(callback: CallbackQuery, bot: Bot, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return

    _, order_id, new_status = callback.data.split("_")
    order_id = int(order_id)

    update_order_status(order_id, new_status)
    order = get_order_by_id(order_id)

    await bot.send_message(
        order['user_id'],
        f"🔄 Статус вашего заказа №{order_id} изменён: {new_status}"
    )

    await callback.message.edit_text(
        f"✅ Статус заказа №{order_id} обновлён на '{new_status}'"
    )
    await callback.answer()
    await state.clear()