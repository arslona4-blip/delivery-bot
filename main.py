import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# Token va botni sozlash (o'zingizning tokeningiz turganiga ishonch hosil qiling)
TOKEN = "8825022746:AAGO5dOX9EX0rtOOMLwi6SdbJ_EBDJxAWEI"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Holatlar (FSM)
class OrderState(StatesGroup):
    waiting_for_location = State()

# Asosiy klaviatura (misol tariqasida)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🛒 Buyurtma berish")]],
    resize_keyboard=True
)

# Veb-server uchun handle funksiyasi (Render o'chib qolmasligi uchun)
async def handle(request):
    return web.Response(text="Bot is running!")
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Xush kelibsiz. Buyurtma berish uchun quyidagi tugmani bosing:", 
        reply_markup=main_keyboard
    )
# Lokatsiyani qabul qiluvchi funksiya
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
    # Veb-server va bot polling'ni bir vaqtning o'zida ishga tushiramiz
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
