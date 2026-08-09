# Telegram Mini App sozlash

Bu qo‘llanma yetkazib berish botining Mini App (web do‘kon) ni lokal yoki serverda ochish uchun.

## 1. Botni ishga tushirish

`.env` faylida kamida `BOT_TOKEN` va `ADMIN_IDS` bo‘lsin. Mini App server avtomatik `WEBAPP_PORT` (default **8088**) da ochiladi.

```powershell
cd C:\Users\arslo\yetkazib_berish_xizmati_bot
.\.venv\Scripts\Activate.ps1
python -m bot.main
```

Tekshirish:

- Brauzer: `http://127.0.0.1:8088/`
- API: `http://127.0.0.1:8088/api/config`

## 2. Cloudflare Tunnel (HTTPS URL)

Telegram Mini App **faqat HTTPS** manzilni qabul qiladi. Lokal serverni tashqariga ochish uchun `cloudflared` ishlating.

1. [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) ni o‘rnating.
2. Bot ishlab turgan holatda yangi terminalda:

```powershell
cloudflared tunnel --url http://127.0.0.1:8088
```

3. Chiqgan URL ni nusxalang, masalan:
   `https://xxxx.trycloudflare.com`

4. `.env` ga qo‘ying:

```env
WEBAPP_PORT=8088
MINIAPP_URL=https://xxxx.trycloudflare.com
```

5. Botni qayta ishga tushiring (MINIAPP_URL o‘zgarishi uchun).

**Eslatma:** `trycloudflare.com` URL vaqtinchalik — tunnel qayta ochilsa manzil o‘zgarishi mumkin. Doimiy domen uchun Cloudflare Named Tunnel ishlating.

## 3. BotFather — Menu Button

1. [@BotFather](https://t.me/BotFather) ga kiring.
2. `/mybots` → botingiz → **Bot Settings** → **Menu Button**.
3. **Configure menu button** ni tanlang.
4. URL sifatida `MINIAPP_URL` ni yuboring (masalan `https://xxxx.trycloudflare.com`).
5. Tugma matni: `Do'kon` yoki `🛒 Do'kon`.

Shu tugma Telegram chatining pastki chapida Mini App ni ochadi.

## 4. /start dagi tugma

Agar `MINIAPP_URL` to‘ldirilgan bo‘lsa, `/start` xabarida **🛒 Do'konni ochish** WebApp tugmasi chiqadi.

Kodda `miniapp_keyboard()` ham bor — kerak joylarda chaqirish mumkin.

## 5. Lokal test (brauzer)

Telegram `initData` bo‘lmaganda buyurtma uchun:

```
http://127.0.0.1:8088/?dev_user_id=SIZNING_TELEGRAM_ID
```

`dev_user_id` faqat `initData` yaroqsiz/bo‘sh bo‘lganda ishlaydi. Productionda haqiqiy Telegram Mini App orqali oching.

## 6. Muammolar

| Muammo | Yechim |
|--------|--------|
| Mini App ochilmaydi | `MINIAPP_URL` HTTPS ekanini va tunnel ishlayotganini tekshiring |
| Rasmlar ko‘rinmaydi | Bot ishlayotganini va mahsulotda `image_file_id` borligini tekshiring |
| Buyurtma 401 | Telegram ichida oching yoki `?dev_user_id=` qo‘shing |
| Port band | `.env` da `WEBAPP_PORT` ni o‘zgartiring va tunnel URL ni yangilang |
