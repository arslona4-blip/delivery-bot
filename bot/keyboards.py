from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot.config import MINIAPP_URL, ORDER_STATUS_LABELS


def main_menu_keyboard(is_admin: bool = False, is_courier: bool = False) -> ReplyKeyboardMarkup:
    # Mijoz uchun ixcham menyu — asosiy 4 tugma
    rows = [
        ["🛍 Katalog", "🛒 Savatcha"],
        ["📋 Mening buyurtmalarim", "📞 Aloqa"],
        ["⋯ Ko'proq"],
    ]
    if MINIAPP_URL:
        rows.insert(0, [KeyboardButton("📷 Skaner", web_app=WebAppInfo(url=f"{MINIAPP_URL}/scan.html?mode=sale"))])
    staff_row = []
    if is_admin:
        staff_row.append("🛠 Admin panel")
    if is_courier:
        staff_row.append("🚴 Kuryer panel")
    if staff_row:
        rows.append(staff_row)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def scan_sale_keyboard() -> ReplyKeyboardMarkup | None:
    if not MINIAPP_URL:
        return None
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "📷 Yana skan",
                    web_app=WebAppInfo(url=f"{MINIAPP_URL}/scan.html?mode=sale"),
                )
            ],
            ["🛒 Savatcha", "🛍 Katalog"],
            ["⬅️ Asosiy menyu"],
        ],
        resize_keyboard=True,
    )


def barcode_attach_keyboard() -> ReplyKeyboardMarkup:
    rows: list[list] = []
    if MINIAPP_URL:
        rows.append(
            [
                KeyboardButton(
                    "📷 Kodni skanerlash",
                    web_app=WebAppInfo(url=f"{MINIAPP_URL}/scan.html?mode=add"),
                )
            ]
        )
    rows.append(["⏭ O‘chirish (0)"])
    rows.append(["❌ Bekor qilish"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def new_product_barcode_keyboard() -> ReplyKeyboardMarkup:
    """Yangi mahsulot: avval shtrix-kod (skan yoki o'tkazib yuborish)."""
    rows: list[list] = []
    if MINIAPP_URL:
        rows.append(
            [
                KeyboardButton(
                    "📷 Kodni skanerlash",
                    web_app=WebAppInfo(url=f"{MINIAPP_URL}/scan.html?mode=add"),
                )
            ]
        )
    rows.append(["⏭ O'tkazib yuborish"])
    rows.append(["❌ Bekor qilish"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def suggested_name_keyboard(name: str) -> ReplyKeyboardMarkup:
    label = name if len(name) <= 40 else name[:37] + "…"
    return ReplyKeyboardMarkup(
        [[f"✅ {label}"], ["✏️ Boshqa nom yozaman"], ["❌ Bekor qilish"]],
        resize_keyboard=True,
    )


def miniapp_keyboard() -> InlineKeyboardMarkup | None:
    """Mini App ochish tugmasi (faqat MINIAPP_URL sozlanganda)."""
    if not MINIAPP_URL:
        return None
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛒 Do'konni ochish",
                    web_app=WebAppInfo(url=MINIAPP_URL),
                )
            ]
        ]
    )


def more_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["🔍 Qidiruv", "⭐ Sevimlilar"],
            ["🎁 Bonus", "👥 Ulashish"],
            ["ℹ️ Yordam", "⬅️ Asosiy menyu"],
        ],
        resize_keyboard=True,
    )


