import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {
    int(admin_id.strip())
    for admin_id in os.getenv("ADMIN_IDS", "").split(",")
    if admin_id.strip().isdigit()
}
COURIER_IDS = {
    int(cid.strip())
    for cid in os.getenv("COURIER_IDS", "").split(",")
    if cid.strip().isdigit()
}
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "bot.db"))

ORDER_STATUS_LABELS = {
    "new": "🆕 Yangi",
    "accepted": "✅ Qabul qilindi",
    "in_delivery": "🚚 Yo'lda",
    "delivered": "📦 Yetkazildi",
    "cancelled": "❌ Bekor qilindi",
}

PAYMENT_STATUS_LABELS = {
    "pending": "⏳ Kutilmoqda",
    "cash": "💵 Naqd",
    "card_waiting": "💳 Karta (tekshirilmoqda)",
    "paid": "✅ To'langan",
    "rejected": "❌ Rad etildi",
}

DELIVERY_PRICE = int(os.getenv("DELIVERY_PRICE", "10000"))
MIN_ORDER_AMOUNT = int(os.getenv("MIN_ORDER_AMOUNT", "30000"))
BONUS_PERCENT = int(os.getenv("BONUS_PERCENT", "2"))
BONUS_RATE = int(os.getenv("BONUS_RATE", "100"))  # 100 so'm = 1 ball

SHOP_NAME = os.getenv("SHOP_NAME", "Do'kon")
SHOP_ADDRESS = os.getenv("SHOP_ADDRESS", "Toshkent sh.")
SHOP_PHONE = os.getenv("SHOP_PHONE", "+998 90 123 45 67")
SHOP_TELEGRAM = os.getenv("SHOP_TELEGRAM", "@support")
SHOP_HOURS = os.getenv("SHOP_HOURS", "09:00 - 22:00")

CARD_NUMBER = os.getenv("CARD_NUMBER", "").strip()
CARD_HOLDER = os.getenv("CARD_HOLDER", SHOP_NAME).strip()
PAYME_LINK = os.getenv("PAYME_LINK", "").strip()
CLICK_LINK = os.getenv("CLICK_LINK", "").strip()

DELIVERY_SLOTS = [
    "Bugun 10:00–12:00",
    "Bugun 12:00–15:00",
    "Bugun 15:00–18:00",
    "Bugun 18:00–21:00",
    "Ertaga 10:00–14:00",
    "Ertaga 14:00–18:00",
]


def online_payment_enabled() -> bool:
    return bool(PAYMENT_PROVIDER_TOKEN) and not PAYMENT_PROVIDER_TOKEN.startswith("your_")


def card_payment_enabled() -> bool:
    return bool(CARD_NUMBER) and "XXXX" not in CARD_NUMBER
