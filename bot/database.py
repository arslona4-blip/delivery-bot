import sqlite3
from contextlib import contextmanager
from typing import Any

from bot.config import DATABASE_PATH, DELIVERY_PRICE, ORDER_STATUS_LABELS, PAYMENT_STATUS_LABELS
from bot.timeutil import format_dt, money_html, now_tashkent


def _now_iso() -> str:
    return now_tashkent().isoformat()


DEFAULT_CATEGORIES = [
    "🍞 Oziq-ovqat",
    "🥤 Ichimliklar",
    "🏠 Uy-ro'zg'or",
]

DEFAULT_PRODUCTS = [
    ("Non (1 dona)", 4000, "Yangilik non", "🍞 Oziq-ovqat"),
    ("Sut 1L", 12000, "Tabiiy sut", "🍞 Oziq-ovqat"),
    ("Tuxum (10 dona)", 18000, "Tovuq tuxumi", "🍞 Oziq-ovqat"),
    ("Guruch 1kg", 16000, "Oq guruch", "🍞 Oziq-ovqat"),
    ("Yog' 1L", 22000, "O'simlik yog'i", "🍞 Oziq-ovqat"),
    ("Shakar 1kg", 14000, "Oq shakar", "🍞 Oziq-ovqat"),
    ("Choy 100g", 25000, "Qora choy", "🍞 Oziq-ovqat"),
    ("Makaron 400g", 9000, "Spaghetti", "🍞 Oziq-ovqat"),
    ("Cola 1.5L", 13000, "Ichimlik", "🥤 Ichimliklar"),
    ("Suv 1.5L", 5000, "Ichiladigan suv", "🥤 Ichimliklar"),
]


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pickup_address TEXT NOT NULL,
                delivery_address TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                description TEXT,
                phone TEXT NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'new',
                payment_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                category_id INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            );

            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (product_id) REFERENCES products (id)
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                variant_id INTEGER NOT NULL DEFAULT 0,
                quantity INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, product_id, variant_id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            );
            """
        )
        order_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()
        }
        if "latitude" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN latitude REAL")
        if "longitude" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN longitude REAL")

        product_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()
        }
        if "category_id" not in product_columns:
            conn.execute("ALTER TABLE products ADD COLUMN category_id INTEGER")

        cart_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(cart_items)").fetchall()
        }
        if cart_columns and "variant_id" not in cart_columns:
            conn.executescript(
                """
                CREATE TABLE cart_items_new (
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    variant_id INTEGER NOT NULL DEFAULT 0,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (user_id, product_id, variant_id)
                );
                INSERT INTO cart_items_new (user_id, product_id, variant_id, quantity)
                SELECT user_id, product_id, 0, quantity FROM cart_items;
                DROP TABLE cart_items;
                ALTER TABLE cart_items_new RENAME TO cart_items;
                """
            )

        cat_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if cat_count == 0:
            conn.executemany(
                "INSERT INTO categories (name) VALUES (?)",
                [(name,) for name in DEFAULT_CATEGORIES],
            )

        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            for name, price, description, category_name in DEFAULT_PRODUCTS:
                category_id = conn.execute(
                    "SELECT id FROM categories WHERE name = ?",
                    (category_name,),
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO products (name, price, description, category_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (name, price, description, category_id),
                )
        else:
            default_cat = conn.execute(
                "SELECT id FROM categories ORDER BY id LIMIT 1"
            ).fetchone()
            if default_cat:
                conn.execute(
                    """
                    UPDATE products
                    SET category_id = ?
                    WHERE category_id IS NULL
                    """,
                    (default_cat[0],),
                )

        _migrate_features(conn)


def _migrate_features(conn: sqlite3.Connection) -> None:
    user_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "bonus_points" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN bonus_points INTEGER NOT NULL DEFAULT 0")

    product_cols = {r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()}
    if "stock" not in product_cols:
        conn.execute("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 100")
    if "image_file_id" not in product_cols:
        conn.execute("ALTER TABLE products ADD COLUMN image_file_id TEXT")
    if "barcode" not in product_cols:
        conn.execute("ALTER TABLE products ADD COLUMN barcode TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_products_barcode
        ON products(barcode)
        WHERE barcode IS NOT NULL AND barcode != ''
        """
    )

    variant_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(product_variants)").fetchall()
    }
    if "stock" not in variant_cols:
        conn.execute(
            "ALTER TABLE product_variants ADD COLUMN stock INTEGER NOT NULL DEFAULT 100"
        )

    order_cols = {r[1] for r in conn.execute("PRAGMA table_info(orders)").fetchall()}
    for col, sql_type in [
        ("delivery_slot", "TEXT"),
        ("promo_code", "TEXT"),
        ("discount", "INTEGER NOT NULL DEFAULT 0"),
        ("bonus_spent", "INTEGER NOT NULL DEFAULT 0"),
        ("subtotal", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        if col not in order_cols:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {col} {sql_type}")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, product_id)
        );

        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            discount_percent INTEGER NOT NULL DEFAULT 0,
            discount_amount INTEGER NOT NULL DEFAULT 0,
            min_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS referrals (
            referred_user_id INTEGER PRIMARY KEY,
            referrer_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            rewarded INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            note TEXT,
            telegram_user_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS debt_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount INTEGER NOT NULL,
            order_id INTEGER,
            note TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES contacts (id)
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_debt_contact ON debt_ledger(contact_id)"
    )
    promo_count = conn.execute("SELECT COUNT(*) FROM promo_codes").fetchone()[0]
    if promo_count == 0:
        conn.execute(
            """
            INSERT INTO promo_codes (code, discount_percent, discount_amount, min_order, is_active)
            VALUES ('BARAKA10', 10, 0, 30000, 1)
            """
        )


@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_user(user_id: int, full_name: str, username: str | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username, full_name, _now_iso()),
        )


