from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def lookup_barcode_name(barcode: str) -> dict[str, Any] | None:
    """Open Food Facts dan mahsulot nomini qidiradi. Topilmasa None."""
    code = barcode.strip()
    if not code or not code.isdigit() or len(code) < 8:
        return None
    url = f"https://world.openfoodfacts.org/api/v2/product/{code}.json"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "YetkazibBerishBot/1.0 (shop bot)"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.info("Barcode lookup failed: %s", exc)
        return None

    if data.get("status") != 1:
        return None
    product = data.get("product") or {}
    name = (
        product.get("product_name_uz")
        or product.get("product_name_ru")
        or product.get("product_name_en")
        or product.get("product_name")
        or ""
    ).strip()
    if not name:
        return None
    brand = (product.get("brands") or "").strip()
    if brand and brand.lower() not in name.lower():
        name = f"{brand} {name}".strip()
    return {"name": name[:80], "brand": brand}
