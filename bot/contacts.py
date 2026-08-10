"""Admin: kontaktlar va qarzdorlik."""

from __future__ import annotations

from enum import IntEnum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import ADMIN_IDS
from bot.database import (
    add_debt_entry,
    create_contact,
    debt_totals,
    get_contact,
    get_contact_balance,
    list_contacts,
    list_debt_ledger,
    mark_order_as_debt,
)
from bot.keyboards import admin_menu_keyboard, cancel_keyboard, main_menu_keyboard
from bot.timeutil import format_now_html, money_html


class ContactState(IntEnum):
    NAME = 1
    PHONE = 2
    NOTE = 3
    DEBT_AMOUNT = 4
    PAY_AMOUNT = 5


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def menu_kb(user_id: int):
    return main_menu_keyboard(is_admin(user_id), is_admin(user_id))


def contacts_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📒 Qarzdorlar", callback_data="contact:debtors"
                ),
                InlineKeyboardButton(
                    "👥 Hammasi", callback_data="contact:list"
                ),
            ],
            [
                InlineKeyboardButton(
                    "➕ Yangi kontakt", callback_data="contact:add"
                )
            ],
            [InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu")],
        ]
    )


def contact_list_keyboard(
    contacts: list[dict], *, debtors: bool = False
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for c in contacts[:25]:
        bal = int(c.get("balance") or 0)
        mark = f" · {bal:,}" if bal else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{c['name']}{mark}",
                    callback_data=f"contact:view:{c['id']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("➕ Yangi", callback_data="contact:add"),
            InlineKeyboardButton(
                "📒 Qarz" if not debtors else "👥 Hammasi",
                callback_data="contact:debtors" if not debtors else "contact:list",
            ),
        ]
    )
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="contact:home")])
    return InlineKeyboardMarkup(rows)


def contact_card_keyboard(contact_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Qarz", callback_data=f"contact:debt:{contact_id}"
                ),
                InlineKeyboardButton(
                    "💵 To'lov", callback_data=f"contact:pay:{contact_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📜 Tarix", callback_data=f"contact:hist:{contact_id}"
                )
            ],
            [InlineKeyboardButton("⬅️ Ro'yxat", callback_data="contact:list")],
        ]
    )


def _format_contact_card(contact, balance: int) -> str:
    phone = contact["phone"] or "—"
    note = contact["note"] or "—"
    return (
        f"👤 <b>{contact['name']}</b>\n"
        f"📞 {phone}\n"
        f"📝 {note}\n"
        f"💳 Qarz: <b>{money_html(balance)}</b>\n"
        f"{format_now_html()}"
    )