def set_user_phone(user_id: int, phone: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (phone, user_id),
        )


def get_user(user_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row


def get_categories(active_only: bool = True) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM categories WHERE is_active = 1 ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    return list(rows)


def get_category(category_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM categories WHERE id = ?",
            (category_id,),
        ).fetchone()
    return row


def create_category(name: str) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM categories WHERE name = ?",
            (name,),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE categories SET is_active = 1 WHERE id = ?",
                (existing["id"],),
            )
            return int(existing["id"])
        cursor = conn.execute(
            "INSERT INTO categories (name, is_active) VALUES (?, 1)",
            (name,),
        )
        return int(cursor.lastrowid)


def delete_category(category_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET category_id = NULL WHERE category_id = ?",
            (category_id,),
        )
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def get_products(active_only: bool = True, category_id: int | None = None) -> list[sqlite3.Row]:
    with get_connection() as conn:
        query = """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE 1=1
        """
        params: list[Any] = []
        if active_only:
            query += " AND p.is_active = 1 AND COALESCE(p.stock, 0) > 0"
        if category_id is not None:
            query += " AND p.category_id = ?"
            params.append(category_id)
        query += " ORDER BY p.name COLLATE NOCASE, p.id"
        rows = conn.execute(query, params).fetchall()
    return list(rows)


def get_product(product_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id = ? AND p.is_active = 1
            """,
            (product_id,),
        ).fetchone()
    return row


def get_product_by_id(product_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        ).fetchone()
    return row


def create_product(
    name: str,
    price: int,
    description: str = "",
    category_id: int | None = None,
    barcode: str | None = None,
) -> int:
    code = (barcode or "").strip() or None
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO products (name, price, description, category_id, is_active, barcode)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (name, price, description, category_id, code),
        )
        return int(cursor.lastrowid)


def get_product_by_barcode(barcode: str) -> sqlite3.Row | None:
    code = (barcode or "").strip()
    if not code:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.barcode = ? AND p.is_active = 1
            """,
            (code,),
        ).fetchone()
    return row


