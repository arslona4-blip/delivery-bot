"""Telegram Mini App — aiohttp server."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from typing import Any
from urllib.parse import parse_qsl

from aiohttp import web

from bot.config import (
    ADMIN_IDS,
    BASE_DIR,
    BOT_TOKEN,
    DELIVERY_PRICE,
    MIN_ORDER_AMOUNT,
    SHOP_ADDRESS,
    SHOP_HOURS,
    SHOP_NAME,
    SHOP_PHONE,
    SHOP_TELEGRAM,
    WEBAPP_PORT,
)
from bot.database import (
    create_order,
    format_order,
    get_categories,
    get_order,
    get_product,
    get_products,
    get_variant,
    get_variants,
    product_display_price,
    save_order_items_direct,
    set_user_phone,
    upsert_user,
)
from bot.timeutil import get_delivery_slots

logger = logging.getLogger(__name__)

_bot = None
MINIAPP_DIR = BASE_DIR / "miniapp"


def set_bot(bot) -> None:
    global _bot
    _bot = bot


def validate_webapp_init_data(init_data: str) -> dict[str, Any] | None:
    """Telegram WebApp initData HMAC tekshiruvi."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        return None

    result: dict[str, Any] = dict(parsed)
    user_raw = parsed.get("user")
    if user_raw:
        try:
            result["user"] = json.loads(user_raw)
        except json.JSONDecodeError:
            return None
    return result


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = exc
            _add_cors(response)
            raise
        except Exception:
            raise
    _add_cors(response)
    return response


def _add_cors(response: web.StreamResponse) -> None:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"


