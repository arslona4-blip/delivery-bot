from enum import IntEnum

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import (
    ADMIN_IDS,
    BONUS_PERCENT,
    CARD_HOLDER,
    CARD_NUMBER,
    COURIER_IDS,
    DELIVERY_PRICE,
    DELIVERY_SLOTS,
    MIN_ORDER_AMOUNT,
    PAYMENT_PROVIDER_TOKEN,
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
    delete_product,
    delete_variant,
    format_cart,
    format_order,
    get_bonus,
    get_cart,
    get_cart_totals,
    get_categories,
    get_category,
    get_order,
    get_orders_by_status,
    get_product,
    get_product_by_id,
    get_products,
    get_stats,
    get_user,
    get_user_orders,
    get_variants,
    is_favorite,
    product_display_price,
    remove_from_cart,
    save_order_items,
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
    admin_category_item_keyboard,
    admin_menu_keyboard,
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
    favorite_toggle_keyboard,
    location_keyboard,
    main_menu_keyboard,
    order_actions_keyboard,
    payment_keyboard,
    product_keyboard,
    promo_keyboard,
)


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


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def menu_for(user_id: int):
    return main_menu_keyboard(
        is_admin(user_id),
        user_id in COURIER_IDS or is_admin(user_id),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    upsert_user(user.id, user.full_name, user.username)

    await update.message.reply_text(
        f"Assalomu alaykum! 👋\n\n"
        f"«{SHOP_NAME}» do'konining yetkazib berish botiga xush kelibsiz.\n"
        f"📍 Do'kon manzili: {SHOP_ADDRESS}\n\n"
        "Katalogdan mahsulot tanlang, savatchaga qo'shing va buyurtma bering.",
        reply_markup=menu_for(user.id),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📌 Qanday foydalanish:\n"
        "1. «🛍 Katalog» dan mahsulot tanlang\n"
        "2. Savatchaga qo'shing\n"
        "3. «🛒 Savatcha» → Rasmiylashtirish\n"
        "4. «📍 Joylashuv» tugmasini bosing\n\n"
        "Savollar bo'lsa, «📞 Aloqa» bo'limidan foydalaning."
    )


async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"📞 Aloqa — {SHOP_NAME}:\n"
        f"Telegram: {SHOP_TELEGRAM}\n"
        f"Telefon: {SHOP_PHONE}\n"
        f"Ish vaqti: {SHOP_HOURS}"
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
            text = "Hozircha mahsulotlar yo'q."
            if update.callback_query:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        text = f"🛍 {SHOP_NAME} katalogi\nMahsulotni tanlang:"
        markup = catalog_keyboard(products, cart_qty=_cart_qty_by_product(user_id))
    else:
        text = f"🛍 {SHOP_NAME} katalogi\nToifani tanlang:"
        markup = catalog_categories_keyboard(categories)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def show_category_products(
    update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int
) -> None:
    user_id = update.effective_user.id
    category = get_category(category_id)
    products = get_products(category_id=category_id)
    title = category["name"] if category else "Toifa"
    if not products:
        text = f"{title}\n\nBu toifada mahsulot yo'q."
        markup = catalog_categories_keyboard(get_categories())
    else:
        text = f"{title}\nMahsulotni tanlang:"
        markup = catalog_keyboard(
            products,
            category_id,
            cart_qty=_cart_qty_by_product(user_id),
        )

    await update.callback_query.edit_message_text(text, reply_markup=markup)


async def show_cart_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    items = get_cart(user_id)
    text = format_cart(user_id)

    if update.callback_query:
        if not items:
            await update.callback_query.edit_message_text(text)
            return
        await update.callback_query.edit_message_text(
            text, reply_markup=cart_keyboard(items)
        )
    else:
        if not items:
            await update.message.reply_text(
                text, reply_markup=main_menu_keyboard(is_admin(user_id))
            )
            return
        await update.message.reply_text(text, reply_markup=cart_keyboard(items))


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "catalog:list":
        await show_catalog(update, context)
        return

    if query.data.startswith("catalog:cat:"):
        category_id = int(query.data.split(":")[2])
        await show_category_products(update, context, category_id)
        return

    product_id = int(query.data.split(":")[1])
    product = get_product(product_id)
    if not product:
        await query.edit_message_text("Mahsulot topilmadi.")
        return

    variants = get_variants(product_id)
    if not variants:
        add_to_cart(query.from_user.id, product_id, 1, 0)
        count, _ = get_cart_totals(query.from_user.id)
        await query.answer(f"✅ Qo'shildi! Savatchada: {count} ta", show_alert=False)
        if product["category_id"]:
            await show_category_products(update, context, product["category_id"])
        else:
            await show_catalog(update, context)
        return

    category_name = product["category_name"] or "—"
    price_text = product_display_price(product)
    text = (
        f"🛍 {product['name']}\n"
        f"🗂 {category_name}\n"
        f"💰 {price_text}\n"
        f"📝 {product['description'] or '—'}\n\n"
        "O'lchamni tanlang:"
    )
    fav_kb = favorite_toggle_keyboard(
        product_id, is_favorite(query.from_user.id, product_id)
    )
    size_kb = product_keyboard(
        product_id,
        product["category_id"],
        variants,
        cart_variant_qty=_cart_qty_by_variant(query.from_user.id, product_id),
    )
    # merge fav row into size keyboard by sending two messages if photo
    image_id = None
    try:
        image_id = product["image_file_id"]
    except (KeyError, IndexError):
        image_id = None

    if image_id:
        await query.message.reply_photo(photo=image_id, caption=text, reply_markup=size_kb)
        await query.message.reply_text("Sevimli:", reply_markup=fav_kb)
        await query.answer()
    else:
        await query.edit_message_text(text, reply_markup=size_kb)
        await query.message.reply_text("Sevimli:", reply_markup=fav_kb)


async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "cart:view":
        await show_cart_message(update, context)
        return None

    if data == "cart:clear":
        clear_cart(user_id)
        await query.edit_message_text("🛒 Savatcha tozalandi.")
        return None

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
        await query.answer(f"✅ {label} qo'shildi! Savat: {count}")
        if product["category_id"]:
            await show_category_products(update, context, product["category_id"])
        else:
            await show_catalog(update, context)
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
            await query.edit_message_text(text)
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

    text = (
        f"{format_cart(user_id)}\n\n"
        "📍 Qayerga yetkazilsin?\n"
        "Pastdagi «📍 Joylashuv» tugmasini bosing."
    )
    if query:
        await query.edit_message_text("Buyurtma davom etmoqda...")
        await query.message.reply_text(text, reply_markup=location_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=location_keyboard())
    return OrderState.DELIVERY


async def continue_after_delivery(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        "🕒 Yetkazish vaqtini tanlang:",
        reply_markup=delivery_slots_keyboard(DELIVERY_SLOTS),
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

    idx = int(query.data.split(":")[1])
    context.user_data["order"]["delivery_slot"] = DELIVERY_SLOTS[idx]
    await query.edit_message_text(f"🕒 Vaqt: {DELIVERY_SLOTS[idx]}")
    await query.message.reply_text(
        "🏷 Promo kod bo'lsa yozing (masalan BARAKA10)\n"
        "yoki tugmani bosing:",
        reply_markup=promo_keyboard(),
    )
    return OrderState.PROMO


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
    return await ask_bonus(update, context)


async def ask_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    bonus = get_bonus(user_id)
    context.user_data["order"].setdefault("discount", 0)
    context.user_data["order"].setdefault("promo_code", "")
    context.user_data["order"]["bonus_spent"] = 0
    msg = update.effective_message
    await msg.reply_text(
        f"🎁 Bonus balingiz: {bonus:,}\nIshlatasizmi?",
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
    user = get_user(user_id)
    if user and user["phone"]:
        context.user_data["order"]["phone"] = user["phone"]
        return await show_order_summary_message(query.message, query.from_user, context)

    await query.message.reply_text(
        "📱 Telefon raqamingizni yuboring:",
        reply_markup=contact_keyboard(),
    )
    return OrderState.PHONE


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
    if text and text != "📍 Joylashuv":
        context.user_data["order"]["latitude"] = None
        context.user_data["order"]["longitude"] = None
        context.user_data["order"]["delivery_address"] = text
        await update.message.reply_text("✅ Manzil qabul qilindi.")
        return await continue_after_delivery(update, context)

    await update.message.reply_text(
        "📍 «Joylashuv» tugmasini bosing.",
        reply_markup=location_keyboard(),
    )
    return OrderState.DELIVERY


async def receive_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Eski holat uchun: izoh bosqichi o'tkazib yuboriladi
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_order_flow(update, context)
    if text not in {"⏭ O'tkazib yuborish", "O'tkazib yuborish", "-"}:
        context.user_data["order"]["description"] = text
    else:
        context.user_data["order"]["description"] = ""
    return await continue_after_delivery(update, context)


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Bekor qilish":
        return await cancel_order_flow(update, context)

    phone = None
    if update.message.contact:
        phone = update.message.contact.phone_number
    elif update.message.text:
        phone = update.message.text.strip()

    if not phone:
        await update.message.reply_text(
            "Iltimos, telefon raqam yuboring yoki kontakt tugmasidan foydalaning."
        )
        return OrderState.PHONE

    context.user_data["order"]["phone"] = phone
    set_user_phone(update.effective_user.id, phone)
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
        f"🧾 Buyurtma ma'lumotlari:\n\n"
        f"{cart_text}\n"
        f"🕒 Vaqt: {order.get('delivery_slot') or '—'}\n"
        f"🏷 Promo: {order.get('promo_code') or '—'} (−{discount:,})\n"
        f"🎁 Bonus: −{bonus_spent:,}\n"
        f"📍 Qayerdan: {order['pickup_address']}\n"
        f"🏁 Qayerga: {delivery}\n"
        f"📞 Telefon: {order['phone']}\n"
        f"💰 Jami: {total:,} so'm\n\n"
        "Ma'lumotlar to'g'rimi?"
    )
    await message.reply_text(summary, reply_markup=confirm_order_keyboard())
    await message.reply_text("Asosiy menyu:", reply_markup=menu_for(user_id))
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
        await update.message.reply_text("Sizda hali buyurtmalar yo'q.")
        return

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
        "🛠 Admin panel",
        reply_markup=admin_menu_keyboard(),
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
            "🛠 Admin panel",
            reply_markup=admin_menu_keyboard(),
        )
        return

    if action == "stats":
        stats = get_stats()
        await query.edit_message_text(
            "📊 Statistika:\n"
            f"👥 Foydalanuvchilar: {stats['total_users']}\n"
            f"📦 Jami buyurtmalar: {stats['total_orders']}\n"
            f"🆕 Yangi buyurtmalar: {stats['new_orders']}\n"
            f"🚚 Faol buyurtmalar: {stats['active_orders']}",
            reply_markup=admin_menu_keyboard(),
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
        await query.edit_message_text(
            "🛍 Mahsulotlar boshqaruvi",
            reply_markup=admin_products_keyboard(),
        )
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
        await query.edit_message_text(
            "Mahsulotlar yo'q. Yangi qo'shing.",
            reply_markup=admin_products_keyboard(),
        )
        return

    await query.edit_message_text(f"🛍 Jami {len(products)} ta mahsulot:")
    for product in products:
        status = "✅ Faol" if product["is_active"] else "🚫 Yashirin"
        category = product["category_name"] or "—"
        await query.message.reply_text(
            f"#{product['id']} {product['name']}\n"
            f"🗂 {category}\n"
            f"💰 {product['price']:,} so'm\n"
            f"📝 {product['description'] or '—'}\n"
            f"Holat: {status}",
            reply_markup=admin_product_item_keyboard(
                product["id"], bool(product["is_active"])
            ),
        )


async def show_admin_categories(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    categories = get_categories(active_only=False)
    if not categories:
        await query.edit_message_text(
            "Toifalar yo'q. Yangi qo'shing.",
            reply_markup=admin_products_keyboard(),
        )
        return

    await query.edit_message_text(f"🗂 Jami {len(categories)} ta toifa:")
    for category in categories:
        count = len(get_products(active_only=False, category_id=category["id"]))
        await query.message.reply_text(
            f"#{category['id']} {category['name']}\nMahsulotlar: {count} ta",
            reply_markup=admin_category_item_keyboard(category["id"]),
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

    if action == "addcat":
        await query.edit_message_text("Yangi toifa qo'shish...")
        await query.message.reply_text(
            "🗂 Toifa nomini yozing:\nMasalan: Non mahsulotlari",
            reply_markup=cancel_keyboard(),
        )
        return ProductAdminState.CATEGORY_NAME

    if action == "delcat":
        category_id = int(parts[2])
        category = get_category(category_id)
        if not category:
            await query.answer("Toifa topilmadi.", show_alert=True)
            return None
        delete_category(category_id)
        await query.edit_message_text(f"🗑 «{category['name']}» toifasi o'chirildi.")
        return None

    if action == "add":
        context.user_data["admin_product"] = {}
        await query.edit_message_text("Yangi mahsulot qo'shish...")
        await query.message.reply_text(
            "🛍 Mahsulot nomini yozing:",
            reply_markup=cancel_keyboard(),
        )
        return ProductAdminState.NAME

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
        await query.edit_message_text(
            f"#{product['id']} {product['name']}\n"
            f"🗂 {category}\n"
            f"💰 {product['price']:,} so'm\n"
            f"📝 {product['description'] or '—'}\n"
            f"Holat: {status}",
            reply_markup=admin_product_item_keyboard(
                product["id"], bool(product["is_active"])
            ),
        )
        return None

    if action == "del":
        product_id = int(parts[2])
        product = get_product_by_id(product_id)
        if not product:
            await query.answer("Mahsulot topilmadi.", show_alert=True)
            return None
        delete_product(product_id)
        await query.edit_message_text(f"🗑 «{product['name']}» o'chirildi.")
        return None

    return None


async def admin_product_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    context.user_data.setdefault("admin_product", {})["name"] = text
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


async def admin_product_price(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    raw = update.message.text or ""
    if raw.strip() == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    text = raw.strip().replace(" ", "").replace(",", "")
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("To'g'ri narx yozing. Masalan: 12000")
        return ProductAdminState.PRICE

    context.user_data["admin_product"]["price"] = int(text)
    await update.message.reply_text(
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
    if text == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    description = "" if text in {"⏭ O'tkazib yuborish", "O'tkazib yuborish"} else text
    data = context.user_data.get("admin_product", {})
    product_id = create_product(
        data["name"],
        data["price"],
        description,
        data.get("category_id"),
    )
    category = get_category(data["category_id"]) if data.get("category_id") else None
    context.user_data.pop("admin_product", None)

    await update.message.reply_text(
        f"✅ Mahsulot qo'shildi!\n"
        f"#{product_id} {data['name']} — {data['price']:,} so'm\n"
        f"🗂 {category['name'] if category else '—'}",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    await update.message.reply_text(
        "🛍 Mahsulotlar boshqaruvi",
        reply_markup=admin_products_keyboard(),
    )
    return ConversationHandler.END


async def admin_category_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if text == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    if len(text) < 2:
        await update.message.reply_text("Toifa nomi juda qisqa. Qayta yozing:")
        return ProductAdminState.CATEGORY_NAME

    try:
        category_id = create_category(text)
    except Exception:
        await update.message.reply_text(
            "Bu toifa allaqachon bor yoki xato. Boshqa nom yozing:"
        )
        return ProductAdminState.CATEGORY_NAME

    await update.message.reply_text(
        f"✅ Toifa qo'shildi!\n#{category_id} {text}",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    await update.message.reply_text(
        "🛍 Mahsulotlar boshqaruvi",
        reply_markup=admin_products_keyboard(),
    )
    return ConversationHandler.END


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

    text = raw.strip().replace(" ", "").replace(",", "")
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("To'g'ri narx yozing. Masalan: 9000")
        return ProductAdminState.SIZE_PRICE

    data = context.user_data.get("admin_product", {})
    product_id = data.get("id")
    size_name = data.get("size_name")
    if not product_id or not size_name:
        await update.message.reply_text("Xatolik. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    create_variant(product_id, size_name, int(text))
    product_name = data.get("product_name", "Mahsulot")
    context.user_data.pop("admin_product", None)

    await update.message.reply_text(
        f"✅ O'lcham qo'shildi!\n"
        f"{product_name} — {size_name}: {int(text):,} so'm",
        reply_markup=main_menu_keyboard(is_admin(update.effective_user.id)),
    )
    return ConversationHandler.END


async def admin_edit_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().replace(" ", "").replace(",", "")
    if update.message.text == "❌ Bekor qilish":
        return await cancel_product_admin(update, context)

    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("To'g'ri narx yozing. Masalan: 15000")
        return ProductAdminState.EDIT_PRICE

    product_id = context.user_data.get("admin_product", {}).get("id")
    if not product_id:
        await update.message.reply_text("Xatolik. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    update_product_price(product_id, int(text))
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
    await query.edit_message_text(format_order(order))

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
                pattern=r"^admin_prod:(add|addcat|price:\d+|size:\d+|setcat:\d+)$",
            ),
        ],
        states={
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