def set_product_barcode(product_id: int, barcode: str | None) -> None:
    code = (barcode or "").strip() or None
    if code in {"0", "-", "none", "yo'q", "yoq"}:
        code = None
    with get_connection() as conn:
        if code:
            other = conn.execute(
                "SELECT id, name FROM products WHERE barcode = ? AND id != ?",
                (code, product_id),
            ).fetchone()
            if other:
                raise ValueError(
                    f"Kod boshqa mahsulotda: #{other['id']} {other['name']}"
                )
        conn.execute(
            "UPDATE products SET barcode = ? WHERE id = ?",
            (code, product_id),
        )


def update_product_price(product_id: int, price: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET price = ? WHERE id = ?",
            (price, product_id),
        )


def update_product_name(product_id: int, name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET name = ? WHERE id = ?",
            (name, product_id),
        )


def set_product_active(product_id: int, is_active: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, product_id),
        )


def delete_product(product_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


def get_variants(product_id: int, active_only: bool = True) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if active_only:
            rows = conn.execute(
                """
                SELECT * FROM product_variants
                WHERE product_id = ? AND is_active = 1
                ORDER BY price, id
                """,
                (product_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM product_variants
                WHERE product_id = ?
                ORDER BY price, id
                """,
                (product_id,),
            ).fetchall()
    return list(rows)


def get_variant(variant_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT v.*, p.name AS product_name, p.category_id, p.is_active AS product_active
            FROM product_variants v
            JOIN products p ON p.id = v.product_id
            WHERE v.id = ? AND v.is_active = 1 AND p.is_active = 1
            """,
            (variant_id,),
        ).fetchone()
    return row


def create_variant(product_id: int, name: str, price: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO product_variants (product_id, name, price, is_active)
            VALUES (?, ?, ?, 1)
            """,
            (product_id, name, price),
        )
        return int(cursor.lastrowid)


def delete_variant(variant_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM cart_items WHERE variant_id = ?",
            (variant_id,),
        )
        conn.execute("DELETE FROM product_variants WHERE id = ?", (variant_id,))


def product_display_price(product: sqlite3.Row) -> str:
    variants = get_variants(product["id"])
    if not variants:
        return f"{product['price']:,} so'm"
    prices = [v["price"] for v in variants]
    low, high = min(prices), max(prices)
    if low == high:
        return f"{low:,} so'm"
    return f"{low:,} – {high:,} so'm"


def add_to_cart(
    user_id: int,
    product_id: int,
    quantity: int = 1,
    variant_id: int = 0,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cart_items (user_id, product_id, variant_id, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, product_id, variant_id) DO UPDATE SET
                quantity = cart_items.quantity + excluded.quantity
            """,
            (user_id, product_id, variant_id, quantity),
        )


def set_cart_quantity(
    user_id: int,
    product_id: int,
    quantity: int,
    variant_id: int = 0,
) -> None:
    with get_connection() as conn:
        if quantity <= 0:
            conn.execute(
                """
                DELETE FROM cart_items
                WHERE user_id = ? AND product_id = ? AND variant_id = ?
                """,
                (user_id, product_id, variant_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO cart_items (user_id, product_id, variant_id, quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, product_id, variant_id) DO UPDATE SET
                    quantity = excluded.quantity
                """,
                (user_id, product_id, variant_id, quantity),
            )


def remove_from_cart(
    user_id: int, product_id: int, variant_id: int = 0
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM cart_items
            WHERE user_id = ? AND product_id = ? AND variant_id = ?
            """,
            (user_id, product_id, variant_id),
        )


def clear_cart(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))


def get_cart(user_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.product_id,
                c.variant_id,
                c.quantity,
                p.name AS product_name,
                p.description,
                CASE
                    WHEN c.variant_id > 0 THEN v.name
                    ELSE NULL
                END AS variant_name,
                CASE
                    WHEN c.variant_id > 0 THEN v.price
                    ELSE p.price
                END AS price,
                CASE
                    WHEN c.variant_id > 0 THEN p.name || ' (' || v.name || ')'
                    ELSE p.name
                END AS name
            FROM cart_items c
            JOIN products p ON p.id = c.product_id
            LEFT JOIN product_variants v ON v.id = c.variant_id
            WHERE c.user_id = ?
              AND p.is_active = 1
              AND (c.variant_id = 0 OR v.is_active = 1)
            ORDER BY name
            """,
            (user_id,),
        ).fetchall()
    return list(rows)


def get_cart_totals(user_id: int) -> tuple[int, int]:
    items = get_cart(user_id)
    count = sum(item["quantity"] for item in items)
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    return count, subtotal


def format_cart(user_id: int) -> str:
    from bot.timeutil import money_html

    items = get_cart(user_id)
    if not items:
        return (
            "🛒 Savatchangiz bo'sh\n\n"
            "🛍 Katalogdan mahsulot tanlang — bir bosishda qo'shiladi!"
        )

    lines = ["🛒 <b>Sizning savatchangiz</b>", "┄┄┄┄┄┄┄┄┄┄┄┄"]
    for i, item in enumerate(items, 1):
        line_total = item["price"] * item["quantity"]
        lines.append(
            f"{i}. {item['name']}\n"
            f"   {item['quantity']} × {item['price']:,} = "
            f"{money_html(line_total, with_emoji=False)}"
        )
    _, subtotal = get_cart_totals(user_id)
    total = subtotal + DELIVERY_PRICE
    lines.append("┄┄┄┄┄┄┄┄┄┄┄┄")
    lines.append(f"🛍 Mahsulotlar: {money_html(subtotal, with_emoji=False)}")
    lines.append(f"🚚 Yetkazish: {money_html(DELIVERY_PRICE, with_emoji=False)}")
    lines.append(f"✨ {money_html(total)} <b>← JAMI</b> ✨")
    return "\n".join(lines)


def create_order(
    user_id: int,
    pickup_address: str,
    delivery_address: str,
    description: str,
    phone: str,
    price: int,
    latitude: float | None = None,
    longitude: float | None = None,
    delivery_slot: str = "",
    promo_code: str = "",
    discount: int = 0,
    bonus_spent: int = 0,
    subtotal: int = 0,
) -> int:
    now = _now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO orders (
                user_id, pickup_address, delivery_address, latitude, longitude,
                description, phone, price, status, payment_status, created_at, updated_at,
                delivery_slot, promo_code, discount, bonus_spent, subtotal
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', 'pending', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                pickup_address,
                delivery_address,
                latitude,
                longitude,
                description,
                phone,
                price,
                now,
                now,
                delivery_slot,
                promo_code,
                discount,
                bonus_spent,
                subtotal,
            ),
        )
        return int(cursor.lastrowid)


def save_order_items(order_id: int, user_id: int) -> None:
    items = get_cart(user_id)
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO order_items (
                order_id, product_id, product_name, price, quantity
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    order_id,
                    item["product_id"],
                    item["name"],
                    item["price"],
                    item["quantity"],
                )
                for item in items
            ],
        )


def save_order_items_direct(
    order_id: int, items: list[dict[str, Any]]
) -> None:
    """Mini App / tashqi buyurtma uchun."""
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO order_items (
                order_id, product_id, product_name, price, quantity
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    order_id,
                    int(item["product_id"]),
                    str(item["name"]),
                    int(item["price"]),
                    int(item["quantity"]),
                )
                for item in items
            ],
        )


def get_order_items(order_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM order_items
            WHERE order_id = ?
            ORDER BY id
            """,
            (order_id,),
        ).fetchall()
    return list(rows)


def get_order(order_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
    return row


def delete_order(order_id: int) -> bool:
    """Buyurtma va uning mahsulotlarini butunlay o'chiradi."""
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if not exists:
            return False
        conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    return True


def get_user_orders(user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return list(rows)


def get_last_delivery_address(user_id: int) -> str | None:
    """Oxirgi muvaffaqiyatli buyurtma manzili (lokatsiya emas, matn)."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT delivery_address FROM orders
            WHERE user_id = ?
              AND delivery_address IS NOT NULL
              AND delivery_address != ''
              AND delivery_address != 'Lokatsiya'
              AND status != 'cancelled'
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    addr = (row["delivery_address"] or "").strip()
    return addr or None


def get_orders_by_status(status: str, limit: int = 20) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE status = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()
    return list(rows)


def update_order_status(order_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE orders
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, _now_iso(), order_id),
        )


def update_payment_status(order_id: int, payment_status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE orders
            SET payment_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (payment_status, _now_iso(), order_id),
        )


def format_order_items(order_id: int) -> str:
    items = get_order_items(order_id)
    if not items:
        return ""
    lines = ["🛍 Mahsulotlar:"]
    for item in items:
        lines.append(
            f"• {item['product_name']} x{item['quantity']} — "
            f"{item['price'] * item['quantity']:,} so'm"
        )
    return "\n".join(lines)


from bot.timeutil import money_html


def format_order(row: sqlite3.Row) -> str:
    status = ORDER_STATUS_LABELS.get(row["status"], row["status"])
    payment = PAYMENT_STATUS_LABELS.get(row["payment_status"], row["payment_status"])
    delivery = row["delivery_address"]
    if row["latitude"] is not None and row["longitude"] is not None:
        maps_url = f"https://maps.google.com/?q={row['latitude']},{row['longitude']}"
        delivery = f"{delivery}\n🗺 Xarita: {maps_url}"

    items_text = format_order_items(row["id"])
    parts = [
        f"📦 Buyurtma #{row['id']}",
        f"Holat: {status}",
        f"To'lov: {payment}",
        f"📅 Berilgan: ❰ {format_dt(row['created_at'])} ❱",
    ]
    if items_text:
        parts.append(items_text)
    slot = row["delivery_slot"] if "delivery_slot" in row.keys() else None
    if slot:
        parts.append(f"🕒 Yetkazish: ❰ {slot} ❱")
    promo = row["promo_code"] if "promo_code" in row.keys() else None
    discount = row["discount"] if "discount" in row.keys() else 0
    if promo:
        parts.append(f"🏷 Promo: {promo} (−{discount or 0:,} so'm)")
    bonus = row["bonus_spent"] if "bonus_spent" in row.keys() else 0
    if bonus:
        parts.append(f"🎁 Bonus: −{bonus:,} so'm")
    parts.extend(
        [
            f"📍 Qayerdan: {row['pickup_address']}",
            f"🏁 Qayerga: {delivery}",
            f"📝 Izoh: {row['description'] or '—'}",
            f"📞 Telefon: {row['phone']}",
            f"✨💰 JAMI: {row['price']:,} so'm ✨",
        ]
    )
    return "\n".join(parts)


def get_stats() -> dict[str, Any]:
    with get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        new_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'new'"
        ).fetchone()[0]
        active_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status IN ('accepted', 'in_delivery')"
        ).fetchone()[0]
        delivered = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'delivered'"
        ).fetchone()[0]
        revenue = conn.execute(
            """
            SELECT COALESCE(SUM(price), 0) FROM orders
            WHERE status != 'cancelled'
            """
        ).fetchone()[0]
        today_row = conn.execute(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(price), 0) AS total
            FROM orders
            WHERE date(created_at) = date('now', 'localtime')
              AND status != 'cancelled'
            """
        ).fetchone()
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "new_orders": new_orders,
        "active_orders": active_orders,
        "delivered_orders": delivered,
        "revenue_sum": int(revenue or 0),
        "today_orders": int(today_row["cnt"] or 0),
        "today_sum": int(today_row["total"] or 0),
    }


def search_products(query: str, limit: int = 20) -> list[sqlite3.Row]:
    q = f"%{query.strip()}%"
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.is_active = 1 AND p.stock > 0
              AND (p.name LIKE ? OR IFNULL(p.description, '') LIKE ?)
            ORDER BY p.name
            LIMIT ?
            """,
            (q, q, limit),
        ).fetchall()
    return list(rows)


def add_favorite(user_id: int, product_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO favorites (user_id, product_id, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, product_id, _now_iso()),
        )


def remove_favorite(user_id: int, product_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )


def is_favorite(user_id: int, product_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        ).fetchone()
    return row is not None


def get_favorites(user_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM favorites f
            JOIN products p ON p.id = f.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE f.user_id = ? AND p.is_active = 1
            ORDER BY p.name COLLATE NOCASE
            """,
            (user_id,),
        ).fetchall()
    return list(rows)


def get_promo(code: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM promo_codes
            WHERE UPPER(code) = UPPER(?) AND is_active = 1
            """,
            (code.strip(),),
        ).fetchone()
    return row


def calc_promo_discount(code: str, subtotal: int) -> tuple[int, str]:
    promo = get_promo(code)
    if not promo:
        return 0, "Promo kod topilmadi."
    if subtotal < promo["min_order"]:
        return 0, f"Minimal summa: {promo['min_order']:,} so'm"
    if promo["discount_percent"]:
        return int(subtotal * promo["discount_percent"] / 100), "OK"
    return int(promo["discount_amount"]), "OK"


def get_bonus(user_id: int) -> int:
    user = get_user(user_id)
    if not user:
        return 0
    try:
        return int(user["bonus_points"] or 0)
    except (KeyError, IndexError, TypeError):
        return 0


def add_bonus(user_id: int, points: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET bonus_points = COALESCE(bonus_points, 0) + ? WHERE user_id = ?",
            (points, user_id),
        )


def save_referral(referred_user_id: int, referrer_user_id: int) -> bool:
    """Yangi foydalanuvchi referralini saqlaydi. Takror bo'lsa False."""
    if referred_user_id == referrer_user_id:
        return False
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM referrals WHERE referred_user_id = ?",
            (referred_user_id,),
        ).fetchone()
        if exists:
            return False
        if not get_user(referrer_user_id):
            return False
        conn.execute(
            """
            INSERT INTO referrals (referred_user_id, referrer_user_id, created_at, rewarded)
            VALUES (?, ?, ?, 1)
            """,
            (referred_user_id, referrer_user_id, _now_iso()),
        )
    return True


def spend_bonus(user_id: int, points: int) -> bool:
    if points <= 0:
        return True
    current = get_bonus(user_id)
    if current < points:
        return False
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET bonus_points = bonus_points - ? WHERE user_id = ?",
            (points, user_id),
        )
    return True


