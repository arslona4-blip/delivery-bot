import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Render health check server ---
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

# --- Telegram Bot ---
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    CallbackQuery
)

TOKEN = "8825022746:AAHcx_6qCFAiKvjW04VQFNpAfGYYIQgd0Wc"
ADMIN_ID = 1490138644

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM states
class OrderState(StatesGroup):
    choosing_products = State()
    waiting_for_phone = State()
    waiting_for_location = State()

# Asosiy menyu
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🛒 Buyurtma berish"),
            KeyboardButton(text="📦 Mening buyurtmalarim"),
        ],
        [
            KeyboardButton(text="📞 Biz bilan aloqa"),
            KeyboardButton(text="ℹ️ Ma'lumot"),
        ],
    ],
    resize_keyboard=True,
)

# Mahsulotlar menyusi
def products_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Moxito 0.5L - 12000 so'm")],
            [KeyboardButton(text="🛒 Savatchani ko'rish / Rasmiylashtirish")],
            [KeyboardButton(text="🔙 Asosiy menyu")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\n"
        f"Yetkazib berish xizmatimiz botiga xush kelibsiz.",
        reply_markup=main_keyboard,
    )

@dp.message(F.text == "🛒 Buyurtma berish")
async def start_order(message: Message, state: FSMContext):
    await state.update_data(cart={})
    await message.answer(
        "Menudan mahsulotlarni tanlang:",
        reply_markup=products_keyboard()
    )
    await state.set_state(OrderState.choosing_products)

@dp.message(OrderState.choosing_products, F.text.contains("Moxito"))
async def add_moxito_to_cart(message: Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    
    cart["moxito"] = cart.get("moxito", 0) + 1
    await state.update_data(cart=cart)
    
    await message.answer("Moxito 0.5L savatchaga qo'shildi! Yana mahsulot tanlashingiz mumkin yoki savatchani ko'ring.")

@dp.message(OrderState.choosing_products, F.text == "🛒 Savatchani ko'rish / Rasmiylashtirish")
async def show_cart(message: Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    
    if not cart:
        await message.answer("Savatchangiz bo'sh!")
        return
        
    text = "🛒 **Sizning savatchangiz:**\n\n"
    total = 0
    for code, count in cart.items():
        if code == "moxito":
            name = "Moxito 0.5L"
            price = 12000
            total += price * count
            text += f"• {name} x {count} = {price * count} so'm\n"
            
    text += f"\n**Jami:** {total} so'm"
    
    phone_button = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]
        ],
        resize_keyboard=True
    )
    await message.answer(text, reply_markup=phone_button)
    await state.set_state(OrderState.waiting_for_phone)

@dp.message(OrderState.waiting_for_phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    location_button = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Joylashuvni (GPS) yuborish", request_location=True)]
        ],
        resize_keyboard=True
    )
    await message.answer("Rahmat! Endi yetkazib berish manzilini (lokatsiyangizni) yuboring:", reply_markup=location_button)
    await state.set_state(OrderState.waiting_for_location)

@dp.message(OrderState.waiting_for_location, F.location)
async def process_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    data = await state.get_data()
    phone = data.get("phone")
    
    await message.answer(
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"📞 Telefon: {phone}\n"
        f"📍 Koordinatalar: {lat}, {lon}\n\n"
        f"Tez orada operatorimiz siz bilan bog'lanadi.",
        reply_markup=main_keyboard
    )
    await state.clear()

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
