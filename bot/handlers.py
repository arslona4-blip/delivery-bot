import json
import re
from enum import IntEnum

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.barcode_lookup import lookup_barcode_name
from bot.config import (
    ADMIN_IDS,
    BONUS_PERCENT,
    BOT_USERNAME,
    CARD_HOLDER,
    CARD_NUMBER,
    COURIER_IDS,
    DELIVERY_PRICE,
    MIN_ORDER_AMOUNT,
    MINIAPP_URL,
    PAYMENT_PROVIDER_TOKEN,
    REFERRAL_BONUS,
    SHOP_ADDRESS,
    SHOP_HOURS,
    SHOP_NAME,
    SHOP_PHONE,
    SHOP_TELEGRAM,
    card_payment_enabled,
    online_payment_enabled,
)
from bot.database import (
    add_bonus,
    add_to_cart,
    calc_promo_discount,
    clear_cart,
    create_category,
    create_order,
    create_product,
    create_variant,
    decrease_stock_for_cart,
    delete_category,
    delete_order,
    delete_product,
    delete_variant,
    format_cart,
    format_order,
    get_bonus,
    get_cart,
    get_cart_totals,
    get_categories,
    get_category,
    get_favorites,
    get_order,
    get_orders_by_status,
    get_product,
    get_product_by_barcode,
    get_product_by_id,
    get_products,
    get_stats,
    get_last_delivery_address,
    get_user,
    get_user_orders,
    get_variants,
    product_display_price,
    remove_from_cart,
    save_order_items,
    save_referral,
    set_cart_quantity,
    set_product_active,
    set_user_phone,
    spend_bonus,
    update_order_status,
    update_payment_status,
    update_product_price,
    upsert_user,
)
from bot.keyboards import (
    admin_all_products_list_keyboard,
    admin_categories_list_keyboard,
    admin_category_item_keyboard,
    admin_category_products_header_keyboard,
    admin_category_products_list_keyboard,
    admin_menu_keyboard,
    admin_delete_order_confirm_keyboard,
    admin_order_keyboard,
    admin_payment_keyboard,
    admin_product_item_keyboard,
    admin_products_keyboard,
    admin_variant_item_keyboard,
    bonus_keyboard,
    cancel_keyboard,
    card_paid_keyboard,
    cart_keyboard,
    catalog_categories_keyboard,
    catalog_keyboard,
    category_pick_keyboard,
    confirm_order_keyboard,
    contact_keyboard,
    delivery_slots_keyboard,
    location_keyboard,
    main_menu_keyboard,
    more_menu_keyboard,
    order_actions_keyboard,
    payment_keyboard,
    product_keyboard,
    promo_keyboard,
    new_product_barcode_keyboard,
    scan_sale_keyboard,
    shop_inline_button,
    suggested_name_keyboard,
)
from bot.timeutil import format_now_html, get_delivery_slots, money_html


class OrderState(IntEnum):
    DELIVERY = 1
    NOTE = 2
    PHONE = 3
    CONFIRM = 4
    SLOT = 5
    PROMO = 6
    BONUS = 7


class ProductAdminState(IntEnum):
    NAME = 1
    PRICE = 2
    DESCRIPTION = 3
    EDIT_PRICE = 4
    CATEGORY_NAME = 5
    PICK_CATEGORY = 6
    SIZE_NAME = 7
    SIZE_PRICE = 8
    BARCODE = 9


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def menu_for(user_id: int):
    return main_menu_keyboard(
        is_admin(user_id),
        user_id in COURIER_IDS or is_admin(user_id),
    )


def parse_price_sum(raw: str) -> int | None:
    """'15000', '15 000', '15000 so'm' kabi yozuvlardan narxni oladi."""
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    value = int(digits)
    return value if value > 0 else None


