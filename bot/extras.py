from enum import IntEnum
import json

from telegram import InputFile, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import ADMIN_IDS, COURIER_IDS, MINIAPP_URL, SHOP_NAME
from bot.database import (
    add_favorite,
    export_products_csv,
    format_order,
    get_all_user_ids,
    get_bonus,
    get_cart,
    get_courier_orders,
    get_daily_report,
    get_favorites,
    get_order,
    get_product_by_id,
    import_products_csv,
    is_favorite,
    refill_cart_from_order,
    remove_favorite,
    search_products,
    set_product_barcode,
    set_product_image,
    set_product_stock,
    update_order_status,
)
from bot.keyboards import (
    admin_menu_keyboard,
    admin_order_keyboard,
    barcode_attach_keyboard,
    cancel_keyboard,
    catalog_keyboard,
    main_menu_keyboard,
)


class ExtraState(IntEnum):
    SEARCH = 1
    BROADCAST = 2
    IMPORT_CSV = 3
    STOCK = 4
    PHOTO = 5
    BARCODE = 6


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_courier(user_id: int) -> bool:
    return user_id in COURIER_IDS


def menu_kb(user_id: int):
    return main_menu_keyboard(is_admin(user_id), is_courier(user_id))


def cart_qty_by_product(user_id: int) -> dict[int, int]:
    qty: dict[int, int] = {}
    for item in get_cart(user_id):
        qty[item["product_id"]] = qty.get(item["product_id"], 0) + item["quantity"]
    return qty


async def cancel_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("awaiting_barcode_product_id", None)
    context.user_data.pop("barcode_product_id", None)
    await update.message.reply_text(
        "Bekor qilindi.",
        reply_markup=menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔍 Qidiruv: mahsulot nomini yozing",
        reply_markup=cancel_keyboard(),
    )
    return ExtraState.SEARCH


async def do_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_extra(update, context)

    products = search_products(text)
    if not products:
        await update.message.reply_text("Hech narsa topilmadi. Boshqa so'z yozing:")
        return ExtraState.SEARCH

    await update.message.reply_text(
        f"Natija: {len(products)} ta",
        reply_markup=menu_kb(update.effective_user.id),
    )
    await update.message.reply_text(
        "Tanlang:",
        reply_markup=catalog_keyboard(
            products, cart_qty=cart_qty_by_product(update.effective_user.id)
        ),
    )
    return ConversationHandler.END


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    products = get_favorites(update.effective_user.id)
    if not products:
        await update.message.reply_text("⭐ Sevimlilar bo'sh.")
        return
    await update.message.reply_text(
        "⭐ Sevimlilaringiz:",
        reply_markup=catalog_keyboard(
            products, cart_qty=cart_qty_by_product(update.effective_user.id)
        ),
    )


async def show_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.timeutil import format_now_html

    points = get_bonus(update.effective_user.id)
    await update.message.reply_text(
        f"🎁 <b>Bonus hisobingiz</b>\n"
        f"{format_now_html()}\n\n"
        f"⭐ Balans: <b><u>{points:,}</u></b> ball\n"
        f"1 ball ≈ 1 so‘m chegirma\n\n"
        f"Har to‘langan buyurtmadan bonus yig‘iladi.\n"
        f"Buyurtmada bonus bilan to‘lash mumkin!",
        parse_mode="HTML",
    )


async def fav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    product_id = int(query.data.split(":")[1])
    user_id = query.from_user.id
    if is_favorite(user_id, product_id):
        remove_favorite(user_id, product_id)
        await query.answer("Sevimlidan olib tashlandi", show_alert=True)
    else:
        add_favorite(user_id, product_id)
        await query.answer("Sevimliga qo'shildi ⭐", show_alert=True)


async def reorder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    order_id = int(query.data.split(":")[1])
    order = get_order(order_id)
    if not order or order["user_id"] != query.from_user.id:
        await query.answer("Buyurtma topilmadi", show_alert=True)
        return
    added = refill_cart_from_order(query.from_user.id, order_id)
    await query.answer()
    await query.edit_message_text(
        f"🔁 {added} ta mahsulot savatchaga qo'shildi.\n"
        "🛒 Savatcha → Rasmiylashtirish orqali davom eting."
    )


async def cancel_order_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    order_id = int(query.data.split(":")[1])
    order = get_order(order_id)
    if not order or order["user_id"] != query.from_user.id:
        await query.answer("Ruxsat yo'q", show_alert=True)
        return
    if order["status"] not in {"new", "accepted"}:
        await query.answer("Bu buyurtmani bekor qilib bo'lmaydi", show_alert=True)
        return
    update_order_status(order_id, "cancelled")
    await query.answer()
    await query.edit_message_text(f"❌ Buyurtma #{order_id} bekor qilindi.")
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, f"❌ Mijoz buyurtma #{order_id} ni bekor qildi."
            )
        except Exception:
            pass