def contact_keyboard(last_phone: str | None = None) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton("📱 Kontaktni yuborish", request_contact=True)],
    ]
    if last_phone:
        short = last_phone if len(last_phone) <= 28 else last_phone[:25] + "..."
        rows.append([f"✅ Shu raqam: {short}"])
    rows.append(["❌ Bekor qilish"])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def location_keyboard(last_address: str | None = None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
    if last_address:
        short = last_address if len(last_address) <= 40 else last_address[:37] + "..."
        rows.append([f"🏠 {short}"])
    rows.append(["❌ Bekor qilish"])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ Bekor qilish"]], resize_keyboard=True)


def catalog_categories_keyboard(categories) -> InlineKeyboardMarkup:
    from bot.database import get_products

    rows = []
    for category in categories:
        count = len(get_products(category_id=category["id"]))
        label = f"{category['name']} · {count} ta"
        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"catalog:cat:{category['id']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("🔍 Qidiruv", callback_data="catalog:search"),
            InlineKeyboardButton("⭐ Sevimlilar", callback_data="catalog:favs"),
        ]
    )
    if MINIAPP_URL:
        rows.append(
            [
                InlineKeyboardButton(
                    "📷 Skaner",
                    web_app=WebAppInfo(url=f"{MINIAPP_URL}/scan.html?mode=sale"),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("🛒 Savatchaga o'tish", callback_data="cart:view")]
    )
    return InlineKeyboardMarkup(rows)


def catalog_keyboard(
    products,
    category_id: int | None = None,
    cart_qty: dict[int, int] | None = None,
) -> InlineKeyboardMarkup:
    from bot.database import get_variants, product_display_price

    cart_qty = cart_qty or {}
    rows = []
    for product in products:
        # Har doim mahsulot kartochkasini ochamiz (rasm ko'rinsin)
        callback = f"product:{product['id']}"

        qty = cart_qty.get(product["id"], 0)
        mark = f" ✅ x{qty}" if qty else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{product['name']} — {product_display_price(product)}{mark}",
                    callback_data=callback,
                )
            ]
        )

    total_qty = sum(cart_qty.values())
    cart_label = f"🛒 Savatcha ({total_qty})" if total_qty else "🛒 Savatcha"
    rows.append(
        [
            InlineKeyboardButton("⬅️ Toifalar", callback_data="catalog:list"),
            InlineKeyboardButton(cart_label, callback_data="cart:view"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def product_keyboard(
    product_id: int,
    category_id: int | None = None,
    variants=None,
    cart_variant_qty: dict[int, int] | None = None,
) -> InlineKeyboardMarkup:
    back_data = (
        f"catalog:cat:{category_id}" if category_id else "catalog:list"
    )
    cart_variant_qty = cart_variant_qty or {}
    rows = []
    if variants:
        for variant in variants:
            qty = cart_variant_qty.get(variant["id"], 0)
            mark = f" ✅ x{qty}" if qty else ""
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{variant['name']} — {variant['price']:,} so'm{mark}",
                        callback_data=f"cart_add:{product_id}:{variant['id']}",
                    )
                ]
            )
    else:
        qty = cart_variant_qty.get(0, 0)
        mark = f" ✅ x{qty}" if qty else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"➕ Savatchaga qo'shish{mark}",
                    callback_data=f"cart_add:{product_id}:0",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("⭐", callback_data=f"fav:{product_id}"),
            InlineKeyboardButton("⬅️ Orqaga", callback_data=back_data),
            InlineKeyboardButton("🛒", callback_data="cart:view"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def category_pick_keyboard(categories) -> InlineKeyboardMarkup:
    rows = []
    for category in categories:
        rows.append(
            [
                InlineKeyboardButton(
                    category["name"],
                    callback_data=f"admin_prod:setcat:{category['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def cart_keyboard(items) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        pid = item["product_id"]
        vid = item["variant_id"]
        rows.append(
            [
                InlineKeyboardButton("➖", callback_data=f"cart_dec:{pid}:{vid}"),
                InlineKeyboardButton(
                    f"{item['name']} x{item['quantity']}",
                    callback_data=f"product:{pid}",
                ),
                InlineKeyboardButton("➕", callback_data=f"cart_inc:{pid}:{vid}"),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "✅ Buyurtma berish", callback_data="cart:checkout"
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🛍 Yana tanlash", callback_data="catalog:list"),
            InlineKeyboardButton("🧹 Tozalash", callback_data="cart:clear"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def confirm_order_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Ha, buyurtma beraman", callback_data="order:confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏷 Promo kod", callback_data="order:add_promo"
                ),
                InlineKeyboardButton("❌ Bekor", callback_data="order:cancel"),
            ],
        ]
    )


def payment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    from bot.config import CLICK_LINK, PAYME_LINK, online_payment_enabled

    rows = [
        [
            InlineKeyboardButton(
                "💵 Naqd to'lash",
                callback_data=f"pay_cash:{order_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "💳 Kartaga o'tkazish",
                callback_data=f"pay_card:{order_id}",
            )
        ],
    ]
    if PAYME_LINK:
        rows.append([InlineKeyboardButton("🟢 Payme", url=PAYME_LINK)])
        rows.append(
            [
                InlineKeyboardButton(
                    "✅ Payme orqali to'ladim",
                    callback_data=f"pay_done:{order_id}",
                )
            ]
        )
    if CLICK_LINK:
        rows.append([InlineKeyboardButton("🔵 Click", url=CLICK_LINK)])
        rows.append(
            [
                InlineKeyboardButton(
                    "✅ Click orqali to'ladim",
                    callback_data=f"pay_done:{order_id}",
                )
            ]
        )
    if online_payment_enabled():
        rows.append(
            [
                InlineKeyboardButton(
                    "🤖 Telegram orqali to'lov",
                    callback_data=f"pay_online:{order_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def card_paid_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Men to'lov qildim",
                    callback_data=f"pay_done:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Orqaga",
                    callback_data=f"pay_menu:{order_id}",
                )
            ],
        ]
    )


def admin_payment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ To'lovni tasdiqlash",
                    callback_data=f"pay_confirm:{order_id}",
                ),
                InlineKeyboardButton(
                    "❌ Rad etish",
                    callback_data=f"pay_reject:{order_id}",
                ),
            ]
        ]
    )


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🆕 Yangi buyurtmalar", callback_data="admin:new")],
            [
                InlineKeyboardButton(
                    "🚚 Faol buyurtmalar", callback_data="admin:active"
                )
            ],
            [InlineKeyboardButton("🛍 Mahsulotlar", callback_data="admin:products")],
            [InlineKeyboardButton("📊 Statistika", callback_data="admin:stats")],
            [InlineKeyboardButton("📈 Kunlik hisobot", callback_data="admin:report")],
            [InlineKeyboardButton("📣 Broadcast", callback_data="admin:broadcast")],
            [InlineKeyboardButton("📤 Excel eksport", callback_data="admin:export")],
            [InlineKeyboardButton("📥 Excel import", callback_data="admin:import")],
        ]
    )