async def edit_or_reply(query, text: str, reply_markup=None, parse_mode=None) -> None:
    """Rasmli xabarda edit_message_text ishlamaydi — yangi xabar yuboriladi."""
    message = query.message
    has_photo = bool(message and message.photo)
    if not has_photo:
        try:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
            return
        except Exception:
            pass
    await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    is_new = get_user(user.id) is None
    upsert_user(user.id, user.full_name, user.username)
    name = (user.first_name or "mehmon").strip()

    # Do'st taklifi: /start ref123456
    if is_new and context.args:
        raw = (context.args[0] or "").strip()
        if raw.lower().startswith("ref"):
            digits = "".join(ch for ch in raw[3:] if ch.isdigit())
            if digits:
                referrer_id = int(digits)
                if save_referral(user.id, referrer_id):
                    add_bonus(referrer_id, REFERRAL_BONUS)
                    try:
                        await context.bot.send_message(
                            referrer_id,
                            f"🎉 Do‘stingiz botga qo‘shildi!\n"
                            f"+{REFERRAL_BONUS:,} bonus ball berildi.",
                        )
                    except Exception:
                        pass

    bot_link = f"https://t.me/{BOT_USERNAME}"
    share_url = (
        "https://t.me/share/url?url="
        f"{bot_link}?start=ref{user.id}"
        "&text=Baraka%20Market%20%E2%80%94%20tez%20yetkazib%20berish!"
    )

    await update.message.reply_text(
        f"✨ <b>Assalomu alaykum, {name}!</b>\n\n"
        f"🏪 <b>{SHOP_NAME}</b>\n"
        f"🚚 Uyingizgacha tez yetkazib beramiz\n"
        f"{format_now_html()}\n\n"
        f"┌──────────────┐\n"
        f"│ 📍 {SHOP_ADDRESS}\n"
        f"│ 🕐 {SHOP_HOURS}\n"
        f"│ 📞 {SHOP_PHONE}\n"
        f"└──────────────┘\n\n"
        f"🏷 Promo: <b>BARAKA10</b> — 10% chegirma "
        f"(min {MIN_ORDER_AMOUNT:,} so‘m)\n"
        f"👇 Pastdagi <b>🛒 Do'kon</b> tugmasini bosing!",
        reply_markup=menu_for(user.id),
        parse_mode="HTML",
    )
    start_rows: list[list[InlineKeyboardButton]] = []
    shop_btn = shop_inline_button("🛒 Do'konni ochish")
    if shop_btn:
        start_rows.append([shop_btn])
    start_rows.append(
        [
            InlineKeyboardButton("🛒 Savatcham", callback_data="cart:view"),
            InlineKeyboardButton("📞 Aloqa", callback_data="catalog:contact"),
        ]
    )
    if not shop_btn:
        start_rows.insert(
            0,
            [
                InlineKeyboardButton(
                    "🛍 Katalogni ochish", callback_data="catalog:list"
                )
            ],
        )
    start_rows.append(
        [InlineKeyboardButton("👥 Do‘stlarga ulashish", url=share_url)]
    )
    await update.message.reply_text(
        "Tez buyurtma uchun do‘konni oching 👇",
        reply_markup=InlineKeyboardMarkup(start_rows),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    shop_line = (
        "🛒 <b>Do'kon</b> — bir bosishda web do‘kon (rasmli katalog)\n"
        if MINIAPP_URL
        else ""
    )
    scan_line = (
        "📷 <b>Skaner</b> — shtrix-kod bilan tezkor savatga\n"
        if MINIAPP_URL
        else ""
    )
    await update.message.reply_text(
        "🧭 <b>Qanday buyurtma beriladi?</b>\n\n"
        f"{shop_line}"
        f"{scan_line}"
        "1️⃣ <b>Katalog</b> — yoqqan mahsulotni bosing\n"
        "    (avtomatik savatchaga tushadi ✅)\n"
        "2️⃣ <b>Savatcha</b> — miqdorni sozlang\n"
        "3️⃣ <b>Buyurtma berish</b> — manzil + vaqt\n"
        "4️⃣ Tasdiqlang va to‘lovni tanlang\n\n"
        f"🏷 Promo: <b>BARAKA10</b> (10%, min {MIN_ORDER_AMOUNT:,} so‘m)\n"
        f"👥 Do‘st taklif qilsangiz — +{REFERRAL_BONUS:,} bonus\n"
        "   («⋯ Ko‘proq» → «👥 Ulashish»)\n\n"
        "Savol bo‘lsa — «📞 Aloqa» ni bosing.",
        parse_mode="HTML",
    )


async def webapp_scan_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kamera skaneridan kelgan kodlar → savatcha (yoki admin barcode)."""
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg or not msg.web_app_data:
        return
    try:
        payload = json.loads(msg.web_app_data.data)
    except json.JSONDecodeError:
        await msg.reply_text("Skaner ma’lumoti o‘qilmadi.")
        return

    # Admin barcode biriktirish — extras conversation ushlamasa fallback
    if context.user_data.get("awaiting_barcode_product_id"):
        from bot.extras import apply_barcode_from_payload

        await apply_barcode_from_payload(update, context, payload)
        return

    action = payload.get("action") or "scan"
    barcodes: list[str] = []
    if action == "scan_many":
        barcodes = [
            str(x).strip() for x in (payload.get("barcodes") or []) if str(x).strip()
        ]
    else:
        one = str(payload.get("barcode") or "").strip()
        if one:
            barcodes = [one]
    if not barcodes:
        await msg.reply_text("Kod bo‘sh.")
        return

    await _sale_add_barcodes(update, context, barcodes)


async def _sale_add_barcodes(
    update: Update, context: ContextTypes.DEFAULT_TYPE, barcodes: list[str]
) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    added: list[str] = []
    need_size: list[tuple] = []
    missing: list[str] = []

    for code in barcodes:
        product = get_product_by_barcode(code)
        if not product:
            missing.append(code)
            continue
        variants = get_variants(int(product["id"]))
        if variants:
            need_size.append((product, variants))
            continue
        add_to_cart(user.id, int(product["id"]), 1, 0)
        added.append(str(product["name"]))

    parts: list[str] = []
    if added:
        parts.append("📷 Savatchaga:\n" + "\n".join(f"• {n}" for n in added[-20:]))
    if missing:
        parts.append("❌ Topilmadi:\n" + "\n".join(f"• `{c}`" for c in missing[:10]))
    if not parts and not need_size:
        parts.append("Hech narsa qo‘shilmadi.")

    kb = scan_sale_keyboard() or menu_for(user.id)
    await msg.reply_text(
        "\n\n".join(parts) + f"\n\n{format_cart(user.id)}",
        parse_mode="Markdown",
        reply_markup=kb,
    )

    for product, variants in need_size[:5]:
        await msg.reply_text(
            f"📐 <b>{product['name']}</b> — o‘lcham tanlang:",
            parse_mode="HTML",
            reply_markup=product_keyboard(
                int(product["id"]),
                product["category_id"],
                variants,
                cart_variant_qty={},
            ),
        )


async def share_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot_link = f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"
    share_url = (
        "https://t.me/share/url?url="
        f"{bot_link}"
        "&text=Baraka%20Market%20yetkazib%20berish%20%E2%80%94%20sinab%20ko%E2%80%98ring!"
    )
    await update.message.reply_text(
        f"👥 <b>Do‘stlarni taklif qiling!</b>\n\n"
        f"Har bir yangi do‘st uchun <b>+{REFERRAL_BONUS:,}</b> bonus ball.\n\n"
        f"🔗 Sizning havolangiz:\n"
        f"<code>{bot_link}</code>\n\n"
        f"Pastdagi tugma orqali Telegram’da ulashing 👇",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📤 Ulashish", url=share_url)]]
        ),
    )


async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"📞 <b>Biz bilan bog‘laning</b>\n"
        f"🏪 {SHOP_NAME}\n"
        f"{format_now_html()}\n\n"
        f"📱 Telefon: <b>{SHOP_PHONE}</b>\n"
        f"💬 Telegram: {SHOP_TELEGRAM}\n"
        f"📍 Manzil: {SHOP_ADDRESS}\n"
        f"🕐 Ish vaqti: {SHOP_HOURS}\n\n"
        f"⏳ Buyurtmangizni tez qabul qilamiz!",
        parse_mode="HTML",
    )


async def show_more_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✨ <b>Qo‘shimcha imkoniyatlar</b>\n"
        "Qidiruv, sevimlilar, bonus va yordam shu yerda:",
        reply_markup=more_menu_keyboard(),
        parse_mode="HTML",
    )


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🏠 Asosiy menyu\nKerakli bo‘limni tanlang 👇",
        reply_markup=menu_for(update.effective_user.id),
    )


def _cart_qty_by_product(user_id: int) -> dict[int, int]:
    qty: dict[int, int] = {}
    for item in get_cart(user_id):
        qty[item["product_id"]] = qty.get(item["product_id"], 0) + item["quantity"]
    return qty


def _cart_qty_by_variant(user_id: int, product_id: int) -> dict[int, int]:
    qty: dict[int, int] = {}
    for item in get_cart(user_id):
        if item["product_id"] == product_id:
            qty[item["variant_id"]] = item["quantity"]
    return qty


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    categories = get_categories()
    if not categories:
        products = get_products()
        if not products:
            text = (
                "🛍 <b>Katalog</b>\n\n"
                "Hozircha mahsulotlar yo‘q.\n"
                "Tez orada yangilanadi — qayta urinib ko‘ring!"
            )
            if update.callback_query:
                await edit_or_reply(
                    update.callback_query, text, parse_mode="HTML"
                )
            else:
                await update.message.reply_text(text, parse_mode="HTML")
            return
        text = (
            f"🛍 <b>{SHOP_NAME}</b>\n"
            f"{format_now_html()}\n"
            f"Mahsulotni tanlang — bir bosishda savatchaga tushadi ✨"
        )
        markup = catalog_keyboard(products, cart_qty=_cart_qty_by_product(user_id))
    else:
        text = (
            f"🛍 <b>{SHOP_NAME} katalogi</b>\n"
            f"{format_now_html()}\n"
            f"Toifani tanlang va tanlovni boshlang 👇"
        )
        markup = catalog_categories_keyboard(categories)

    if update.callback_query:
        await edit_or_reply(
            update.callback_query, text, reply_markup=markup, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="HTML"
        )


async def show_category_products(
    update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int
) -> None:
    user_id = update.effective_user.id
    category = get_category(category_id)
    products = get_products(category_id=category_id)
    title = category["name"] if category else "Toifa"
    if not products:
        text = (
            f"📁 <b>{title}</b>\n\n"
            f"Bu toifada hozircha mahsulot yo‘q.\n"
            f"Boshqa toifani ko‘ring 👇"
        )
        markup = catalog_categories_keyboard(get_categories())
    else:
        text = (
            f"📁 <b>{title}</b>\n"
            f"{format_now_html()}\n"
            f"{len(products)} ta mahsulot — tanlang ✨"
        )
        markup = catalog_keyboard(
            products,
            category_id,
            cart_qty=_cart_qty_by_product(user_id),
        )

    await edit_or_reply(
        update.callback_query, text, reply_markup=markup, parse_mode="HTML"
    )


async def show_cart_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    items = get_cart(user_id)
    text = f"{format_now_html()}\n\n{format_cart(user_id)}"
    if not items:
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🛍 Katalogni ochish", callback_data="catalog:list"
                    )
                ]
            ]
        )
    else:
        markup = cart_keyboard(items)

    if update.callback_query:
        await edit_or_reply(
            update.callback_query, text, reply_markup=markup, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=markup,
            parse_mode="HTML",
        )
        await update.message.reply_text(
            "Asosiy menyu 👇",
            reply_markup=menu_for(user_id),
        )


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if query.data == "catalog:list":
        await query.answer()
        await show_catalog(update, context)
        return

    if query.data == "catalog:contact":
        await query.answer()
        await query.message.reply_text(
            f"📞 <b>Biz bilan bog‘laning</b>\n"
            f"🏪 {SHOP_NAME}\n"
            f"{format_now_html()}\n\n"
            f"📱 Telefon: <b>{SHOP_PHONE}</b>\n"
            f"💬 Telegram: {SHOP_TELEGRAM}\n"
            f"📍 Manzil: {SHOP_ADDRESS}\n"
            f"🕐 Ish vaqti: {SHOP_HOURS}",
            parse_mode="HTML",
        )
        return

    if query.data == "catalog:search":
        await query.answer()
        await query.message.reply_text(
            "🔍 <b>Qidiruv</b>\n\n"
            "Mahsulot nomini yozing — topib beraman!\n"
            "Yoki pastdan «⋯ Ko‘proq» → «🔍 Qidiruv».",
            parse_mode="HTML",
        )
        return

    if query.data == "catalog:favs":
        await query.answer()
        products = get_favorites(query.from_user.id)
        if not products:
            await query.message.reply_text(
                "⭐ <b>Sevimlilar bo‘sh</b>\n\n"
                "Mahsulotda ⭐ tugmasini bosib saqlang — "
                "keyin tez topasiz!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🛍 Katalog", callback_data="catalog:list"
                            )
                        ]
                    ]
                ),
            )
            return
        await query.message.reply_text(
            "⭐ <b>Sevimlilaringiz</b>\nYoqqanlaringiz shu yerda:",
            parse_mode="HTML",
            reply_markup=catalog_keyboard(
                products, cart_qty=_cart_qty_by_product(query.from_user.id)
            ),
        )
        return

    if query.data.startswith("catalog:cat:"):
        await query.answer()
        category_id = int(query.data.split(":")[2])
        await show_category_products(update, context, category_id)
        return

    product_id = int(query.data.split(":")[1])
    product = get_product(product_id)
    if not product:
        await query.answer()
        await query.edit_message_text("Mahsulot topilmadi.")
        return

    variants = get_variants(product_id)

    # O'lchamsiz mahsulot — rasm bo'lsa kartochka, yo'qsa tezkor savatga
    if not variants:
        image_id = None
        try:
            image_id = product["image_file_id"]
        except (KeyError, IndexError):
            image_id = None
        if image_id:
            await query.answer()
            category_name = product["category_name"] or "—"
            price_text = product_display_price(product)
            desc = product["description"] or "Sifatli mahsulot"
            text = (
                f"✨ <b>{product['name']}</b>\n"
                f"📁 {category_name}\n"
                f"✨ 💰 <b><u>{price_text}</u></b> ✨\n"
                f"📝 {desc}"
            )
            back = (
                f"catalog:cat:{product['category_id']}"
                if product["category_id"]
                else "catalog:list"
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Savatchaga",
                            callback_data=f"cart_add:{product_id}:0",
                        )
                    ],
                    [InlineKeyboardButton("⬅️ Orqaga", callback_data=back)],
                ]
            )
            try:
                await query.message.reply_photo(
                    photo=image_id,
                    caption=text,
                    reply_markup=kb,
                    parse_mode="HTML",
                )
            except Exception:
                await query.message.reply_text(
                    text, reply_markup=kb, parse_mode="HTML"
                )
            return
        add_to_cart(query.from_user.id, product_id, 1, 0)
        count, _ = get_cart_totals(query.from_user.id)
        await query.answer(f"✅ Savatchaga qo'shildi · {count} ta", show_alert=False)
        if product["category_id"]:
            await show_category_products(update, context, product["category_id"])
        else:
            await show_catalog(update, context)
        return

    # O'lchamli mahsulot — rasm + o'lcham tanlash
    await query.answer()
    category_name = product["category_name"] or "—"
    price_text = product_display_price(product)
    desc = product["description"] or "Sifatli mahsulot"
    text = (
        f"✨ <b>{product['name']}</b>\n"
        f"📁 {category_name}\n"
        f"✨ 💰 <b><u>{price_text}</u></b> ✨\n"
        f"📝 {desc}\n\n"
        "O‘lchamni tanlang 👇"
    )
    size_kb = product_keyboard(
        product_id,
        product["category_id"],
        variants,
        cart_variant_qty=_cart_qty_by_variant(query.from_user.id, product_id),
    )
    image_id = None
    try:
        image_id = product["image_file_id"]
    except (KeyError, IndexError):
        image_id = None

    if image_id:
        try:
            await query.message.reply_photo(
                photo=image_id,
                caption=text,
                reply_markup=size_kb,
                parse_mode="HTML",
            )
        except Exception:
            await query.message.reply_text(
                text, reply_markup=size_kb, parse_mode="HTML"
            )
    else:
        await edit_or_reply(query, text, reply_markup=size_kb, parse_mode="HTML")


async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data.startswith("cart_add:"):
        parts = data.split(":")
        product_id = int(parts[1])
        variant_id = int(parts[2]) if len(parts) > 2 else 0
        product = get_product(product_id)
        if not product:
            await query.answer("Mahsulot topilmadi.", show_alert=True)
            return None
        if variant_id > 0:
            variants = {v["id"]: v for v in get_variants(product_id)}
            if variant_id not in variants:
                await query.answer("O'lcham topilmadi.", show_alert=True)
                return None
            label = f"{product['name']} ({variants[variant_id]['name']})"
        else:
            label = product["name"]
        add_to_cart(user_id, product_id, 1, variant_id)
        count, _ = get_cart_totals(user_id)
        await query.answer(
            f"✅ Savatchaga qo'shildi · {label} ({count} ta)",
            show_alert=False,
        )
        if product["category_id"]:
            await show_category_products(update, context, product["category_id"])
        else:
            await show_catalog(update, context)
        return None

    await query.answer()

    if data == "cart:view":
        await show_cart_message(update, context)
        return None

    if data == "cart:clear":
        clear_cart(user_id)
        await edit_or_reply(query, "🛒 Savatcha tozalandi.")
        return None

    if data.startswith("cart_inc:"):
        _, pid, vid = data.split(":")
        product_id, variant_id = int(pid), int(vid)
        items = {
            (i["product_id"], i["variant_id"]): i["quantity"] for i in get_cart(user_id)
        }
        set_cart_quantity(
            user_id,
            product_id,
            items.get((product_id, variant_id), 0) + 1,
            variant_id,
        )
        await show_cart_message(update, context)
        return None

    if data.startswith("cart_dec:"):
        _, pid, vid = data.split(":")
        product_id, variant_id = int(pid), int(vid)
        items = {
            (i["product_id"], i["variant_id"]): i["quantity"] for i in get_cart(user_id)
        }
        set_cart_quantity(
            user_id,
            product_id,
            items.get((product_id, variant_id), 0) - 1,
            variant_id,
        )
        await show_cart_message(update, context)
        return None

    if data.startswith("cart_del:"):
        _, pid, vid = data.split(":")
        remove_from_cart(user_id, int(pid), int(vid))
        await show_cart_message(update, context)
        return None

    return None


async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id
    items = get_cart(user_id)
    if not items:
        text = "Savatcha bo'sh. Avval mahsulot qo'shing."
        if query:
            await edit_or_reply(query, text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END

    _, subtotal = get_cart_totals(user_id)
    if subtotal < MIN_ORDER_AMOUNT:
        text = (
            f"Minimal buyurtma: {MIN_ORDER_AMOUNT:,} so'm\n"
            f"Hozirgi savat: {subtotal:,} so'm"
        )
        if query:
            await query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END

    context.user_data["order"] = {
        "pickup_address": SHOP_ADDRESS,
        "from_cart": True,
        "subtotal": subtotal,
        "price": subtotal + DELIVERY_PRICE,
        "discount": 0,
        "promo_code": "",
        "bonus_spent": 0,
        "delivery_slot": "",
        "description": "",
    }

    last_addr = get_last_delivery_address(user_id)
    text = (
        f"{format_cart(user_id)}\n\n"
        "📍 Qayerga yetkazilsin?\n"
        "«📍 Joylashuvni yuborish» yoki manzilni yozing."
    )
    if last_addr:
        text += "\nYoki oxirgi manzilni tanlang."
    markup = location_keyboard(last_addr)
    if query:
        await query.answer()
        await query.message.reply_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
    return OrderState.DELIVERY


async def continue_after_delivery(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    slots = get_delivery_slots()
    await update.message.reply_text(
        f"🕒 <b>Qachon yetkazaylik?</b>\n"
        f"{format_now_html()}\n"
        f"Qulay sana va vaqtni tanlang 👇",
        reply_markup=delivery_slots_keyboard(slots),
        parse_mode="HTML",
    )
    return OrderState.SLOT


async def receive_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "order:cancel":
        await query.edit_message_text("Bekor qilindi.")
        context.user_data.pop("order", None)
        await query.message.reply_text("Menyu:", reply_markup=menu_for(query.from_user.id))
        return ConversationHandler.END

    slots = get_delivery_slots()
    idx = int(query.data.split(":")[1])
    if idx < 0 or idx >= len(slots):
        await query.edit_message_text("Vaqt noto‘g‘ri. Qaytadan tanlang.")
        return ConversationHandler.END
    slot = slots[idx]
    context.user_data["order"]["delivery_slot"] = slot
    await query.edit_message_text(f"🕒 Yetkazish: {slot}")
    # Promo bosqichi o'tkazib yuboriladi (kerak bo'lsa tasdiqda «🏷 Promo kod»)
    return await ask_bonus(update, context)


async def receive_promo_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_order_flow(update, context)
    return await apply_promo(update, context, text)


async def receive_promo_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "order:cancel":
        await query.edit_message_text("Bekor qilindi.")
        context.user_data.pop("order", None)
        await query.message.reply_text("Menyu:", reply_markup=menu_for(query.from_user.id))
        return ConversationHandler.END
    await query.edit_message_text("Promo ishlatilmadi.")
    order = context.user_data.get("order") or {}
    if order.get("phone"):
        return await show_order_summary_message(
            query.message, query.from_user, context
        )
    return await ask_bonus(update, context)


async def apply_promo(
    update: Update, context: ContextTypes.DEFAULT_TYPE, code: str
) -> int:
    _, subtotal = get_cart_totals(update.effective_user.id)
    discount, msg = calc_promo_discount(code, subtotal)
    if discount <= 0:
        await update.message.reply_text(f"❌ {msg}\nQayta yozing yoki Promo yo'q tugmasini bosing:")
        return OrderState.PROMO
    context.user_data["order"]["promo_code"] = code.upper()
    context.user_data["order"]["discount"] = discount
    await update.message.reply_text(f"✅ Promo qo'llandi: −{discount:,} so'm")
    # Agar allaqachon telefon bor (tasdiqdan kelgan) — xulosani yangilash
    order = context.user_data.get("order") or {}
    if order.get("phone"):
        return await show_order_summary(update, context)
    return await ask_bonus(update, context)


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Har doim ishlaydigan telefon so'raydi (eski raqamni avtomatik o'tkazmaydi)."""
    context.user_data.setdefault("order", {})
    context.user_data["order"].pop("phone", None)

    user = get_user(update.effective_user.id)
    last_phone = None
    if user:
        try:
            last_phone = (user["phone"] or "").strip() or None
        except (KeyError, IndexError, TypeError):
            last_phone = None

    text = (
        "📞 <b>Telefon raqamingizni qoldiring</b>\n\n"
        "Yetkazib berish uchun <b>hozir ishlaydigan</b> raqam kerak.\n"
        "Telegramdagi raqam eski, SIM almashtirilgan yoki "
        "faol emas bo‘lishi mumkin — shunda bog‘lana olmaymiz.\n\n"
        "<b>Qanday yuborasiz?</b>\n"
        "1️⃣ «📱 Kontaktni yuborish» — Telegramdagi raqamingiz\n"
        "2️⃣ 📎 → <b>Kontakt</b> — telefonda saqlangan raqamni tanlang\n"
        "3️⃣ Qo‘lda yozing: <code>+998901234567</code>"
    )
    if last_phone:
        text += (
            f"\n\nSaqlangan raqam: <b>{last_phone}</b>\n"
            "To‘g‘ri bo‘lsa — pastdagi «✅ Shu raqam» ni bosing.\n"
            "Boshqa bo‘lsa — yangisini yuboring."
        )

    msg = update.effective_message
    await msg.reply_text(
        text,
        reply_markup=contact_keyboard(last_phone),
        parse_mode="HTML",
    )
    return OrderState.PHONE


async def ask_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    bonus = get_bonus(user_id)
    context.user_data["order"].setdefault("discount", 0)
    context.user_data["order"].setdefault("promo_code", "")
    context.user_data["order"]["bonus_spent"] = 0

    # Bonus yo'q — to'g'ridan-to'g'ri telefon so'rash
    if bonus <= 0:
        return await ask_phone(update, context)

    msg = update.effective_message
    await msg.reply_text(
        f"🎁 Bonus: {bonus:,} ball\nIshlatasizmi?",
        reply_markup=bonus_keyboard(bonus),
    )
    return OrderState.BONUS


async def receive_bonus_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _, subtotal = get_cart_totals(user_id)
    discount = context.user_data["order"].get("discount", 0)
    if query.data == "bonus:use":
        bonus = get_bonus(user_id)
        max_use = max(0, subtotal + DELIVERY_PRICE - discount - 1000)
        use = min(bonus, max_use)
        context.user_data["order"]["bonus_spent"] = use
        await query.edit_message_text(f"🎁 Bonus: −{use:,} so'm")
    else:
        context.user_data["order"]["bonus_spent"] = 0
        await query.edit_message_text("Bonus ishlatilmadi.")

    context.user_data["order"]["description"] = context.user_data["order"].get(
        "description", ""
    )
    return await ask_phone(update, context)


async def receive_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Bekor qilish":
        return await cancel_order_flow(update, context)

    location = update.message.location
    if location:
        lat = location.latitude
        lon = location.longitude
        context.user_data["order"]["latitude"] = lat
        context.user_data["order"]["longitude"] = lon
        context.user_data["order"]["delivery_address"] = "Lokatsiya"
        await update.message.reply_text("✅ Joylashuv qabul qilindi.")
        return await continue_after_delivery(update, context)

    text = (update.message.text or "").strip()
    # Oxirgi manzil tugmasi: "🏠 ..."
    if text.startswith("🏠 "):
        text = text[2:].strip()
        if text.endswith("..."):
            last = get_last_delivery_address(update.effective_user.id)
            if last:
                text = last

    if text and text not in {"📍 Joylashuv", "📍 Joylashuvni yuborish"}:
        context.user_data["order"]["latitude"] = None
        context.user_data["order"]["longitude"] = None
        context.user_data["order"]["delivery_address"] = text
        await update.message.reply_text("✅ Manzil qabul qilindi.")
        return await continue_after_delivery(update, context)

    last_addr = get_last_delivery_address(update.effective_user.id)
    await update.message.reply_text(
        "📍 Joylashuvni yuboring yoki manzilni yozing.",
        reply_markup=location_keyboard(last_addr),
    )
    return OrderState.DELIVERY


async def receive_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Eski holat uchun: izoh bosqichi o'tkazib yuboriladi
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_order_flow(update, context)
    if text not in {"-", ""} and not _is_skip_text(text):
        context.user_data["order"]["description"] = text
    else:
        context.user_data["order"]["description"] = ""
    return await continue_after_delivery(update, context)


def _normalize_phone(raw: str) -> str | None:
    """Telefonni tozalaydi. Kamida 9 ta raqam bo'lishi kerak."""
    text = (raw or "").strip()
    if text.startswith("✅ Shu raqam:"):
        text = text.split(":", 1)[1].strip()
    digits = re.sub(r"\D", "", text)
    if len(digits) < 9:
        return None
    if text.startswith("+"):
        return "+" + digits
    if digits.startswith("998") and len(digits) >= 12:
        return "+" + digits
    if len(digits) == 9:
        return "+998" + digits
    return text if text.startswith("+") else ("+" + digits if digits else None)


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Bekor qilish":
        return await cancel_order_flow(update, context)

    phone = None
    if update.message.contact:
        phone = _normalize_phone(update.message.contact.phone_number or "")
    elif update.message.text:
        phone = _normalize_phone(update.message.text)

    if not phone:
        user_row = get_user(update.effective_user.id)
        last = None
        if user_row:
            try:
                last = (user_row["phone"] or "").strip() or None
            except (KeyError, IndexError, TypeError):
                last = None
        await update.message.reply_text(
            "❌ Raqam noto‘g‘ri.\n\n"
            "Ishlaydigan raqamni qoldiring:\n"
            "• Kontakt tugmasi, yoki\n"
            "• <code>+998901234567</code> ko‘rinishida yozing",
            parse_mode="HTML",
            reply_markup=contact_keyboard(last),
        )
        return OrderState.PHONE

    context.user_data["order"]["phone"] = phone
    set_user_phone(update.effective_user.id, phone)
    await update.message.reply_text(
        f"✅ Telefon qabul qilindi: <b>{phone}</b>\n"
        "Yetkazishda shu raqam orqali bog‘lanamiz.",
        parse_mode="HTML",
    )
    return await show_order_summary(update, context)


async def show_order_summary_message(message, user, context: ContextTypes.DEFAULT_TYPE) -> int:
    order = context.user_data["order"]
    user_id = user.id
    delivery = order["delivery_address"]
    if order.get("latitude") is not None and order.get("longitude") is not None:
        delivery = (
            f"{delivery}\n"
            f"🗺 https://maps.google.com/?q={order['latitude']},{order['longitude']}"
        )

    _, subtotal = get_cart_totals(user_id)
    discount = order.get("discount", 0)
    bonus_spent = order.get("bonus_spent", 0)
    total = max(0, subtotal + DELIVERY_PRICE - discount - bonus_spent)
    order["subtotal"] = subtotal
    order["price"] = total

    cart_text = format_cart(user_id)
    summary = (
        f"🧾 <b>Buyurtmani tekshiring</b>\n"
        f"{format_now_html()}\n\n"
        f"{cart_text}\n\n"
        f"🕒 Yetkazish: <b><u>{order.get('delivery_slot') or '—'}</u></b>\n"
        f"🏷 Promo: {order.get('promo_code') or '—'} (−{discount:,})\n"
        f"🎁 Bonus: −{bonus_spent:,}\n"
        f"📍 Qayerdan: {order['pickup_address']}\n"
        f"🏁 Qayerga: {delivery}\n"
        f"📞 Telefon: {order['phone']}\n\n"
        f"✨ 💳 {money_html(total)} <b>← TO‘LOV</b> ✨\n\n"
        "Hammasi to‘g‘rimi? Tasdiqlang 👇"
    )
    await message.reply_text(
        summary, reply_markup=confirm_order_keyboard(), parse_mode="HTML"
    )
    await message.reply_text(
        "Asosiy menyu 👇", reply_markup=menu_for(user_id)
    )
    return OrderState.CONFIRM


async def show_order_summary(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await show_order_summary_message(
        update.message, update.effective_user, context
    )


async def confirm_order_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "order:cancel":
        await query.edit_message_text("Buyurtma bekor qilindi.")
        context.user_data.pop("order", None)
        await query.message.reply_text(
            "Asosiy menyu:",
            reply_markup=menu_for(query.from_user.id),
        )
        return ConversationHandler.END

    if query.data == "order:add_promo":
        await query.message.reply_text(
            "🏷 Promo kodni yozing (masalan BARAKA10)\n"
            "yoki o'tkazib yuboring:",
            reply_markup=promo_keyboard(),
        )
        return OrderState.PROMO

    order_data = context.user_data.get("order")
    if not order_data:
        await query.edit_message_text("Buyurtma ma'lumotlari topilmadi.")
        return ConversationHandler.END

    user_id = query.from_user.id
    items = get_cart(user_id)
    if not items:
        await query.edit_message_text("Savatcha bo'sh. Qaytadan urinib ko'ring.")
        context.user_data.pop("order", None)
        return ConversationHandler.END

    _, subtotal = get_cart_totals(user_id)
    discount = int(order_data.get("discount") or 0)
    bonus_spent = int(order_data.get("bonus_spent") or 0)
    total = max(0, subtotal + DELIVERY_PRICE - discount - bonus_spent)

    if bonus_spent and not spend_bonus(user_id, bonus_spent):
        await query.edit_message_text("Bonus yetarli emas. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    decrease_stock_for_cart(user_id)

    order_id = create_order(
        user_id=user_id,
        pickup_address=order_data["pickup_address"],
        delivery_address=order_data["delivery_address"],
        description=order_data.get("description") or "",
        phone=order_data["phone"],
        price=total,
        latitude=order_data.get("latitude"),
        longitude=order_data.get("longitude"),
        delivery_slot=order_data.get("delivery_slot") or "",
        promo_code=order_data.get("promo_code") or "",
        discount=discount,
        bonus_spent=bonus_spent,
        subtotal=subtotal,
    )
    save_order_items(order_id, user_id)
    clear_cart(user_id)
    context.user_data.pop("order", None)

    await query.edit_message_text(
        f"✅ Buyurtma qabul qilindi!\nBuyurtma raqami: #{order_id}\n"
        f"💰 Jami: {total:,} so'm"
    )
    await query.message.reply_text(
        "To'lov usulini tanlang:",
        reply_markup=payment_keyboard(order_id),
    )

    order = get_order(order_id)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🆕 Yangi buyurtma #{order_id}\n\n{format_order(order)}",
                reply_markup=admin_order_keyboard(order_id),
            )
            if order["latitude"] is not None and order["longitude"] is not None:
                await context.bot.send_location(
                    chat_id=admin_id,
                    latitude=order["latitude"],
                    longitude=order["longitude"],
                )
        except Exception:
            pass

    return ConversationHandler.END


async def cancel_order_flow(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data.pop("order", None)
    await update.message.reply_text(
        "Buyurtma bekor qilindi. Savatcha saqlanib qoldi.",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    return ConversationHandler.END


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    orders = get_user_orders(update.effective_user.id)
    if not orders:
        await update.message.reply_text(
            f"📋 <b>Buyurtmalar</b>\n"
            f"{format_now_html()}\n\n"
            f"Sizda hali buyurtmalar yo‘q.\n"
            f"Katalogdan tanlab berishingiz mumkin!",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        f"📋 <b>Buyurtmalaringiz</b>\n{format_now_html()}",
        parse_mode="HTML",
    )
    for order in orders:
        payment = order["payment_status"]
        can_pay = payment in {"pending", "rejected"}
        can_cancel = order["status"] in {"new", "accepted"}
        await update.message.reply_text(
            format_order(order),
            reply_markup=order_actions_keyboard(order["id"], can_pay, can_cancel),
        )
        if can_pay:
            await update.message.reply_text(
                "To'lov usuli:",
                reply_markup=payment_keyboard(order["id"]),
            )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bu bo'lim faqat adminlar uchun.")
        return

    await update.message.reply_text(
        f"🛠 <b>Admin panel</b>\n"
        f"{format_now_html()}\n\n"
        "🛒 Do'kon — mijoz ko‘rinishi\n"
        "📷 Skaner — kod bilan savatga",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Ruxsat yo'q.")
        return

    action = query.data.split(":", 1)[1]

    if action == "menu":
        await query.edit_message_text(
            f"🛠 <b>Admin panel</b>\n{format_now_html()}",
            reply_markup=admin_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    if action == "stats":
        stats = get_stats()
        text = (
            "📊 <b>Statistika</b>\n"
            f"{format_now_html()}\n\n"
            f"👥 Foydalanuvchilar: {stats['total_users']}\n"
            f"📦 Jami buyurtmalar: {stats['total_orders']}\n"
            f"🆕 Yangi: {stats['new_orders']}\n"
            f"🚚 Faol: {stats['active_orders']}\n"
            f"✅ Yetkazilgan: {stats['delivered_orders']}\n"
            f"💰 Jami savdo: {stats['revenue_sum']:,} so'm\n"
            f"📅 Bugun: {stats['today_orders']} ta — {stats['today_sum']:,} so'm"
        )
        await edit_or_reply(
            query, text, reply_markup=admin_menu_keyboard(), parse_mode="HTML"
        )
        return

    if action == "report":
        from bot.extras import report_callback

        await report_callback(update, context)
        return

    if action == "export":
        from bot.extras import export_csv_callback

        await export_csv_callback(update, context)
        return

    if action == "products":
        await show_admin_products_list(update, context)
        return

    if action == "new":
        orders = get_orders_by_status("new")
    elif action == "active":
        orders = [
            *get_orders_by_status("accepted"),
            *get_orders_by_status("in_delivery"),
        ]
    else:
        await query.edit_message_text(
            "🛠 Admin panel",
            reply_markup=admin_menu_keyboard(),
        )
        return

    if not orders:
        await query.edit_message_text(
            "Buyurtmalar topilmadi.",
            reply_markup=admin_menu_keyboard(),
        )
        return

    await query.edit_message_text(f"Topildi: {len(orders)} ta buyurtma")
    for order in orders[:5]:
        await query.message.reply_text(
            format_order(order),
            reply_markup=admin_order_keyboard(order["id"]),
        )


async def show_admin_products_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    products = get_products(active_only=False)
    if not products:
        text = "🛍 Mahsulotlar yo'q.\nYangi qo'shing 👇"
        markup = admin_products_keyboard()
    else:
        no_photo = 0
        for p in products:
            try:
                if not p["image_file_id"]:
                    no_photo += 1
            except (KeyError, IndexError):
                no_photo += 1
        cats = {
            (p["category_name"] or "Toifasiz")
            for p in products
        }
        text = (
            f"🛍 <b>Mahsulotlar spiskasi</b>\n"
            f"📦 Jami: <b>{len(products)}</b> ta · "
            f"📁 Toifa: <b>{len(cats)}</b> ta\n"
            f"🖼 Rasmli: <b>{len(products) - no_photo}</b> · "
            f"📷· Rasmsiz: <b>{no_photo}</b>\n\n"
            f"<b>━━ 📁 TOIFA ━━</b> — toifani ochish\n"
            f"　　✅🖼 mahsulot — tahrirlash / rasm"
        )
        markup = admin_all_products_list_keyboard(products)

    if query:
        await query.edit_message_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
    elif update.message:
        await update.message.reply_text(
            text, reply_markup=markup, parse_mode="HTML"
        )


async def show_admin_categories(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    categories = get_categories(active_only=False)
    if not categories:
        text = "Toifalar yo'q. Yangi qo'shing."
        markup = admin_products_keyboard()
    else:
        with_counts = [
            (
                category,
                len(get_products(active_only=False, category_id=category["id"])),
            )
            for category in categories
        ]
        text = (
            f"🗂 Toifalar ({len(categories)} ta)\n"
            "Keraklisini tanlang:"
        )
        markup = admin_categories_list_keyboard(with_counts)

    if query:
        await query.edit_message_text(text, reply_markup=markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=markup)


async def show_admin_category_products(
    update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int
) -> None:
    query = update.callback_query
    category = get_category(category_id)
    if not category:
        await query.answer("Toifa topilmadi.", show_alert=True)
        return

    products = get_products(active_only=False, category_id=category_id)
    text = (
        f"🗂 <b>{category['name']}</b>\n"
        f"Mahsulotlar: {len(products)} ta\n\n"
        "Mahsulotni tanlang yoki yangisini qo'shing."
    )
    await query.edit_message_text(
        text,
        reply_markup=admin_category_products_list_keyboard(category_id, products),
        parse_mode="HTML",
    )


async def admin_product_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int | None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Ruxsat yo'q.")
        return ConversationHandler.END

    parts = query.data.split(":")
    action = parts[1]

    if action == "list":
        await show_admin_products_list(update, context)
        return None

    if action == "cats":
        await show_admin_categories(update, context)
        return None

    if action == "viewcat":
        category_id = int(parts[2])
        await show_admin_category_products(update, context, category_id)
        return None

    if action == "item":
        product_id = int(parts[2])
        product = get_product_by_id(product_id)
        if not product:
            await query.answer("Mahsulot topilmadi.", show_alert=True)
            return None
        status = "✅ Faol" if product["is_active"] else "🚫 Yashirin"
        category = product["category_name"] or "—"
        cat_id = product["category_id"]
        barcode = ""
        try:
            barcode = product["barcode"] or ""
        except (KeyError, IndexError):
            barcode = ""
        code_line = f"📷 Kod: <code>{barcode}</code>\n" if barcode else "📷 Kod: —\n"
        rows = admin_product_item_keyboard(
            product["id"], bool(product["is_active"])
        ).inline_keyboard
        back_row = [
            [
                InlineKeyboardButton(
                    "⬅️ Spiskaga",
                    callback_data="admin_prod:list",
                )
            ]
        ]
        if cat_id:
            back_row.append(
                [
                    InlineKeyboardButton(
                        "⬅️ Toifaga",
                        callback_data=f"admin_prod:viewcat:{cat_id}",
                    )
                ]
            )
        markup = InlineKeyboardMarkup(list(rows) + back_row)
        await query.edit_message_text(
            f"#{product['id']} <b>{product['name']}</b>\n"
            f"🗂 {category}\n"
            f"✨ {money_html(product['price'])} ✨\n"
            f"{code_line}"
            f"📝 {product['description'] or '—'}\n"
            f"Holat: {status}",
            reply_markup=markup,
            parse_mode="HTML",
        )
        return None

    if action == "addcat":
        # ConversationHandler ga bog'liq emas — ishonchliroq
        context.user_data["awaiting_admin"] = "category_name"
        context.user_data.pop("admin_product", None)
        await query.edit_message_text("🗂 Yangi toifa qo'shish")
        await query.message.reply_text(
            "🗂 Toifa nomini yozing.\n\n"
            "💡 Oldiga emoji qo‘ying — ro‘yxatda chiroyli chiqadi:\n"
            "• <code>🍎 Meva</code>\n"
            "• <code>🍦 Muzqaymoqlar</code>\n"
            "• <code>💄 Parfyumeriya</code>\n"
            "• <code>✏️ Kantselyariya</code>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML",
        )
        return None

    if action == "delcat":
        category_id = int(parts[2])
        category = get_category(category_id)
        if not category:
            await query.answer("Toifa topilmadi.", show_alert=True)
            return None
        delete_category(category_id)
        await query.edit_message_text(
            f"🗑 «{category['name']}» toifasi o'chirildi.",
            reply_markup=admin_products_keyboard(),
        )
        return None

    if action == "addin":
        # Toifa ichidan yangi mahsulot — avval skaner / kod
        category_id = int(parts[2])
        category = get_category(category_id)
        if not category:
            await query.answer("Toifa topilmadi.", show_alert=True)
            return ConversationHandler.END
        context.user_data["admin_product"] = {"category_id": category_id}
        await query.edit_message_text(
            f"➕ «{category['name']}» toifasiga yangi mahsulot"
        )
        await query.message.reply_text(
            "Avval shtrix-kodni skanerlang.\n\n"
            "1) «📷 Kodni skanerlash» — kamera\n"
            "2) yoki kodni qo‘lda yozing\n"
            "3) kod bo‘lmasa «⏭ O'tkazib yuborish»",
            reply_markup=new_product_barcode_keyboard(),
        )
        return ProductAdminState.BARCODE

    if action == "add":
        context.user_data["admin_product"] = {}
        await query.edit_message_text("Yangi mahsulot qo'shish...")
        await query.message.reply_text(
            "Avval shtrix-kodni skanerlang.\n\n"
            "1) «📷 Kodni skanerlash» — kamera\n"
            "2) yoki kodni qo‘lda yozing\n"
            "3) kod bo‘lmasa «⏭ O'tkazib yuborish»",
            reply_markup=new_product_barcode_keyboard(),
        )
        return ProductAdminState.BARCODE

    if action == "setcat":
        category_id = int(parts[2])
        context.user_data.setdefault("admin_product", {})["category_id"] = category_id
        category = get_category(category_id)
        await query.edit_message_text(
            f"Toifa: {category['name'] if category else category_id}"
        )
        await query.message.reply_text(
            "💰 Narxni yozing (faqat raqam, so'm):",
            reply_markup=cancel_keyboard(),
        )
        return ProductAdminState.PRICE

    if action == "price":
        product_id = int(parts[2])
        product = get_product_by_id(product_id)
        if not product:
            await query.answer("Mahsulot topilmadi.", show_alert=True)
            return ConversationHandler.END
        context.user_data["admin_product"] = {"id": product_id, "mode": "edit_price"}
        await query.message.reply_text(
            f"«{product['name']}» uchun yangi asosiy narxni yozing (so'm):\n"
            f"Hozirgi: {product['price']:,} so'm\n"
            "(O'lchamlar bo'lsa, ular alohida narxda qoladi)",
            reply_markup=cancel_keyboard(),
        )
        return ProductAdminState.EDIT_PRICE

    if action == "size":
        product_id = int(parts[2])
        product = get_product_by_id(product_id)
        if not product:
            await query.answer("Mahsulot topilmadi.", show_alert=True)
            return ConversationHandler.END
        variants = get_variants(product_id, active_only=False)
        if variants:
            await query.message.reply_text(
                f"«{product['name']}» o'lchamlari:"
            )
            for variant in variants:
                await query.message.reply_text(
                    f"• {variant['name']} — {variant['price']:,} so'm",
                    reply_markup=admin_variant_item_keyboard(variant["id"]),
                )
        context.user_data["admin_product"] = {
            "id": product_id,
            "mode": "add_size",
            "product_name": product["name"],
        }
        await query.message.reply_text(
            f"«{product['name']}» uchun yangi o'lcham nomini yozing:\n"
            "Masalan: 0.5L yoki 1.5L",
            reply_markup=cancel_keyboard(),
        )
        return ProductAdminState.SIZE_NAME

    if action == "delsize":
        variant_id = int(parts[2])
        delete_variant(variant_id)
        await query.edit_message_text("🗑 O'lcham o'chirildi.")
        return None

    if action == "toggle":
        product_id = int(parts[2])
        product = get_product_by_id(product_id)
        if not product:
            await query.answer("Mahsulot topilmadi.", show_alert=True)
            return None
        new_active = not bool(product["is_active"])
        set_product_active(product_id, new_active)
        product = get_product_by_id(product_id)
        status = "✅ Faol" if product["is_active"] else "🚫 Yashirin"
        category = product["category_name"] or "—"
        cat_id = product["category_id"]
        rows = admin_product_item_keyboard(
            product["id"], bool(product["is_active"])
        ).inline_keyboard
        back_row = (
            [
                [
                    InlineKeyboardButton(
                        "⬅️ Toifaga",
                        callback_data=f"admin_prod:viewcat:{cat_id}",
                    )
                ]
            ]
            if cat_id
            else []
        )
        await query.edit_message_text(
            f"#{product['id']} <b>{product['name']}</b>\n"
            f"🗂 {category}\n"
            f"✨ {money_html(product['price'])} ✨\n"
            f"📝 {product['description'] or '—'}\n"
            f"Holat: {status}",
            reply_markup=InlineKeyboardMarkup(list(rows) + back_row),
            parse_mode="HTML",
        )
        return None

    if action == "del":
        product_id = int(parts[2])
        product = get_product_by_id(product_id)
        if not product:
            await query.answer("Mahsulot topilmadi.", show_alert=True)
            return None
        cat_id = product["category_id"]
        name = product["name"]
        delete_product(product_id)
        if cat_id:
            await query.answer(f"«{name}» o'chirildi")
            await show_admin_category_products(update, context, cat_id)
        else:
            await query.edit_message_text(f"🗑 «{name}» o'chirildi.")
        return None

    return None


def _barcode_payload_code(payload: dict) -> str:
    action = payload.get("action") or "scan"
    if action == "scan_many":
        codes = [
            str(x).strip() for x in (payload.get("barcodes") or []) if str(x).strip()
        ]
        return codes[0] if codes else ""
    return str(payload.get("barcode") or "").strip()


async def _ask_new_product_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    msg = update.effective_message
    data = context.user_data.setdefault("admin_product", {})
    suggested = data.get("suggested_name")
    if suggested:
        await msg.reply_text(
            f"Nom topildi: <b>{suggested}</b>\nQabul qilasizmi yoki boshqa nom yozasizmi?",
            parse_mode="HTML",
            reply_markup=suggested_name_keyboard(suggested),
        )
    else:
        await msg.reply_text(
            "🛍 Mahsulot nomini yozing:",
            reply_markup=cancel_keyboard(),
        )
    return ProductAdminState.NAME


async def _apply_new_product_barcode(
    update: Update, context: ContextTypes.DEFAULT_TYPE, barcode: str | None
) -> int:
    msg = update.effective_message
    data = context.user_data.setdefault("admin_product", {})
    if barcode:
        existing = get_product_by_barcode(barcode)
        if existing:
            await msg.reply_text(
                f"❌ Bu kod allaqachon bor: #{existing['id']} {existing['name']}\n"
                "Boshqa kod skanerlang yoki «⏭ O'tkazib yuborish».",
                reply_markup=new_product_barcode_keyboard(),
            )
            return ProductAdminState.BARCODE
        data["barcode"] = barcode
        info = lookup_barcode_name(barcode)
        if info and info.get("name"):
            data["suggested_name"] = info["name"]
        await msg.reply_text(f"✅ Kod: `{barcode}`", parse_mode="Markdown")
    else:
        data.pop("barcode", None)
        data.pop("suggested_name", None)
    return await _ask_new_product_name(update, context)


async def admin_product_barcode(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if _is_cancel_text(text):
        return await cancel_product_admin(update, context)
    if _is_skip_text(text):
        return await _apply_new_product_barcode(update, context, None)
    return await _apply_new_product_barcode(update, context, text)


async def admin_product_barcode_webapp(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    msg = update.effective_message
    if not msg or not msg.web_app_data:
        return ProductAdminState.BARCODE
    try:
        payload = json.loads(msg.web_app_data.data)
    except json.JSONDecodeError:
        await msg.reply_text(
            "Skaner o‘qimadi. Qayta urinib ko‘ring.",
            reply_markup=new_product_barcode_keyboard(),
        )
        return ProductAdminState.BARCODE
    code = _barcode_payload_code(payload)
    if not code:
        await msg.reply_text(
            "Kod bo‘sh. Qayta skanerlang.",
            reply_markup=new_product_barcode_keyboard(),
        )
        return ProductAdminState.BARCODE
    return await _apply_new_product_barcode(update, context, code)


async def admin_product_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)
    if text == "✏️ Boshqa nom yozaman":
        await update.message.reply_text(
            "🛍 Mahsulot nomini yozing:",
            reply_markup=cancel_keyboard(),
        )
        return ProductAdminState.NAME
    if text.startswith("✅ "):
        suggested = (context.user_data.get("admin_product") or {}).get("suggested_name")
        text = suggested or text[2:].strip()

    context.user_data.setdefault("admin_product", {})["name"] = text
    context.user_data["admin_product"].pop("suggested_name", None)
    # Toifa ichidan qo'shilayotgan bo'lsa — toifa tanlashni o'tkazib yuborish
    preset_cat = context.user_data["admin_product"].get("category_id")
    if preset_cat:
        category = get_category(preset_cat)
        await update.message.reply_text(
            f"🗂 Toifa: {category['name'] if category else preset_cat}\n"
            "💰 Narxni yozing (faqat raqam, so'm):",
            reply_markup=cancel_keyboard(),
        )
        return ProductAdminState.PRICE

    categories = get_categories()
    if not categories:
        await update.message.reply_text(
            "Avval toifa yarating (Admin → Mahsulotlar → Yangi toifa).",
            reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
        )
        context.user_data.pop("admin_product", None)
        return ConversationHandler.END

    await update.message.reply_text(
        "🗂 Toifani tanlang:",
        reply_markup=category_pick_keyboard(categories),
    )
    return ProductAdminState.PICK_CATEGORY


def _is_skip_text(text: str) -> bool:
    """«O'tkazib yuborish» tugmasi / matnini aniqlash (emoji variantlari bilan)."""
    normalized = (text or "").strip().casefold()
    return (
        "tkazib yuborish" in normalized
        or normalized in {"-", "skip", "o'tkazib", "otkazib"}
    )


def _is_cancel_text(text: str) -> bool:
    normalized = (text or "").strip().casefold()
    return normalized.startswith("❌") or "bekor" in normalized


async def admin_product_price(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    raw = update.message.text or ""
    if _is_cancel_text(raw):
        return await cancel_product_admin(update, context)

    price = parse_price_sum(raw)
    if price is None:
        await update.message.reply_text(
            "Narxni shunday yozing:\n"
            "• <code>12000</code>\n"
            "• yoki <code>15000 so'm</code>\n"
            "• yoki <code>15 000</code>",
            parse_mode="HTML",
        )
        return ProductAdminState.PRICE

    context.user_data.setdefault("admin_product", {})["price"] = price
    # Conversation uzilsa ham izoh bosqichi ishlasin
    context.user_data["awaiting_admin"] = "product_description"
    await update.message.reply_text(
        f"✅ Narx: {price:,} so'm\n\n"
        "📝 Izoh yozing yoki «O'tkazib yuborish» ni bosing:",
        reply_markup=ReplyKeyboardMarkup(
            [["⏭ O'tkazib yuborish"], ["❌ Bekor qilish"]],
            resize_keyboard=True,
        ),
    )
    return ProductAdminState.DESCRIPTION


async def admin_product_description(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if _is_cancel_text(text):
        return await cancel_product_admin(update, context)

    description = "" if _is_skip_text(text) else text
    data = context.user_data.get("admin_product") or {}
    if not data.get("name") or data.get("price") is None:
        context.user_data.pop("awaiting_admin", None)
        await update.message.reply_text(
            "⚠️ Ma'lumot yo'qaldi. Mahsulotni qaytadan qo'shing.",
            reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
        )
        return ConversationHandler.END

    try:
        product_id = create_product(
            data["name"],
            int(data["price"]),
            description,
            data.get("category_id"),
            barcode=data.get("barcode"),
        )
    except Exception as exc:
        context.user_data["awaiting_admin"] = "product_description"
        await update.message.reply_text(
            f"❌ Mahsulot saqlanmadi: {exc}\nQayta urinib ko'ring yoki izoh yozing:"
        )
        return ProductAdminState.DESCRIPTION

    category = get_category(data["category_id"]) if data.get("category_id") else None
    context.user_data.pop("admin_product", None)
    context.user_data.pop("awaiting_admin", None)
    code = data.get("barcode") or "—"

    await update.message.reply_text(
        f"✅ Mahsulot qo'shildi!\n"
        f"#{product_id} {data['name']} — {data['price']:,} so'm\n"
        f"🗂 {category['name'] if category else '—'}\n"
        f"📷 Kod: {code}\n\n"
        f"🖼 Endi rasm qo‘shing — mijozlar ko‘proq sotib oladi!",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    await update.message.reply_text(
        "Rasm qo‘shish yoki spiskaga qaytish:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🖼 Rasm qo‘shish",
                        callback_data=f"admin_prod:photo:{product_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📋 Spiska", callback_data="admin_prod:list"
                    )
                ],
            ]
        ),
    )
    return ConversationHandler.END


async def admin_category_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    context.user_data.pop("awaiting_admin", None)

    if text == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    if len(text) < 2:
        context.user_data["awaiting_admin"] = "category_name"
        await update.message.reply_text("Toifa nomi juda qisqa. Qayta yozing:")
        return ProductAdminState.CATEGORY_NAME

    try:
        category_id = create_category(text)
    except Exception as exc:
        context.user_data["awaiting_admin"] = "category_name"
        await update.message.reply_text(
            f"❌ Toifa qo'shilmadi: {exc}\nBoshqa nom yozing:"
        )
        return ProductAdminState.CATEGORY_NAME

    await update.message.reply_text(
        f"✅ Toifa qo'shildi!\n#{category_id} · {text}",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    await show_admin_categories(update, context)
    return ConversationHandler.END


async def admin_awaiting_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """ConversationHandler ishlamasa ham admin matnini qabul qilish."""
    from telegram.ext import ApplicationHandlerStop

    if not update.message or not is_admin(update.effective_user.id):
        return

    mode = context.user_data.get("awaiting_admin")
    text = update.message.text or ""
    draft = context.user_data.get("admin_product") or {}
    has_product_draft = bool(draft.get("name") and draft.get("price") is not None)

    # Stuck recovery: izoh bosqichida conversation uzilgan bo'lsa
    if mode not in {"category_name", "product_description"}:
        if has_product_draft and (_is_skip_text(text) or _is_cancel_text(text)):
            mode = "product_description"
        else:
            return

    if mode == "category_name":
        await admin_category_name(update, context)
    else:
        await admin_product_description(update, context)
    raise ApplicationHandlerStop


async def admin_size_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    context.user_data.setdefault("admin_product", {})["size_name"] = text
    await update.message.reply_text(
        f"💰 «{text}» uchun narxni yozing (so'm):",
        reply_markup=cancel_keyboard(),
    )
    return ProductAdminState.SIZE_PRICE


async def admin_size_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text or ""
    if raw.strip() == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    price = parse_price_sum(raw)
    if price is None:
        await update.message.reply_text("Narxni yozing. Masalan: 9000 yoki 9000 so'm")
        return ProductAdminState.SIZE_PRICE

    data = context.user_data.get("admin_product", {})
    product_id = data.get("id")
    size_name = data.get("size_name")
    if not product_id or not size_name:
        await update.message.reply_text("Xatolik. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    create_variant(product_id, size_name, price)
    product_name = data.get("product_name", "Mahsulot")
    context.user_data.pop("admin_product", None)

    await update.message.reply_text(
        f"✅ O'lcham qo'shildi!\n"
        f"{product_name} — {size_name}: {price:,} so'm",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    return ConversationHandler.END


async def admin_edit_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text or ""
    if raw.strip() == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    price = parse_price_sum(raw)
    if price is None:
        await update.message.reply_text("Narxni yozing. Masalan: 15000 yoki 15000 so'm")
        return ProductAdminState.EDIT_PRICE

    product_id = context.user_data.get("admin_product", {}).get("id")
    if not product_id:
        await update.message.reply_text("Xatolik. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    update_product_price(product_id, price)
    product = get_product_by_id(product_id)
    context.user_data.pop("admin_product", None)

    await update.message.reply_text(
        f"✅ Narx yangilandi!\n"
        f"{product['name']} — {product['price']:,} so'm",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    return ConversationHandler.END


async def cancel_product_admin(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data.pop("admin_product", None)
    context.user_data.pop("awaiting_admin", None)
    await update.message.reply_text(
        "Bekor qilindi.",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    return ConversationHandler.END


async def admin_status_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Ruxsat yo'q.")
        return

    _, order_id_str, status = query.data.split(":", 2)
    order_id = int(order_id_str)
    update_order_status(order_id, status)

    order = get_order(order_id)
    await query.edit_message_text(
        format_order(order),
        reply_markup=admin_order_keyboard(order_id),
    )

    try:
        text = (
            f"🔔 Buyurtma #{order_id} holati yangilandi:\n"
            f"{format_order(order)}"
        )
        markup = None
        if order["payment_status"] in {"pending", "rejected"}:
            text += "\n\nTo'lov qilish uchun pastdagi tugmalardan foydalaning:"
            markup = payment_keyboard(order_id)
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=text,
            reply_markup=markup,
        )
    except Exception:
        pass


async def admin_delete_order_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Ruxsat yo'q.")
        return

    data = query.data
    if data.startswith("admin_del_order_yes:"):
        order_id = int(data.split(":")[1])
        if delete_order(order_id):
            await query.edit_message_text(
                f"🗑 Buyurtma #{order_id} ma'lumotlari o'chirildi."
            )
        else:
            await query.edit_message_text("Buyurtma topilmadi yoki allaqachon o'chirilgan.")
        return

    if data.startswith("admin_del_order_no:"):
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        if not order:
            await query.edit_message_text("Buyurtma topilmadi.")
            return
        await query.edit_message_text(
            format_order(order),
            reply_markup=admin_order_keyboard(order_id),
        )
        return

    # admin_del_order:{id} — tasdiq
    order_id = int(data.split(":")[1])
    order = get_order(order_id)
    if not order:
        await query.edit_message_text("Buyurtma topilmadi.")
        return
    await query.edit_message_text(
        f"⚠️ Buyurtma #{order_id} ni o'chirasizmi?\n"
        f"Bu amalni qaytarib bo'lmaydi.\n\n"
        f"{format_order(order)}",
        reply_markup=admin_delete_order_confirm_keyboard(order_id),
    )


async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pay_menu:"):
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        if not order:
            await query.edit_message_text("Buyurtma topilmadi.")
            return
        await query.edit_message_text(
            f"Buyurtma #{order_id}\n💰 Summa: {order['price']:,} so'm\n\n"
            "To'lov usulini tanlang:",
            reply_markup=payment_keyboard(order_id),
        )
        return

    if data.startswith("pay_cash:"):
        order_id = int(data.split(":")[1])
        update_payment_status(order_id, "cash")
        order = get_order(order_id)
        if order:
            points = max(1, int(order["price"] * BONUS_PERCENT / 100))
            add_bonus(order["user_id"], points)
        await query.edit_message_text(
            f"💵 Buyurtma #{order_id} uchun naqd to'lov belgilandi.\n"
            "Kuryer yetib kelganda to'laysiz."
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"💵 Buyurtma #{order_id}: mijoz naqd to'lashni tanladi.",
                )
            except Exception:
                pass
        return

    if data.startswith("pay_card:"):
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        if not order:
            await query.edit_message_text("Buyurtma topilmadi.")
            return

        if not card_payment_enabled():
            await query.edit_message_text(
                "Karta ma'lumotlari hali sozlanmagan.\n"
                "Iltimos, naqd to'lovni tanlang yoki admin bilan bog'laning.",
                reply_markup=payment_keyboard(order_id),
            )
            return

        await query.edit_message_text(
            f"💳 Kartaga o'tkazish\n\n"
            f"Buyurtma: #{order_id}\n"
            f"Summa: {order['price']:,} so'm\n\n"
            f"Karta: `{CARD_NUMBER}`\n"
            f"Egasi: {CARD_HOLDER}\n\n"
            "Pul o'tkazgach «Men to'lov qildim» tugmasini bosing.\n"
            "Izohga buyurtma raqamini yozing.",
            reply_markup=card_paid_keyboard(order_id),
            parse_mode="Markdown",
        )
        return

    if data.startswith("pay_done:"):
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        if not order:
            await query.edit_message_text("Buyurtma topilmadi.")
            return

        update_payment_status(order_id, "card_waiting")
        await query.edit_message_text(
            f"✅ Bildirishnoma yuborildi!\n"
            f"Buyurtma #{order_id} to'lovi tekshirilmoqda.\n"
            "Admin tasdiqlagach xabar olasiz."
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"💳 To'lov tekshiruvi\n\n"
                    f"Buyurtma #{order_id}\n"
                    f"Mijoz: {query.from_user.full_name}\n"
                    f"Summa: {order['price']:,} so'm\n\n"
                    f"{format_order(order)}",
                    reply_markup=admin_payment_keyboard(order_id),
                )
            except Exception:
                pass
        return

    if data.startswith("pay_confirm:"):
        if not is_admin(query.from_user.id):
            await query.edit_message_text("Ruxsat yo'q.")
            return
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        if not order:
            await query.edit_message_text("Buyurtma topilmadi.")
            return
        update_payment_status(order_id, "paid")
        order = get_order(order_id)
        if order:
            points = max(1, int(order["price"] * BONUS_PERCENT / 100))
            add_bonus(order["user_id"], points)
        await query.edit_message_text(
            f"✅ Buyurtma #{order_id} to'lovi tasdiqlandi.\n\n{format_order(get_order(order_id))}"
        )
        try:
            await context.bot.send_message(
                order["user_id"],
                f"✅ To'lovingiz tasdiqlandi!\nBuyurtma #{order_id} qabul qilindi.",
            )
        except Exception:
            pass
        return

    if data.startswith("pay_reject:"):
        if not is_admin(query.from_user.id):
            await query.edit_message_text("Ruxsat yo'q.")
            return
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        if not order:
            await query.edit_message_text("Buyurtma topilmadi.")
            return
        update_payment_status(order_id, "rejected")
        await query.edit_message_text(
            f"❌ Buyurtma #{order_id} to'lovi rad etildi.\n\n{format_order(get_order(order_id))}"
        )
        try:
            await context.bot.send_message(
                order["user_id"],
                f"❌ Buyurtma #{order_id} to'lovi tasdiqlanmadi.\n"
                "Qayta to'lov qiling yoki admin bilan bog'laning.",
                reply_markup=payment_keyboard(order_id),
            )
        except Exception:
            pass
        return

    if data.startswith("pay_online:") or data.startswith("pay:"):
        order_id = int(data.split(":")[1])
        order = get_order(order_id)
        if not order:
            await query.edit_message_text("Buyurtma topilmadi.")
            return

        if not online_payment_enabled():
            await query.edit_message_text(
                "Telegram onlayn to'lov hozircha yoqilmagan.\n"
                "Kartaga o'tkazish yoki naqd to'lovni tanlang.",
                reply_markup=payment_keyboard(order_id),
            )
            return

        from telegram import LabeledPrice

        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"Buyurtma #{order_id}",
            description=f"{SHOP_NAME} buyurtma to'lovi",
            payload=f"order_{order_id}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="UZS",
            prices=[LabeledPrice("Buyurtma", order["price"])],
        )
        return



async def precheckout_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    payload = update.message.successful_payment.invoice_payload
    order_id = int(payload.replace("order_", ""))
    update_payment_status(order_id, "paid")
    order = get_order(order_id)
    if order:
        points = max(1, int(order["price"] * BONUS_PERCENT / 100))
        add_bonus(order["user_id"], points)

    await update.message.reply_text(
        f"✅ To'lov qabul qilindi!\nBuyurtma #{order_id} uchun rahmat."
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"💳 Buyurtma #{order_id} uchun to'lov qabul qilindi.",
            )
        except Exception:
            pass


def build_product_admin_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                admin_product_callback,
                pattern=r"^admin_prod:(add|addin:\d+|price:\d+|size:\d+|setcat:\d+)$",
            ),
        ],
        states={
            ProductAdminState.BARCODE: [
                MessageHandler(
                    filters.StatusUpdate.WEB_APP_DATA, admin_product_barcode_webapp
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_barcode),
            ],
            ProductAdminState.NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_name)
            ],
            ProductAdminState.PICK_CATEGORY: [
                CallbackQueryHandler(
                    admin_product_callback, pattern=r"^admin_prod:setcat:\d+$"
                )
            ],
            ProductAdminState.PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_product_price)
            ],
            ProductAdminState.DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, admin_product_description
                )
            ],
            ProductAdminState.EDIT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_price)
            ],
            ProductAdminState.CATEGORY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_category_name)
            ],
            ProductAdminState.SIZE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_size_name)
            ],
            ProductAdminState.SIZE_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_size_price)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_product_admin),
            CommandHandler("cancel", cancel_product_admin),
        ],
        allow_reentry=True,
    )


def build_order_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_checkout, pattern=r"^cart:checkout$"),
        ],
        states={
            OrderState.DELIVERY: [
                MessageHandler(
                    filters.LOCATION | (filters.TEXT & ~filters.COMMAND),
                    receive_delivery,
                )
            ],
            OrderState.SLOT: [
                CallbackQueryHandler(receive_slot, pattern=r"^(slot:\d+|order:cancel)$")
            ],
            OrderState.PROMO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_promo_text),
                CallbackQueryHandler(
                    receive_promo_callback, pattern=r"^(promo:skip|order:cancel)$"
                ),
            ],
            OrderState.BONUS: [
                CallbackQueryHandler(receive_bonus_callback, pattern=r"^bonus:(use|skip)$")
            ],
            OrderState.NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_note)
            ],
            OrderState.PHONE: [
                MessageHandler(
                    filters.CONTACT | (filters.TEXT & ~filters.COMMAND),
                    receive_phone,
                )
            ],
            OrderState.CONFIRM: [
                CallbackQueryHandler(confirm_order_callback, pattern=r"^order:")
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel_order_flow),
            CommandHandler("cancel", cancel_order_flow),
        ],
        allow_reentry=True,
    )