def set_product_stock(product_id: int, stock: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE products SET stock = ? WHERE id = ?", (stock, product_id))


def set_product_image(product_id: int, file_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET image_file_id = ? WHERE id = ?",
            (file_id, product_id),
        )


def decrease_stock_for_cart(user_id: int) -> None:
    items = get_cart(user_id)
    with get_connection() as conn:
        for item in items:
            conn.execute(
                "UPDATE products SET stock = MAX(stock - ?, 0) WHERE id = ?",
                (item["quantity"], item["product_id"]),
            )


def refill_cart_from_order(user_id: int, order_id: int) -> int:
    items = get_order_items(order_id)
    clear_cart(user_id)
    added = 0
    for item in items:
        if not item["product_id"]:
            continue
        product = get_product(item["product_id"])
        if not product:
            continue
        add_to_cart(user_id, item["product_id"], item["quantity"], 0)
        added += 1
    return added


def get_all_user_ids() -> list[int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
    return [int(r["user_id"]) for r in rows]


def get_daily_report() -> dict[str, Any]:
    today = now_tashkent().strftime("%Y-%m-%d")
    with get_connection() as conn:
        orders = conn.execute(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(price), 0) AS total
            FROM orders
            WHERE date(created_at) = date('now', 'localtime')
              AND status != 'cancelled'
            """
        ).fetchone()
        paid = conn.execute(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(price), 0) AS total
            FROM orders
            WHERE date(created_at) = date('now', 'localtime')
              AND payment_status IN ('paid', 'cash')
            """
        ).fetchone()
        waiting = conn.execute(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(price), 0) AS total
            FROM orders
            WHERE date(created_at) = date('now', 'localtime')
              AND payment_status IN ('pending', 'card_waiting')
              AND status != 'cancelled'
            """
        ).fetchone()
        top = conn.execute(
            """
            SELECT oi.product_name, SUM(oi.quantity) AS qty
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE date(o.created_at) = date('now', 'localtime')
              AND o.status != 'cancelled'
            GROUP BY oi.product_name
            ORDER BY qty DESC
            LIMIT 5
            """
        ).fetchall()
    return {
        "date": today,
        "orders_count": int(orders["cnt"] or 0),
        "orders_sum": int(orders["total"] or 0),
        "paid_count": int(paid["cnt"] or 0),
        "paid_sum": int(paid["total"] or 0),
        "waiting_count": int(waiting["cnt"] or 0),
        "waiting_sum": int(waiting["total"] or 0),
        "top": list(top),
    }


def export_products_csv() -> str:
    import csv
    from io import StringIO

    products = get_products(active_only=False)
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "price", "description", "category_id", "stock", "is_active"])
    for p in products:
        writer.writerow(
            [
                p["id"],
                p["name"],
                p["price"],
                p["description"] or "",
                p["category_id"] or "",
                p["stock"] if "stock" in p.keys() else 100,
                p["is_active"],
            ]
        )
    return buf.getvalue()


def import_products_csv(text: str) -> int:
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO(text))
    count = 0
    with get_connection() as conn:
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            price = int(float(row.get("price") or 0))
            description = row.get("description") or ""
            category_id = row.get("category_id") or None
            stock = int(float(row.get("stock") or 100))
            is_active = int(float(row.get("is_active") or 1))
            pid = row.get("id")
            if pid:
                exists = conn.execute(
                    "SELECT id FROM products WHERE id = ?", (pid,)
                ).fetchone()
                if exists:
                    conn.execute(
                        """
                        UPDATE products
                        SET name=?, price=?, description=?, category_id=?, stock=?, is_active=?
                        WHERE id=?
                        """,
                        (name, price, description, category_id or None, stock, is_active, pid),
                    )
                    count += 1
                    continue
            conn.execute(
                """
                INSERT INTO products (name, price, description, category_id, stock, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, price, description, category_id or None, stock, is_active),
            )
            count += 1
    return count


