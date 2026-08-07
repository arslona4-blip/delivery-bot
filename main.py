import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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

import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types


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
)

# API Token
TOKEN = "8825022746:AAFv0Z4Jb5lzkPru78DgM5k0ME9fXyi5wBg"
ADMIN_ID = 1490138644
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Buyurtma berish bosqichlari (FSM)
class OrderState(StatesGroup):
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


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\n"
        f"Yetkazib berish xizmatimiz botiga xush kelibsiz.",
        reply_markup=main_keyboard,
    )


@dp.message(F.text == "🛒 Buyurtma berish")
async def start_order(message: Message, state: FSMContext):
    phone_button = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📞 Telefon raqamni yuborish", request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "Buyurtmani rasmiylashtirish uchun telefon raqamingizni yuboring:",
        reply_markup=phone_button,
    )
    await state.set_state(OrderState.waiting_for_phone)


@dp.message(OrderState.waiting_for_phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)

    location_button = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📍 Joylashuvni (GPS) yuborish",
                    request_location=True,
                )
            ]
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "Rahmat! Endi yetkazib berish manzilini (lokatsiyangizni) yuboring:",
        reply_markup=location_button,
    )
    await state.set_state(OrderState.waiting_for_location)


@dp.message(OrderState.waiting_for_location, F.location)
async def process_location(message: Message, state: FSMContext):
    user_data = await state.get_data()
    phone = user_data.get("phone")
    lat = message.location.latitude
    lon = message.location.longitude

    await message.answer(
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"📞 Telefon: {phone}\n"
        f"📍 Koordinatalar: {lat}, {lon}\n\n"
        f"Tez orada operatorimiz siz bilan bog'lanadi.",
        reply_markup=main_keyboard,
    )
    await state.clear()


@dp.message(F.text == "📞 Biz bilan aloqa")
async def contact_handler(message: Message):
    await message.answer(
        "Murojaat uchun:\n📞 Tel: +998 90 123 45 67\n💬 Telegram: @admin"
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)


# Lokatsiya qabul qilinganda Adminga buyurtma yuborish
@dp.message(OrderState.waiting_for_location, F.location)
async def handle_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    
    user_data = await state.get_data()
    phone = user_data.get("phone", "Ko'rsatilmadi")
    
    # Mijozga tasdiq xabari
    await message.answer("✅ Buyurtmangiz qabul qilindi!", reply_markup=main_keyboard)
    
    # Adminga buyurtma yuborish
    admin_text = (
        f"📥 **YANGI BUYURTMA!**\n\n"
        f"👤 **Mijoz:** {message.from_user.full_name}\n"
        f"📞 **Tel:** {phone}\n"
        f"📍 **Lokatsiya:** https://maps.google.com/?q={lat},{lon}"
    )
    
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
    await bot.send_location(chat_id=ADMIN_ID, latitude=lat, longitude=lon)
    
    await state.clear()

if __name__ == "__main__":
    asyncio.run(main())