def delivery_slots_keyboard(slots) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(slot, callback_data=f"slot:{i}")]
        for i, slot in enumerate(slots)
    ]
    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="order:cancel")])
    return InlineKeyboardMarkup(rows)


def promo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭ Promo yo'q", callback_data="promo:skip")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="order:cancel")],
        ]
    )


def bonus_keyboard(bonus: int) -> InlineKeyboardMarkup:
    rows = []
    if bonus > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    f"🎁 Bonus ishlatish ({bonus:,})",
                    callback_data="bonus:use",
                )
            ]
        )
    rows.append([InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="bonus:skip")])
    return InlineKeyboardMarkup(rows)


def order_actions_keyboard(order_id: int, can_pay: bool, can_cancel: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_pay:
        rows.append(
            [InlineKeyboardButton("💳 To'lov", callback_data=f"pay_menu:{order_id}")]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "🔁 Yana buyurtma", callback_data=f"reorder:{order_id}"
            )
        ]
    )
    if can_cancel:
        rows.append(
            [
                InlineKeyboardButton(
                    "❌ Bekor qilish", callback_data=f"cancel_order:{order_id}"
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def favorite_toggle_keyboard(product_id: int, is_fav: bool) -> InlineKeyboardMarkup:
    label = "💔 Sevimlidan olib tashlash" if is_fav else "⭐ Sevimliga"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"fav:{product_id}")]]
    )


def admin_products_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📋 Mahsulotlar spiskasi", callback_data="admin_prod:list"
                )
            ],
            [
                InlineKeyboardButton(
                    "➕ Yangi mahsulot", callback_data="admin_prod:add"
                )
            ],
            [
                InlineKeyboardButton(
                    "🗂 Toifalar", callback_data="admin_prod:cats"
                )
            ],
            [
                InlineKeyboardButton(
                    "➕ Yangi toifa", callback_data="admin_prod:addcat"
                )
            ],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin:menu")],
        ]
    )