def _row_to_dict(row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


async def api_config(_request: web.Request) -> web.Response:
    return web.json_response(
        {
            "shop_name": SHOP_NAME,
            "shop_address": SHOP_ADDRESS,
            "shop_phone": SHOP_PHONE,
            "shop_telegram": SHOP_TELEGRAM,
            "shop_hours": SHOP_HOURS,
            "delivery_price": DELIVERY_PRICE,
            "min_order": MIN_ORDER_AMOUNT,
            "slots": get_delivery_slots(),
        }
    )


async def api_categories(_request: web.Request) -> web.Response:
    cats = get_categories(active_only=True)
    return web.json_response(
        [
            {
                "id": int(c["id"]),
                "name": c["name"],
            }
            for c in cats
        ]
    )


async def api_products(request: web.Request) -> web.Response:
    category_id_raw = request.rel_url.query.get("category_id")
    category_id: int | None = None
    if category_id_raw not in (None, ""):
        try:
            category_id = int(category_id_raw)
        except ValueError:
            raise web.HTTPBadRequest(text="category_id noto'g'ri")

    products = get_products(active_only=True, category_id=category_id)
    payload = []
    for p in products:
        variants = get_variants(int(p["id"]), active_only=True)
        has_photo = bool(p["image_file_id"]) if "image_file_id" in p.keys() else False
        payload.append(
            {
                "id": int(p["id"]),
                "name": p["name"],
                "price": int(p["price"]),
                "display_price": product_display_price(p),
                "description": p["description"] or "",
                "category_id": p["category_id"],
                "category_name": p["category_name"] if "category_name" in p.keys() else None,
                "photo_url": f"/api/photo/{p['id']}" if has_photo else None,
                "variants": [
                    {
                        "id": int(v["id"]),
                        "name": v["name"],
                        "price": int(v["price"]),
                    }
                    for v in variants
                ],
            }
        )
    return web.json_response(payload)


async def api_photo(request: web.Request) -> web.Response:
    if _bot is None:
        raise web.HTTPServiceUnavailable(text="Bot hali tayyor emas")
    try:
        product_id = int(request.match_info["product_id"])
    except (KeyError, ValueError):
        raise web.HTTPBadRequest(text="product_id noto'g'ri")

    product = get_product(product_id)
    if not product:
        raise web.HTTPNotFound(text="Mahsulot topilmadi")
    file_id = None
    if "image_file_id" in product.keys():
        file_id = product["image_file_id"]
    if not file_id:
        raise web.HTTPNotFound(text="Rasm yo'q")

    try:
        tg_file = await _bot.get_file(file_id)
        data = await tg_file.download_as_bytearray()
    except Exception as exc:
        logger.warning("Rasm yuklash xatosi product=%s: %s", product_id, exc)
        raise web.HTTPBadGateway(text="Rasm yuklanmadi") from exc

    return web.Response(body=bytes(data), content_type="image/jpeg")


async def api_order(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="JSON noto'g'ri") from exc

    init_data = (body.get("initData") or body.get("init_data") or "").strip()
    validated = validate_webapp_init_data(init_data)

    user_id: int | None = None
    full_name = "Mini App mijoz"
    username: str | None = None

    if validated and isinstance(validated.get("user"), dict):
        user = validated["user"]
        user_id = int(user.get("id"))
        full_name = (
            f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip()
            or full_name
        )
        username = user.get("username")
    else:
        # Brauzerda test qilish uchun (faqat initData yaroqsiz bo'lsa)
        dev_raw = body.get("dev_user_id")
        if dev_raw is not None and str(dev_raw).strip().isdigit():
            user_id = int(dev_raw)
            full_name = f"Dev user {user_id}"
        else:
            raise web.HTTPUnauthorized(text="initData yaroqsiz")

    phone = str(body.get("phone") or "").strip()
    address = str(body.get("address") or "").strip()
    slot = str(body.get("slot") or "").strip()
    note = str(body.get("note") or "").strip()
    items_raw = body.get("items") or []

    if not phone:
        raise web.HTTPBadRequest(text="Telefon majburiy")
    if not address:
        raise web.HTTPBadRequest(text="Manzil majburiy")
    if not isinstance(items_raw, list) or not items_raw:
        raise web.HTTPBadRequest(text="Savatcha bo'sh")

    order_items: list[dict[str, Any]] = []
    subtotal = 0

    for raw in items_raw:
        try:
            product_id = int(raw["product_id"])
            quantity = int(raw.get("quantity") or 1)
        except (KeyError, TypeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="items format noto'g'ri") from exc
        if quantity < 1:
            raise web.HTTPBadRequest(text="Miqdor 1 dan kam bo'lmasin")

        variant_id_raw = raw.get("variant_id")
        variant_id = int(variant_id_raw) if variant_id_raw not in (None, "", 0, "0") else 0

        product = get_product(product_id)
        if not product:
            raise web.HTTPBadRequest(text=f"Mahsulot topilmadi: {product_id}")

        if variant_id:
            variant = get_variant(variant_id)
            if not variant or int(variant["product_id"]) != product_id:
                raise web.HTTPBadRequest(text=f"Variant topilmadi: {variant_id}")
            unit_price = int(variant["price"])
            name = f"{product['name']} ({variant['name']})"
        else:
            variants = get_variants(product_id, active_only=True)
            if variants:
                raise web.HTTPBadRequest(
                    text=f"'{product['name']}' uchun o'lcham tanlang"
                )
            unit_price = int(product["price"])
            name = str(product["name"])

        line_total = unit_price * quantity
        subtotal += line_total
        order_items.append(
            {
                "product_id": product_id,
                "name": name,
                "price": unit_price,
                "quantity": quantity,
            }
        )

    if subtotal < MIN_ORDER_AMOUNT:
        raise web.HTTPBadRequest(
            text=f"Minimal buyurtma: {MIN_ORDER_AMOUNT:,} so'm"
        )

    total = subtotal + DELIVERY_PRICE
    upsert_user(user_id, full_name, username)
    set_user_phone(user_id, phone)

    order_id = create_order(
        user_id=user_id,
        pickup_address=SHOP_ADDRESS,
        delivery_address=address,
        description=note,
        phone=phone,
        price=total,
        delivery_slot=slot,
        subtotal=subtotal,
    )
    save_order_items_direct(order_id, order_items)

    order_row = get_order(order_id)
    text = format_order(order_row) if order_row else f"Buyurtma #{order_id}"

    if _bot is not None:
        for admin_id in ADMIN_IDS:
            try:
                await _bot.send_message(admin_id, f"🆕 Mini App\n{text}")
            except Exception as exc:
                logger.warning("Admin xabar xatosi %s: %s", admin_id, exc)
        try:
            await _bot.send_message(
                user_id,
                f"✅ Buyurtmangiz qabul qilindi!\n\n{text}",
            )
        except Exception as exc:
            logger.warning("Mijoz xabar xatosi %s: %s", user_id, exc)

    return web.json_response(
        {
            "ok": True,
            "order_id": order_id,
            "total": total,
            "subtotal": subtotal,
            "delivery_price": DELIVERY_PRICE,
        }
    )


async def serve_index(_request: web.Request) -> web.FileResponse:
    index = MINIAPP_DIR / "index.html"
    if not index.is_file():
        raise web.HTTPNotFound(text="index.html topilmadi")
    return web.FileResponse(index)


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/products", api_products)
    app.router.add_get("/api/photo/{product_id}", api_photo)
    app.router.add_post("/api/order", api_order)
    app.router.add_route("OPTIONS", "/api/{tail:.*}", lambda r: web.Response(status=204))

    if MINIAPP_DIR.is_dir():
        app.router.add_get("/", serve_index)
        app.router.add_static("/", MINIAPP_DIR, show_index=False)
    else:
        logger.warning("miniapp papkasi topilmadi: %s", MINIAPP_DIR)

    return app


def start_webapp_server(port: int | None = None) -> None:
    """aiohttp ni daemon thread da ishga tushiradi."""
    listen_port = port if port is not None else WEBAPP_PORT

    def _run() -> None:
        app = create_app()
        logger.info("Mini App server: http://0.0.0.0:%s", listen_port)
        web.run_app(
            app,
            host="0.0.0.0",
            port=listen_port,
            handle_signals=False,
            print=lambda *args: None,
        )

    thread = threading.Thread(target=_run, name="miniapp-web", daemon=True)
    thread.start()
    print(f"Mini App server ishga tushdi: http://0.0.0.0:{listen_port}")
