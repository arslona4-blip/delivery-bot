import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# Token va botni sozlash
TOKEN = "8825022746:AAGO5dOX9EX0rtOOMLwi6SdbJ_EBDJxAWEI"
bot = Bot(token=TOKEN)
dp = Dispatcher()

class OrderState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_location = State()

# YANGI MENYU TUGMALARI (Buni fayldagi eski main_keyboard o'rniga qo'ying)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Mahsulotlar"), KeyboardButton(text="📦 Mening buyurtmalarim")],
        [KeyboardButton(text="🛒 Buyurtma berish")],
        [KeyboardButton(text="ℹ️ Ma'lumot"), KeyboardButton(text="📞 Biz bilan aloqa")]
    ],
    resize_keyboard=True
)

async def handle(request):
    return web.Response(text="Bot is running!")

# /start buyrug'i
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Assalomu alaykum! Xush kelibsiz.", reply_markup=main_keyboard)

# YANGI FUNKSIYALAR (Bularni kodning oxiriga, main() funksiyasidan tepaga qo'shing)
@dp.message(F.text == "🛍 Mahsulotlar")
async def show_products(message: Message):
    await message.answer("Mana bizning mahsulotlarimiz:\n1. Burger\n2. Lavash\n3. Pizza", reply_markup=main_keyboard)

@dp.message(F.text == "📦 Mening buyurtmalarim")
async def show_my_orders(message: Message):
    await message.answer("Sizda hozircha faol buyurtmalar yo'q.", reply_markup=main_keyboard)

@dp.message(F.text == "ℹ️ Ma'lumot")
async def show_info(message: Message):
    await message.answer("Ushbu bot yetkazib berish xizmati uchun.", reply_markup=main_keyboard)

@dp.message(F.text == "📞 Biz bilan aloqa")
async def contact_us(message: Message):
    await message.answer("Murojaat uchun: @admin_username", reply_markup=main_keyboard)

# Buyurtma berish funksiyasi
@dp.message(F.text == "🛒 Buyurtma berish")
async def make_order(message: Message, state: FSMContext):
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard)
    await state.set_state(OrderState.waiting_for_phone)
# ... (oldingi buyurtma berish kodi tugagan joy)

# Telefon raqamni qabul qilib oluvchi funksiya
@dp.message(OrderState.waiting_for_phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    phone_number = message.contact.phone_number
    await state.update_data(phone=phone_number)
    
    await message.answer(
        "Rahmat! Endi mahsulotlarimiz bilan tanishing:", 
        reply_markup=main_keyboard
    )
    await state.clear()

# ... (pastda web_server va main funksiyalar davom etaveradi)
# ... (qolgan telefon va lokatsiya funksiyalari o'z o'rnida qoladi) ...

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