def admin_all_products_list_keyboard(products) -> InlineKeyboardMarkup:
    """Mahsulotlar toifa bo'yicha guruhlangan spiska."""
    from collections import defaultdict

    grouped: dict[str, list] = defaultdict(list)
    for product in products:
        cat_name = product["category_name"] or "Toifasiz"
        grouped[cat_name].append(product)

    rows = []
    for cat_name in sorted(grouped.keys(), key=lambda x: x.casefold()):
        items = sorted(
            grouped[cat_name],
            key=lambda p: (p["name"] or "").casefold(),
        )
        cat_id = items[0]["category_id"] if items else None
        # Toifa — ajralib turadigan sarlavha (mahsulotdan farqli)
        header = f"━━ 📁 {cat_name} · {len(items)} ta ━━"
        if len(header) > 64:
            header = f"━━ 📁 {cat_name[:40]}… ━━"
        rows.append(
            [
                InlineKeyboardButton(
                    header,
                    callback_data=(
                        f"admin_prod:viewcat:{cat_id}"
                        if cat_id
                        else "admin_prod:cats"
                    ),
                )
            ]
        )
        for product in items:
            mark = "✅" if product["is_active"] else "🚫"
            try:
                has_photo = bool(product["image_file_id"])
            except (KeyError, IndexError):
                has_photo = False
            pic = "🖼" if has_photo else "📷·"
            # Mahsulot — oddiyroq, chekinish belgisiga o'xshash
            label = f"　　{mark}{pic} {product['name']} — {product['price']:,}"
            if len(label) > 64:
                label = label[:61] + "..."
            rows.append(
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=f"admin_prod:item:{product['id']}",
                    )
                ]
            )

    rows.append(
        [
            InlineKeyboardButton(
                "➕ Yangi mahsulot", callback_data="admin_prod:add"
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🗂 Toifalar", callback_data="admin_prod:cats"),
            InlineKeyboardButton("⬅️ Admin", callback_data="admin:menu"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def admin_categories_list_keyboard(categories_with_counts) -> InlineKeyboardMarkup:
    """Bitta xabarda toifalar spiskasi."""
    rows = []
    for category, count in categories_with_counts:
        rows.append(
            [
                InlineKeyboardButton(
                    f"{category['name']} ({count})",
                    callback_data=f"admin_prod:viewcat:{category['id']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "➕ Yangi toifa", callback_data="admin_prod:addcat"
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin:products")]
    )
    return InlineKeyboardMarkup(rows)


def admin_category_item_keyboard(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📋 Mahsulotlar",
                    callback_data=f"admin_prod:viewcat:{category_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📷➕ Mahsulot (skan)",
                    callback_data=f"admin_prod:addin:{category_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑 Toifani o'chirish",
                    callback_data=f"admin_prod:delcat:{category_id}",
                )
            ],
        ]
    )


def admin_category_products_list_keyboard(
    category_id: int, products
) -> InlineKeyboardMarkup:
    """Toifa ichidagi mahsulotlar — bitta spiska."""
    rows = []
    for product in products:
        mark = "✅" if product["is_active"] else "🚫"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{mark} {product['name']} — {product['price']:,}",
                    callback_data=f"admin_prod:item:{product['id']}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "📷➕ Mahsulot (skan)",
                callback_data=f"admin_prod:addin:{category_id}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                "🗑 Toifani o'chirish",
                callback_data=f"admin_prod:delcat:{category_id}",
            ),
            InlineKeyboardButton(
                "⬅️ Toifalar",
                callback_data="admin_prod:cats",
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)


def admin_category_products_header_keyboard(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📷➕ Mahsulot (skan)",
                    callback_data=f"admin_prod:addin:{category_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Toifalar",
                    callback_data="admin_prod:cats",
                )
            ],
        ]
    )


def admin_product_item_keyboard(product_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "🚫 Yashirish" if is_active else "✅ Ko'rsatish"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💰 Narx", callback_data=f"admin_prod:price:{product_id}"
                ),
                InlineKeyboardButton(
                    "📐 O'lcham", callback_data=f"admin_prod:size:{product_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📦 Ombor", callback_data=f"admin_prod:stock:{product_id}"
                ),
                InlineKeyboardButton(
                    "🖼 Rasm", callback_data=f"admin_prod:photo:{product_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📷 Shtrix-kod", callback_data=f"admin_prod:barcode:{product_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    toggle_label, callback_data=f"admin_prod:toggle:{product_id}"
                ),
                InlineKeyboardButton(
                    "🗑 O'chirish", callback_data=f"admin_prod:del:{product_id}"
                ),
            ],
        ]
    )


def admin_variant_item_keyboard(variant_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑 O'lchamni o'chirish",
                    callback_data=f"admin_prod:delsize:{variant_id}",
                )
            ]
        ]
    )


def admin_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for status_key, label in ORDER_STATUS_LABELS.items():
        if status_key == "new":
            continue
        buttons.append(
            InlineKeyboardButton(
                label,
                callback_data=f"admin_status:{order_id}:{status_key}",
            )
        )

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [
            InlineKeyboardButton(
                "🗑 Ma'lumotni o'chirish",
                callback_data=f"admin_del_order:{order_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def admin_delete_order_confirm_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Ha, o'chirilsin",
                    callback_data=f"admin_del_order_yes:{order_id}",
                ),
                InlineKeyboardButton(
                    "❌ Yo'q",
                    callback_data=f"admin_del_order_no:{order_id}",
                ),
            ]
        ]
    )
