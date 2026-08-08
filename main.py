import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN", "SIZNING_TOKENINGIZ")

bot = Bot(token=TOKEN)
dp = Dispatcher()

class OrderState(StatesGroup):
    choosing_products = State()
    waiting_for_phone = State()
    waiting_for_location = State()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛒 Buyurtma berish"), KeyboardButton(text="📦 Mening buyurtmalarim")],
        [KeyboardButton(text="📞 Biz bilan aloqa"), KeyboardButton(text="ℹ️ Ma'lumot")],
    ],
    resize_keyboard=True,
)

PRODUCTS = {
    "Cola 0.5L - 8000 so'm": {"code": "cola", "name": "Cola 0.5L", "price": 8000},
    "Fanta 0.5L - 8000 so'm": {"code": "fanta", "name": "Fanta 0.5L", "price": 8000},
    "Pepsi 0.5L - 8000 so'm": {"code": "pepsi", "name": "Pepsi 0.5L", "price": 8000},
    "Moxito 0.5L - 12000 so'm": {"code": "moxito", "name": "Moxito 0.5L", "price": 12000},
    "Pishiriq - 15000 so'm": {"code": "pishiriq", "name": "Pishiriq", "price": 15000},
    "Muzqaymoq - 6000 so'm": {"code": "muzqaymoq", "name": "Muzqaymoq", "price": 6000},
    "Olma (1 kg) - 10000 so'm": {"code": "olma", "name": "Olma (1 kg)", "price": 10000},
    "Shaftoli (1 kg) - 18000 so'm": {"code": "shaftoli", "name": "Shaftoli (1 kg)", "price": 18000},
    "Shakar (1 kg) - 14000 so'm": {"code": "shakar", "name": "Shakar (1 kg)", "price": 14000},
}

def products_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Cola 0.5L - 8000 so'm"), KeyboardButton(text="Fanta 0.5L - 8000 so'm")],
            [KeyboardButton(text="Pepsi 0.5L - 8000 so'm"), KeyboardButton(text="Moxito 0.5L - 12000 so'm")],
            [KeyboardButton(text="Pishiriq - 15000 so'm"), KeyboardButton(text="Muzqaymoq - 6000 so'm")],
            [KeyboardButton(text="Olma (1 kg) - 10000 so'm"), KeyboardButton(text="Shaftoli (1 kg) - 18000 so'm")],
            [KeyboardButton(text="Shakar (1 kg) - 14000 so'm")],
            [KeyboardButton(text="🛒 Savatchani ko'rish / Rasmiylashtirish")],
            [KeyboardButton(text="🔙 Asosiy menyu")]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(f"Assalomu alaykum, {message.from_user.first_name}!\nBotimizga xush kelibsiz.", reply_markup=main_keyboard)

@dp.message(F.text == "🛒 Buyurtma berish")
async def start_order(message: Message, state: FSMContext):
    await state.update_data(cart={})
    await message.answer("Menudan mahsulotlarni tanlang:", reply_markup=products_keyboard())
    await state.set_state(OrderState.choosing_products)

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_keyboard)

@dp.message(OrderState.choosing_products, F.text.in_(PRODUCTS.keys()))
async def add_product_to_cart(message: Message, state: FSMContext):
    product = PRODUCTS[message.text]
    data = await state.get_data()
    cart = data.get("cart", {})
    code = product["code"]
    cart[code] = cart.get(code, 0) + 1
    await state.update_data(cart=cart)
    await message.answer(f"✅ {product['name']} savatchaga qo'shildi!")

@dp.message(OrderState.choosing_products, F.text == "🛒 Savatchani ko'rish / Rasmiylashtirish")
async def show_cart(message: Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    if not cart:
        await message.answer("Savatchangiz bo'sh!")
        return
    text = "🛒 **Sizning savatchangiz:**\n\n"
    total = 0
    price_map = {p["code"]: p for p in PRODUCTS.values()}
    for code, count in cart.items():
        if code in price_map:
            item = price_map[code]
            cost = item["price"] * count
            total += cost
            text += f"• {item['name']} x {count} = {cost} so'm\n"
    text += f"\n**Jami:** {total} so'm"
    phone_button = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True
    )
    await message.answer(text, reply_markup=phone_button)
    await state.set_state(OrderState.waiting_for_phone)

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