def get_courier_orders() -> list[sqlite3.Row]:
    return [
        *get_orders_by_status("accepted"),
        *get_orders_by_status("in_delivery"),
    ]


# --- Contacts & debts ---
def create_contact(
    name: str,
    phone: str | None = None,
    note: str = "",
    telegram_user_id: int | None = None,
) -> int:
    now = _now_iso()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO contacts (name, phone, note, telegram_user_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                (phone or "").strip() or None,
                (note or "").strip(),
                telegram_user_id,
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


def update_contact(
    contact_id: int,
    *,
    name: str | None = None,
    phone: str | None = None,
    note: str | None = None,
) -> None:
    contact = get_contact(contact_id)
    if not contact:
        return
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE contacts
            SET name = ?, phone = ?, note = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name if name is not None else contact["name"],
                phone if phone is not None else contact["phone"],
                note if note is not None else contact["note"],
                _now_iso(),
                contact_id,
            ),
        )


def get_contact(contact_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()


def find_contact_by_phone(phone: str) -> sqlite3.Row | None:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) < 9:
        return None
    tail = digits[-9:]
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE phone IS NOT NULL"
        ).fetchall()
    for row in rows:
        p = "".join(ch for ch in (row["phone"] or "") if ch.isdigit())
        if p.endswith(tail):
            return row
    return None


