import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, Contact
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# Token va botni sozlash
TOKEN ="8825022746:AAGO5dOX9EX0rtOOMLwi6SdbJ_EBDJxAWEI" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Bot holatlari (FSM)
class OrderState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_location = State()

# Asosiy menyu tugmasi
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🛒 Buyurtma berish")]],
    resize_keyboard=True
)

# Veb-server uchun handle funksiyasi (Render o'chib qolmasligi uchun)
async def handle(request):
    return web.Response(text="Bot is running!")

# 1. /start buyrug'i
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Xush kelibsiz. Buyurtma berish uchun quyidagi tugmani bosing:", 
        reply_markup=main_keyboard
    )

# 2. "Buyurtma berish" tugmasi bosilganda telefon raqamni so'rash
@dp.message(F.text == "🛒 Buyurtma berish")
async def make_order(message: Message, state: FSMContext):
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Buyurtmani rasmiylashtirish uchun telefon raqamingizni yuboring:", reply_markup=phone_keyboard)
    await state.set_state(OrderState.waiting_for_phone)

# 3. Telefon raqamni qabul qilib, lokatsiyani so'rash
@dp.message(F.contact, OrderState.waiting_for_phone)
async def get_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    location_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Rahmat! Endi yetkazib berish manzilini aniqlash uchun lokatsiyangizni yuboring:", reply_markup=location_keyboard)
    await state.set_state(OrderState.waiting_for_location)

# 4. Lokatsiyani qabul qilib buyurtmani yakunlash
@dp.message(F.location, OrderState.waiting_for_location)
async def get_location(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = data.get("phone")
    
    await message.answer(
        f"Buyurtmangiz muvaffaqiyatli qabul qilindi! 🚀\n"
        f"Telefon raqamingiz: {phone}\n"
        f"Tez orada yetkazib beramiz. Xaridingiz uchun rahmat! 😊", 
        reply_markup=main_keyboard
    )
    await state.set_state(None)

# Render uchun web-serverni ishga tushirish funksiyasi
async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Asosiy ishga tushirish funksiyasi
async def main():
    print("Bot ishga tushdi...")
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
