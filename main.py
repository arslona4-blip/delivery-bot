import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8825022746:AAGO5dOX9EX0rtOOMLwi6SdbJ_EBDJxAWEI"
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
@dp.message(F.text == "📦 Mening buyurtmalarim")
async def my_orders_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("last_order", {})
    phone = data.get("phone", "Kiritilmagan")
    
    if not cart:
        await message.answer("Sizda hozircha faol buyurtmalar yo'q. 🛒 Buyurtma berish tugmasini bosib xarid qilishingiz mumkin!")
        return

    text = "📦 **Sizning oxirgi buyurtmangiz:**\n\n"
    
    for code, count in cart.items():
        text += f"• {code} x {count}\n"
        
    text += f"\n📞 **Telefon raqamingiz:** {phone}"
    await message.answer(text, parse_mode="Markdown")
PRODUCTS = {
    "Cola 0.5L - 8000 so'm": {"code": "cola", "name": "Cola 0.5L", "price": 7000},
    "Cola 1L-12000 so'm":   {"code": "cola", "name": "Cola 1L", "price": 12000},
    "Cola 1,5L-15000 so'm":   {"code": "cola", "name": "Cola 1L", "price": 15000},
    "Cola 2L-20000 so'm":   {"code": "cola", "name": "Cola 2L", "price": 20000},
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
    # PRODUCTS dagi nomlarni olib bittadan tugma yasaydi
    buttons = [[KeyboardButton(text=name)] for name in PRODUCTS.keys()]
    
    # Oxiriga boshqaruv tugmalarini qo'shamiz
    buttons.append([KeyboardButton(text="🛒 Savatchani ko'rish / Rasmiylashtirish")])
    buttons.append([KeyboardButton(text="🔙 Asosiy menyu")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

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
@dp.message(F.text == "ℹ️ Ma'lumot")
async def info_handler(message: Message):
    text = (
        "ℹ️ **Yetkazib berish xizmati haqida umumiy ma'lumot:**\n\n"
        "🕒 **Ish vaqti:** Har kuni 09:00 dan 22:00 gacha.\n"
        "🚀 **Yetkazib berish vaqti:** O'rtacha 30-45 daqiqa ichida.\n"
        "💰 **To'lov turi:** Naqd pul yoki karta orqali."
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📞 Biz bilan aloqa")
async def contact_us_handler(message: Message):
    text = (
        "📞 **Biz bilan bog'lanish uchun ma'lumotlar:**\n\n"
        "📱 **Telefon raqam:** +998 33 104 76 76\n"
        "📍 **Manzil:** Toshkent viloyati, Bekobod tumani"
    )
    await message.answer(text, parse_mode="Markdown")
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
@dp.message(F.contact, OrderState.waiting_for_phone)
async def get_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    location_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True
    )
    await message.answer("Rahmat! Endi yetkazib berish manzilini aniqlash uchun quyidagi tugmani bosib **lokatsiyangizni yuboring**:", reply_markup=location_keyboard)
    await state.set_state(OrderState.waiting_for_location)

 @dp.message(F.location, OrderState.waiting_for_location)
async def get_location(message: Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    
    await state.update_data(last_order=cart, cart={})
    
    await message.answer(
        "Buyurtmangiz muvaffaqiyatli qabul qilindi! Tez orada yetkazib beramiz. Xaridingiz uchun rahmat! 😊", 
        reply_markup=main_keyboard
    )
    await state.set_state(None)
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    print("Bot ishga tushdi...")
    await web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