async def courier_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not (is_courier(uid) or is_admin(uid)):
        await update.message.reply_text("Faqat kuryerlar uchun.")
        return
    orders = get_courier_orders()
    if not orders:
        await update.message.reply_text("Faol buyurtmalar yo'q.")
        return
    await update.message.reply_text(f"🚴 Faol: {len(orders)} ta")
    for order in orders[:10]:
        await update.message.reply_text(
            format_order(order),
            reply_markup=admin_order_keyboard(order["id"]),
        )


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text("Broadcast matnini yuboring:")
    await query.message.reply_text("Xabar matni:", reply_markup=cancel_keyboard())
    return ExtraState.BROADCAST


async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_extra(update, context)
    users = get_all_user_ids()
    ok = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📣 {SHOP_NAME}\n\n{text}")
            ok += 1
        except Exception:
            pass
    await update.message.reply_text(
        f"Yuborildi: {ok}/{len(users)}",
        reply_markup=menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


async def export_csv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    content = export_products_csv().encode("utf-8")
    await query.message.reply_document(
        document=InputFile(content, filename="products.csv"),
        caption="📤 Mahsulotlar eksporti",
    )


async def start_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text("CSV fayl yuboring (products.csv)")
    await query.message.reply_text("Faylni yuboring:", reply_markup=cancel_keyboard())
    return ExtraState.IMPORT_CSV


async def do_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Bekor qilish":
        return await cancel_extra(update, context)
    doc = update.message.document
    if not doc:
        await update.message.reply_text("CSV fayl yuboring.")
        return ExtraState.IMPORT_CSV
    file = await doc.get_file()
    data = await file.download_as_bytearray()
    count = import_products_csv(data.decode("utf-8", errors="ignore"))
    await update.message.reply_text(
        f"✅ Import: {count} qator",
        reply_markup=menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


async def start_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[2])
    context.user_data["stock_product_id"] = product_id
    await query.message.reply_text(
        f"Ombor sonini yozing (mahsulot #{product_id}):",
        reply_markup=cancel_keyboard(),
    )
    return ExtraState.STOCK


async def do_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_extra(update, context)
    if not text.isdigit():
        await update.message.reply_text("Raqam yozing.")
        return ExtraState.STOCK
    pid = context.user_data.get("stock_product_id")
    set_product_stock(pid, int(text))
    await update.message.reply_text(
        f"✅ Ombor yangilandi: {text}",
        reply_markup=menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


async def start_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[2])
    context.user_data["photo_product_id"] = product_id
    await query.message.reply_text(
        "🖼 Mahsulot rasmini yuboring (telefon galereyasidan).\n"
        "Yaxshi yoritilgan, aniq rasm — sotuvni oshiradi.",
        reply_markup=cancel_keyboard(),
    )
    return ExtraState.PHOTO


async def do_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Bekor qilish":
        return await cancel_extra(update, context)
    if not update.message.photo:
        await update.message.reply_text("Iltimos, rasm yuboring (matn emas).")
        return ExtraState.PHOTO
    file_id = update.message.photo[-1].file_id
    pid = context.user_data.get("photo_product_id")
    set_product_image(pid, file_id)
    try:
        from bot.webapp import cache_product_photo

        await cache_product_photo(int(pid), file_id)
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ Rasm saqlandi! (#{pid})\n"
        f"Katalogda mahsulot endi rasm bilan chiqadi.",
        reply_markup=menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


def _barcode_from_payload(payload: dict) -> str:
    action = payload.get("action") or "scan"
    if action == "scan_many":
        codes = [
            str(x).strip() for x in (payload.get("barcodes") or []) if str(x).strip()
        ]
        return codes[0] if codes else ""
    return str(payload.get("barcode") or "").strip()


async def apply_barcode_from_payload(
    update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict
) -> int:
    msg = update.effective_message
    pid = context.user_data.get("awaiting_barcode_product_id") or context.user_data.get(
        "barcode_product_id"
    )
    if not msg or not pid:
        return ConversationHandler.END
    code = _barcode_from_payload(payload)
    if not code:
        await msg.reply_text("Kod bo‘sh. Qayta skanerlang.")
        return ExtraState.BARCODE
    try:
        set_product_barcode(int(pid), code)
    except ValueError as exc:
        await msg.reply_text(f"❌ {exc}", reply_markup=barcode_attach_keyboard())
        return ExtraState.BARCODE
    context.user_data.pop("awaiting_barcode_product_id", None)
    context.user_data.pop("barcode_product_id", None)
    product = get_product_by_id(int(pid))
    name = product["name"] if product else f"#{pid}"
    await msg.reply_text(
        f"✅ Kod biriktirildi\n{name} → `{code}`",
        parse_mode="Markdown",
        reply_markup=menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


async def start_barcode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.from_user or query.from_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    product_id = int(query.data.split(":")[2])
    product = get_product_by_id(product_id)
    if not product:
        await query.answer("Mahsulot topilmadi.", show_alert=True)
        return ConversationHandler.END
    context.user_data["barcode_product_id"] = product_id
    context.user_data["awaiting_barcode_product_id"] = product_id
    current = ""
    try:
        current = product["barcode"] or "—"
    except (KeyError, IndexError):
        current = "—"
    hint = (
        "Kamerani oching yoki kodni yozing."
        if MINIAPP_URL
        else "Kodni yozing (o‘chirish uchun 0)."
    )
    await query.message.reply_text(
        f"📷 «{product['name']}» uchun shtrix-kod\n"
        f"Hozirgi: {current}\n\n{hint}",
        reply_markup=barcode_attach_keyboard(),
    )
    return ExtraState.BARCODE


async def do_barcode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        context.user_data.pop("awaiting_barcode_product_id", None)
        context.user_data.pop("barcode_product_id", None)
        return await cancel_extra(update, context)
    pid = context.user_data.get("barcode_product_id")
    if not pid:
        return ConversationHandler.END
    if text in {"⏭ O‘chirish (0)", "0"}:
        set_product_barcode(int(pid), None)
        context.user_data.pop("awaiting_barcode_product_id", None)
        context.user_data.pop("barcode_product_id", None)
        await update.message.reply_text(
            "✅ Kod o‘chirildi.",
            reply_markup=menu_kb(update.effective_user.id),
        )
        return ConversationHandler.END
    try:
        set_product_barcode(int(pid), text)
    except ValueError as exc:
        await update.message.reply_text(
            f"❌ {exc}", reply_markup=barcode_attach_keyboard()
        )
        return ExtraState.BARCODE
    context.user_data.pop("awaiting_barcode_product_id", None)
    context.user_data.pop("barcode_product_id", None)
    await update.message.reply_text(
        f"✅ Kod saqlandi: `{text}`",
        parse_mode="Markdown",
        reply_markup=menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


async def do_barcode_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    if not msg or not msg.web_app_data:
        return ExtraState.BARCODE
    try:
        payload = json.loads(msg.web_app_data.data)
    except json.JSONDecodeError:
        await msg.reply_text("Skaner o‘qimadi.")
        return ExtraState.BARCODE
    return await apply_barcode_from_payload(update, context, payload)


async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers import edit_or_reply
    from bot.timeutil import format_now_html

    query = update.callback_query
    # query.answer() allaqachon admin_callback da chaqirilgan bo'lishi mumkin
    try:
        await query.answer()
    except Exception:
        pass
    if not is_admin(query.from_user.id):
        return
    report = get_daily_report()
    lines = [
        "📈 <b>1 kunlik hisobot</b>",
        f"{format_now_html()}",
        "",
        "💵 <b>Bugungi jami savdo</b>",
        f"📦 Buyurtmalar soni: <b>{report['orders_count']}</b> ta",
        f"💰 Jami summa: <b><u>{report['orders_sum']:,}</u></b> so'm",
        "",
        f"✅ To'langan/naqd: {report['paid_count']} ta — <b>{report['paid_sum']:,}</b> so'm",
        f"⏳ Kutilayotgan: {report['waiting_count']} ta — <b>{report['waiting_sum']:,}</b> so'm",
        "",
        "🏆 Top mahsulotlar:",
    ]
    if report["top"]:
        for row in report["top"]:
            lines.append(f"• {row['product_name']} — {row['qty']} dona")
    else:
        lines.append("• Hali yo'q")
    await edit_or_reply(
        query,
        "\n".join(lines),
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


def build_extra_conversations() -> list:
    return [
        ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^🔍 Qidiruv$"), start_search)],
            states={
                ExtraState.SEARCH: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, do_search)
                ]
            },
            fallbacks=[
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_extra),
            ],
            allow_reentry=True,
        ),
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(start_broadcast, pattern=r"^admin:broadcast$")
            ],
            states={
                ExtraState.BROADCAST: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, do_broadcast)
                ]
            },
            fallbacks=[
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_extra),
            ],
            allow_reentry=True,
        ),
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(start_import, pattern=r"^admin:import$")
            ],
            states={
                ExtraState.IMPORT_CSV: [
                    MessageHandler(filters.Document.ALL | filters.TEXT, do_import)
                ]
            },
            fallbacks=[
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_extra),
            ],
            allow_reentry=True,
        ),
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(start_stock, pattern=r"^admin_prod:stock:\d+$")
            ],
            states={
                ExtraState.STOCK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, do_stock)
                ]
            },
            fallbacks=[
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_extra),
            ],
            allow_reentry=True,
        ),
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(start_photo, pattern=r"^admin_prod:photo:\d+$")
            ],
            states={
                ExtraState.PHOTO: [
                    MessageHandler(filters.PHOTO | filters.TEXT, do_photo)
                ]
            },
            fallbacks=[
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_extra),
            ],
            allow_reentry=True,
        ),
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    start_barcode, pattern=r"^admin_prod:barcode:\d+$"
                )
            ],
            states={
                ExtraState.BARCODE: [
                    MessageHandler(
                        filters.StatusUpdate.WEB_APP_DATA, do_barcode_webapp
                    ),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, do_barcode),
                ]
            },
            fallbacks=[
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_extra),
            ],
            allow_reentry=True,
        ),
    ]
