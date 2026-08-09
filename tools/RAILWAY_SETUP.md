# Railway — 24/7 bot

## Muhim
- Railway ishlaganda kompyuterdagi botni OCHIRING (409 Conflict).
- Startup / watchdog ni ham ochiring.
- SQLite uchun Volume: mount path /data

## Qadamlar
1. Kod GitHubga push
2. https://railway.app — GitHub bilan kiring
3. New Project → Deploy from GitHub → yetkazib-berish-bot
4. Variables: BOT_TOKEN, ADMIN_IDS, DATABASE_PATH=/data/bot.db, SHOP_*, CARD_*, va hokazo (.env dan)
5. Settings → Volumes → Add → /data
6. Deploy → Logs: Application started
7. Telegramda botni tekshiring

Lokal bot va Railway BIRGA ishlamasin.