def find_or_create_contact_for_order(order: sqlite3.Row) -> int:
    phone = (order["phone"] or "").strip()
    existing = find_contact_by_phone(phone) if phone else None
    if existing:
        if order["user_id"] and not existing["telegram_user_id"]:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE contacts
                    SET telegram_user_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (order["user_id"], _now_iso(), existing["id"]),
                )
        return int(existing["id"])
    user = get_user(order["user_id"]) if order["user_id"] else None
    name = (user["full_name"] if user else None) or f"Mijoz #{order['user_id']}"
    return create_contact(
        name=name,
        phone=phone or None,
        note=f"Buyurtma #{order['id']}",
        telegram_user_id=order["user_id"],
    )


def list_contacts(*, debtors_only: bool = False) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*,
                   COALESCE((
                     SELECT SUM(
                       CASE WHEN kind='debt' THEN amount ELSE -amount END
                     )
                     FROM debt_ledger d WHERE d.contact_id = c.id
                   ), 0) AS balance
            FROM contacts c
            ORDER BY c.name COLLATE NOCASE
            """
        ).fetchall()
    result = []
    for row in rows:
        item = {k: row[k] for k in row.keys()}
        bal = int(item.get("balance") or 0)
        item["balance"] = bal
        if debtors_only and bal <= 0:
            continue
        result.append(item)
    if debtors_only:
        result.sort(key=lambda x: -x["balance"])
    return result


def get_contact_balance(contact_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(
              SUM(CASE WHEN kind='debt' THEN amount ELSE -amount END), 0
            )
            FROM debt_ledger WHERE contact_id = ?
            """,
            (contact_id,),
        ).fetchone()
    return int(row[0] if row else 0)


