import sqlite3
from pathlib import Path

DB = Path("data/bot.db")
EXACT = {
    "Meva": "\U0001F34E Meva",
    "Parfyumeriya": "\U0001F484 Parfyumeriya",
    "Muzqaymoqlar": "\U0001F366 Muzqaymoqlar",
    "Pishiriqlar": "\U0001F950 Pishiriqlar",
    "Oziq-ovqat": "\U0001F35E Oziq-ovqat",
    "Ichimliklar": "\U0001F964 Ichimliklar",
    "Uy-ro'zg'or": "\U0001F3E0 Uy-ro'zg'or",
}

def has_emoji(name: str) -> bool:
    for ch in (name or "")[:4]:
        if ord(ch) >= 0x1F300:
            return True
    return False

conn = sqlite3.connect(DB)
for cat_id, name in conn.execute("SELECT id, name FROM categories"):
    n = (name or "").strip()
    if has_emoji(n):
        print("KEEP", cat_id, n.encode("unicode_escape").decode())
        continue
    new = EXACT.get(n)
    low = n.casefold()
    if not new and ("antsel" in low or "kantsel" in low or "kontsel" in low):
        new = "\u270F\uFE0F Kantselyariya"
    if new:
        conn.execute("UPDATE categories SET name=? WHERE id=?", (new, cat_id))
        print("UPDATED", cat_id, n.encode("unicode_escape").decode(), "->", new.encode("unicode_escape").decode())
    else:
        print("SKIP", cat_id, n.encode("unicode_escape").decode())
conn.commit()
print("DONE")
for cat_id, name in conn.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE"):
    print(cat_id, name.encode("unicode_escape").decode())
conn.close()
