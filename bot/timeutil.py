"""Toshkent vaqti bo'yicha sana/vaqt yordamchilari."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tashkent")

WEEKDAYS_UZ = (
    "Dushanba",
    "Seshanba",
    "Chorshanba",
    "Payshanba",
    "Juma",
    "Shanba",
    "Yakshanba",
)

# (kun: today|tomorrow, oralik)
DELIVERY_SLOT_RANGES = (
    ("today", "10:00–12:00"),
    ("today", "12:00–15:00"),
    ("today", "15:00–18:00"),
    ("today", "18:00–21:00"),
    ("tomorrow", "10:00–14:00"),
    ("tomorrow", "14:00–18:00"),
)


def now_tashkent() -> datetime:
    return datetime.now(TZ)


def format_now() -> str:
    """Masalan: 09.08.2026 · Yakshanba · 11:31"""
    dt = now_tashkent()
    return (
        f"{dt.strftime('%d.%m.%Y')} · {WEEKDAYS_UZ[dt.weekday()]} · "
        f"{dt.strftime('%H:%M')}"
    )


def format_now_html() -> str:
    """Sana/vaqt — qalin + tagchiziq (e'tiborni tortadi)."""
    return f"📅 <b><u>{format_now()}</u></b>"


def format_dt(value: str | datetime | None) -> str:
    """ISO yoki datetime ni o'qiladigan ko'rinishga o'tkazadi."""
    if value is None or value == "":
        return "—"
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except ValueError:
            return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    else:
        dt = dt.astimezone(TZ)
    return (
        f"{dt.strftime('%d.%m.%Y')} · {WEEKDAYS_UZ[dt.weekday()]} · "
        f"{dt.strftime('%H:%M')}"
    )


def format_dt_html(value: str | datetime | None) -> str:
    return f"📅 <b><u>{format_dt(value)}</u></b>"


def money_html(amount: int, with_emoji: bool = True) -> str:
    """Narx — yaltiroq ko'rinish (qalin + tagchiziq)."""
    core = f"<b><u>{int(amount):,}</u></b> so'm"
    return f"💰 {core}" if with_emoji else core


def get_delivery_slots() -> list[str]:
    """Bugun/ertaga sanasi bilan yetkazish vaqtlari."""
    now = now_tashkent()
    today = now.strftime("%d.%m.%Y")
    tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")
    today_wd = WEEKDAYS_UZ[now.weekday()]
    tomorrow_wd = WEEKDAYS_UZ[(now + timedelta(days=1)).weekday()]

    slots: list[str] = []
    for day_key, rng in DELIVERY_SLOT_RANGES:
        if day_key == "today":
            slots.append(f"Bugun ({today}, {today_wd}) {rng}")
        else:
            slots.append(f"Ertaga ({tomorrow}, {tomorrow_wd}) {rng}")
    return slots
