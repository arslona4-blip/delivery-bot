import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)

# Render Health Check Server
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# Bot Sozlamalari
TOKEN = "8825022746:AAHcx_6qCFAiKvjW04VQFNpAfGYYIQgd0Wc"
ADMIN_ID = 1490138644

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Mahsulotlar bazasi
PRODUCTS = {
    "prod_1": {"name": "Lavash standart", "price": 30000},
    "prod_2": {"name": "Gamburger", "price": 25000},
    "prod_3": {"name": "Pissa Pepperoni", "price": 65000},
    "prod_4": {"name": "Moxito 0.5L", "price": 12000}
}

# FSM Holatlari
class OrderState(StatesGroup):
    choosing_products = State()
    waiting_for_phone = State()
    waiting_for_location = State()

# Klaviaturalar
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍔 Buyurtma berish")],
            [KeyboardButton(text="📞 Biz bilan aloqa"), KeyboardButton(text="ℹ️ Ma'lumot")]
        ],
        resize_keyboard=True
    )

def products_keyboard():
    builder = []
    for code, item in PRODUCTS.items():
        builder.append([InlineKeyboardButton(text=f"{item['name']} - {item['price']} so'm", callback_data=f"add_{code}")])
    builder.append([InlineKeyboardButton(text="🛒 Savatchani ko'rish / Rasmiylashtirish", callback_data="view_cart")])
    return InlineKeyboardMarkup(inline_keyboard=builder)

# Start komandasi
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\nYetkazib berish xizmatimiz botiga xush kelibsiz.",
        reply_markup=main_keyboard()
    )

# Buyurtma berish tugmasi
@dp.message(F.text == "🍔 Buyurtma berish")
async def start_order(message: types.Message, state: FSMContext):
    await state.set_state(OrderState.choosing_products)
    await state.update_data(cart={})
    await message.answer("Menyudan mahsulotlarni tanlang:", reply_markup=products_keyboard())

# Mahsulot qo'shish callback (har qanday holatda ham savatchaga yozadi)
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: CallbackQuery, state: FSMContext):
    prod_code = callback.data.split("_")[1]
    
    # Agar holat o'rnatilmagan bo'lsa, avtomatik ochamiz
    data = await state.get_data()
    cart = data.get("cart", {})

    cart[prod_code] = cart.get(prod_code, 0) + 1
    await state.update_data(cart=cart)
    await state.set_state(OrderState.choosing_products)

    prod_name = PRODUCTS[prod_code]["name"]
    await callback.answer(f"{prod_name} savatchaga qo'shildi!")

# Savatchani ko'rish
@dp.callback_query(F.data == "view_cart")
async def view_cart(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await callback.answer("Savatchangiz bo'sh! Avval mahsulot tanlang.", show_alert=True)
        return

    text = "🛒 **Sizning savatchangiz:**\n\n"
    total_price = 0
    for code, qty in cart.items():
        item = PRODUCTS[code]
        sum_price = item["price"] * qty
        total_price += sum_price
        text += f"• {item['name']} x {qty} = {sum_price} so'm\n"

    text += f"\n**Jami:** {total_price} so'm\n\nDavom etish uchun telefon raqamingizni yuboring:"
    
    phone_btn = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await state.set_state(OrderState.waiting_for_phone)
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=phone_btn)
    await callback.answer()

# Telefon raqam qabul qilish
@dp.message(OrderState.waiting_for_phone, F.contact)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(OrderState.waiting_for_location)

    loc_btn = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Rahmat! Endi yetkazib berish manzilini (lokatsiyangizni) yuboring:", reply_markup=loc_btn)

# Lokatsiya va yakuniy buyurtma
@dp.message(OrderState.waiting_for_location, F.location)
async def process_location(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    cart = user_data.get("cart", {})
    phone = user_data.get("phone")
    lat = message.location.latitude
    lon = message.location.longitude

    order_items = ""
    total_price = 0
    for code, qty in cart.items():
        item = PRODUCTS[code]
        sum_price = item["price"] * qty
        total_price += sum_price
        order_items += f"• {item['name']} x {qty} = {sum_price} so'm\n"

    admin_text = (
        f"📥 **Yangi buyurtma!**\n\n"
        f"👤 **Mijoz:** {message.from_user.full_name}\n"
        f"📞 **Telefon:** {phone}\n\n"
        f"📦 **Tarkibi:**\n{order_items}\n"
        f"💰 **Jami summasi:** {total_price} so'm"
    )
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
    await bot.send_location(ADMIN_ID, latitude=lat, longitude=lon)

    await message.answer("✅ Buyurtmangiz qabul qilindi! Tez orada operatorimiz bog'lanadi.", reply_markup=main_keyboard())
    await state.clear()

# Aloqa va Ma'lumot
@dp.message(F.text == "📞 Biz bilan aloqa")
async def contact_handler(message: types.Message):
    await message.answer("Murojaat uchun:\n📞 Tel: +998 90 123 45 67\n💬 Telegram: @admin")

@dp.message(F.text == "ℹ️ Ma'lumot")
async def info_handler(message: types.Message):
    await message.answer("Bizning xizmat 24/7 rejimida ishlaydi. Tez va sifatli yetkazib beramiz!")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