async def contacts_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
    if not is_admin((query.from_user if query else update.effective_user).id):
        return
    totals = debt_totals()
    text = (
        f"👥 <b>Kontaktlar / Qarzdorlik</b>\n"
        f"{format_now_html()}\n\n"
        f"📒 Ochiq qarz: <b>{money_html(totals['open'])}</b>\n"
        f"➕ Jami yozilgan: {money_html(totals['debts'])}\n"
        f"💵 Jami to'langan: {money_html(totals['payments'])}"
    )
    markup = contacts_home_keyboard()
    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Ruxsat yo'q.")
        return ConversationHandler.END

    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "home":
        await contacts_home(update, context)
        return ConversationHandler.END

    if action in {"list", "debtors"}:
        debtors = action == "debtors"
        contacts = list_contacts(debtors_only=debtors)
        title = "📒 Qarzdorlar" if debtors else "👥 Kontaktlar"
        if not contacts:
            text = f"{title}\n\nHali yo'q."
        else:
            lines = [f"<b>{title}</b> ({len(contacts)})\n"]
            for c in contacts[:20]:
                bal = int(c.get("balance") or 0)
                lines.append(
                    f"• {c['name']} — <b>{money_html(bal)}</b>"
                    if bal
                    else f"• {c['name']}"
                )
            text = "\n".join(lines)
        await query.edit_message_text(
            text,
            reply_markup=contact_list_keyboard(contacts, debtors=debtors),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if action == "add":
        context.user_data["contact_draft"] = {}
        await query.edit_message_text("➕ Yangi kontakt")
        await query.message.reply_text(
            "Ism-familiyani yozing:", reply_markup=cancel_keyboard()
        )
        return ContactState.NAME

    if action == "view" and len(parts) > 2:
        cid = int(parts[2])
        contact = get_contact(cid)
        if not contact:
            await query.answer("Topilmadi", show_alert=True)
            return ConversationHandler.END
        bal = get_contact_balance(cid)
        await query.edit_message_text(
            _format_contact_card(contact, bal),
            reply_markup=contact_card_keyboard(cid),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if action == "hist" and len(parts) > 2:
        cid = int(parts[2])
        contact = get_contact(cid)
        if not contact:
            return ConversationHandler.END
        entries = list_debt_ledger(cid, 15)
        lines = [f"📜 <b>{contact['name']}</b> tarixi\n"]
        if not entries:
            lines.append("Hali yozuv yo'q.")
        for e in entries:
            sign = "➕" if e["kind"] == "debt" else "💵"
            label = "Qarz" if e["kind"] == "debt" else "To'lov"
            ord_bit = f" · #{e['order_id']}" if e["order_id"] else ""
            note = f" — {e['note']}" if e["note"] else ""
            lines.append(
                f"{sign} {label}: {int(e['amount']):,} so'm{ord_bit}{note}"
            )
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=contact_card_keyboard(cid),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if action == "debt" and len(parts) > 2:
        context.user_data["contact_ledger"] = {
            "id": int(parts[2]),
            "kind": "debt",
        }
        await query.message.reply_text(
            "Qarz summasini yozing (so'm):", reply_markup=cancel_keyboard()
        )
        return ContactState.DEBT_AMOUNT

    if action == "pay" and len(parts) > 2:
        context.user_data["contact_ledger"] = {
            "id": int(parts[2]),
            "kind": "payment",
        }
        await query.message.reply_text(
            "To'lov summasini yozing (so'm):", reply_markup=cancel_keyboard()
        )
        return ContactState.PAY_AMOUNT

    return ConversationHandler.END


async def contact_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_contact(update, context)
    if not text:
        await update.message.reply_text("Ism bo'sh bo'lmasin.")
        return ContactState.NAME
    context.user_data.setdefault("contact_draft", {})["name"] = text
    await update.message.reply_text(
        "Telefon raqamini yozing (yoki «-»):", reply_markup=cancel_keyboard()
    )
    return ContactState.PHONE


async def contact_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_contact(update, context)
    phone = None if text in {"-", "yo'q", "yoq", "skip"} else text
    context.user_data.setdefault("contact_draft", {})["phone"] = phone
    await update.message.reply_text(
        "Izoh yozing (yoki «-»):", reply_markup=cancel_keyboard()
    )
    return ContactState.NOTE


async def contact_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_contact(update, context)
    draft = context.user_data.get("contact_draft") or {}
    note = "" if text in {"-", "yo'q", "yoq", "skip"} else text
    cid = create_contact(
        draft.get("name") or "Nomsiz",
        phone=draft.get("phone"),
        note=note,
    )
    context.user_data.pop("contact_draft", None)
    bal = get_contact_balance(cid)
    contact = get_contact(cid)
    await update.message.reply_text(
        f"✅ Kontakt qo'shildi\n\n{_format_contact_card(contact, bal)}",
        parse_mode="HTML",
        reply_markup=contact_card_keyboard(cid),
    )
    await update.message.reply_text(
        "Admin menyu:", reply_markup=menu_kb(update.effective_user.id)
    )
    return ConversationHandler.END


async def contact_ledger_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip().replace(" ", "").replace(",", "")
    if text == "❌ Bekor qilish" or "bekor" in text.casefold():
        return await cancel_contact(update, context)
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        await update.message.reply_text("Faqat son yozing, masalan: 50000")
        data = context.user_data.get("contact_ledger") or {}
        return (
            ContactState.PAY_AMOUNT
            if data.get("kind") == "payment"
            else ContactState.DEBT_AMOUNT
        )
    amount = int(digits)
    data = context.user_data.get("contact_ledger") or {}
    cid = data.get("id")
    kind = data.get("kind") or "debt"
    if not cid:
        await update.message.reply_text("Kontakt topilmadi. Qaytadan boshlang.")
        return ConversationHandler.END
    try:
        add_debt_entry(
            int(cid),
            amount,
            kind=kind,
            note="",
            created_by=update.effective_user.id,
        )
    except ValueError as exc:
        await update.message.reply_text(f"❌ {exc}")
        return (
            ContactState.PAY_AMOUNT
            if kind == "payment"
            else ContactState.DEBT_AMOUNT
        )
    context.user_data.pop("contact_ledger", None)
    contact = get_contact(int(cid))
    bal = get_contact_balance(int(cid))
    label = "Qarz yozildi" if kind == "debt" else "To'lov qabul qilindi"
    await update.message.reply_text(
        f"✅ {label}: {amount:,} so'm\n\n{_format_contact_card(contact, bal)}",
        parse_mode="HTML",
        reply_markup=contact_card_keyboard(int(cid)),
    )
    await update.message.reply_text(
        "Menyu:", reply_markup=menu_kb(update.effective_user.id)
    )
    return ConversationHandler.END


async def cancel_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("contact_draft", None)
    context.user_data.pop("contact_ledger", None)
    await update.message.reply_text(
        "Bekor qilindi.", reply_markup=menu_kb(update.effective_user.id)
    )
    return ConversationHandler.END


async def admin_mark_order_debt(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Admin: buyurtmani qarzga yozish (callback pay_debt:ID yoki admin_debt:ID)."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Ruxsat yo'q.")
        return
    order_id = int((query.data or "").split(":")[-1])
    try:
        cid, bal = mark_order_as_debt(
            order_id, created_by=query.from_user.id
        )
    except ValueError as exc:
        await query.answer(str(exc), show_alert=True)
        return
    contact = get_contact(cid)
    await query.edit_message_text(
        f"📒 Buyurtma #{order_id} qarzga yozildi.\n"
        f"Kontakt: {contact['name'] if contact else cid}\n"
        f"Jami qarz: {bal:,} so'm",
        reply_markup=contact_card_keyboard(cid),
    )


def build_contact_conversations() -> list:
    return [
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    contact_callback,
                    pattern=r"^contact:(add|debt:\d+|pay:\d+)$",
                )
            ],
            states={
                ContactState.NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, contact_name)
                ],
                ContactState.PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, contact_phone)
                ],
                ContactState.NOTE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, contact_note)
                ],
                ContactState.DEBT_AMOUNT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, contact_ledger_amount
                    )
                ],
                ContactState.PAY_AMOUNT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, contact_ledger_amount
                    )
                ],
            },
            fallbacks=[
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_contact),
            ],
            allow_reentry=True,
        )
    ]