def add_debt_entry(
    contact_id: int,
    amount: int,
    *,
    kind: str = "debt",
    order_id: int | None = None,
    note: str = "",
    created_by: int | None = None,
) -> int:
    if amount <= 0:
        raise ValueError("Summa 0 dan katta bo'lsin")
    if kind not in {"debt", "payment"}:
        raise ValueError("kind noto'g'ri")
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO debt_ledger
                (contact_id, kind, amount, order_id, note, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact_id,
                kind,
                int(amount),
                order_id,
                (note or "").strip(),
                created_by,
                _now_iso(),
            ),
        )
        return int(cur.lastrowid)


def list_debt_ledger(contact_id: int, limit: int = 20) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return list(
            conn.execute(
                """
                SELECT * FROM debt_ledger
                WHERE contact_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (contact_id, limit),
            ).fetchall()
        )


def debt_totals() -> dict[str, int]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN kind='debt' THEN amount ELSE 0 END), 0)
                AS debts,
              COALESCE(SUM(CASE WHEN kind='payment' THEN amount ELSE 0 END), 0)
                AS payments
            FROM debt_ledger
            """
        ).fetchone()
    debts = int(row["debts"])
    payments = int(row["payments"])
    return {"debts": debts, "payments": payments, "open": max(0, debts - payments)}


def mark_order_as_debt(
    order_id: int,
    *,
    created_by: int | None = None,
    contact_id: int | None = None,
) -> tuple[int, int]:
    """Buyurtmani qarzga yozadi. Qaytaradi: (contact_id, balance)."""
    order = get_order(order_id)
    if not order:
        raise ValueError("Buyurtma topilmadi")
    cid = contact_id or find_or_create_contact_for_order(order)
    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT id FROM debt_ledger
            WHERE order_id = ? AND kind = 'debt'
            """,
            (order_id,),
        ).fetchone()
    if not exists:
        add_debt_entry(
            cid,
            int(order["price"]),
            kind="debt",
            order_id=order_id,
            note=f"Buyurtma #{order_id}",
            created_by=created_by,
        )
    update_payment_status(order_id, "debt")
    return cid, get_contact_balance(cid)
