import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from bot.config import BOT_TOKEN
from bot.database import init_db
from bot.extras import (
    build_extra_conversations,
    cancel_order_callback,
    courier_panel,
    fav_callback,
    reorder_callback,
    show_bonus,
    show_favorites,
)
from bot.handlers import (
    admin_callback,
    admin_panel,
    admin_product_callback,
    admin_status_callback,
    build_order_conversation,
    build_product_admin_conversation,
    cart_callback,
    contact_info,
    help_command,
    my_orders,
    payment_callback,
    precheckout_callback,
    product_callback,
    show_cart_message,
    show_catalog,
    start,
    successful_payment,
)


def _start_health_server() -> None:
    """Render Web Service uchun PORT da oddiy health endpoint."""
    import os
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port_raw = os.environ.get("PORT", "").strip()
    if not port_raw.isdigit():
        return
    port = int(port_raw)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan.")

    _start_health_server()
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(build_order_conversation())
    app.add_handler(build_product_admin_conversation())
    for conv in build_extra_conversations():
        app.add_handler(conv)

    app.add_handler(MessageHandler(filters.Regex("^🛍 Katalog$"), show_catalog))
    app.add_handler(MessageHandler(filters.Regex("^🛒 Savatcha$"), show_cart_message))
    app.add_handler(MessageHandler(filters.Regex("^⭐ Sevimlilar$"), show_favorites))
    app.add_handler(MessageHandler(filters.Regex("^🎁 Bonus$"), show_bonus))
    app.add_handler(MessageHandler(filters.Regex("^📋 Mening buyurtmalarim$"), my_orders))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yordam$"), help_command))
    app.add_handler(MessageHandler(filters.Regex("^📞 Aloqa$"), contact_info))
    app.add_handler(MessageHandler(filters.Regex("^🛠 Admin panel$"), admin_panel))
    app.add_handler(MessageHandler(filters.Regex("^🚴 Kuryer panel$"), courier_panel))

    app.add_handler(CallbackQueryHandler(product_callback, pattern=r"^(product:|catalog:)"))
    app.add_handler(CallbackQueryHandler(cart_callback, pattern=r"^cart"))
    app.add_handler(CallbackQueryHandler(fav_callback, pattern=r"^fav:\d+$"))
    app.add_handler(CallbackQueryHandler(reorder_callback, pattern=r"^reorder:\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_order_callback, pattern=r"^cancel_order:\d+$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(
        CallbackQueryHandler(
            admin_product_callback,
            pattern=r"^admin_prod:(list|cats|toggle:\d+|del:\d+|delcat:\d+|delsize:\d+)$",
        )
    )
    app.add_handler(CallbackQueryHandler(admin_status_callback, pattern=r"^admin_status:"))
    app.add_handler(CallbackQueryHandler(payment_callback, pattern=r"^pay"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    print("Bot ishga tushdi...")
    app.run_polling(
        allowed_updates=["message", "callback_query", "pre_checkout_query"]
    )


if __name__ == "__main__":
    main()
