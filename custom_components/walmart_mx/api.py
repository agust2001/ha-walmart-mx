"""Cliente de walmart.com.mx.

Walmart no tiene API pública. La página de cada producto trae sus datos embebidos
en <script id="__NEXT_DATA__"> (JSON), así que se lee esa página y se parsea.
Este módulo solo depende de aiohttp para poder probarse fuera de Home Assistant.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

BASE_URL = "https://www.walmart.com.mx"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9",
}
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_ID_IN_URL_RE = re.compile(r"/ip/(?:[^/?#]*/)?(\d{6,20})")
_ID_ONLY_RE = re.compile(r"^\s*(\d{6,20})\s*$")


class WalmartError(Exception):
    """Error genérico al consultar Walmart."""


class ProductNotFound(WalmartError):
    """El producto no existe (404) o la página no trae datos del producto."""


class WalmartBlocked(WalmartError):
    """Walmart está frenando las consultas (anti-bot, captcha o límite)."""


def parse_product_id(text: str) -> str | None:
    """Saca el ID de producto de un link de Walmart o de un ID suelto."""
    if not text:
        return None
    m = _ID_IN_URL_RE.search(text) or _ID_ONLY_RE.match(text)
    return m.group(1) if m else None


def product_url(product_id: str) -> str:
    return f"{BASE_URL}/ip/producto/{product_id}"


@dataclass
class ProductData:
    """Lo que interesa de un producto en un momento dado."""

    product_id: str
    name: str
    price: float | None
    currency: str = "MXN"
    was_price: float | None = None
    savings: float | None = None
    discount_pct: float | None = None
    rollback: bool = False
    available: bool = False
    availability_status: str | None = None
    brand: str | None = None
    seller: str | None = None
    rating: float | None = None
    reviews: int | None = None
    order_limit: int | None = None
    image_url: str | None = None
    url: str = ""
    description: str | None = None
    raw_price_info: dict[str, Any] = field(default_factory=dict, repr=False)


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"[\d,]+(?:\.\d+)?", str(value))
    return float(m.group(0).replace(",", "")) if m else None


def parse_product_html(html: str, product_id: str) -> ProductData:
    """Convierte el HTML de la página de un producto en ProductData."""
    m = _NEXT_DATA_RE.search(html or "")
    if not m:
        # sin __NEXT_DATA__ casi siempre es una página de captcha / bloqueo
        raise WalmartBlocked("La página no trae datos del producto (posible captcha)")
    try:
        data = json.loads(m.group(1))
        product = data["props"]["pageProps"]["initialData"]["data"]["product"]
    except (ValueError, KeyError, TypeError) as err:
        raise ProductNotFound(f"Producto {product_id} sin datos") from err
    if not product:
        raise ProductNotFound(f"Producto {product_id} no encontrado")

    pi = product.get("priceInfo") or {}
    price = _num((pi.get("currentPrice") or {}).get("price"))
    was = _num((pi.get("wasPrice") or {}).get("price"))
    if was is not None and price is not None and was <= price:
        was = None
    savings = _num((pi.get("savingsAmount") or {}).get("amount"))
    if savings is None and was is not None and price is not None:
        savings = round(was - price, 2)
    discount = round(100 * savings / was, 1) if savings and was else None

    status = product.get("availabilityStatus")
    images = (product.get("imageInfo") or {}).get("allImages") or []
    image = images[0].get("url") if images else (product.get("imageInfo") or {}).get("thumbnailUrl")
    pid = product.get("usItemId") or product_id

    return ProductData(
        product_id=pid,
        name=(product.get("name") or f"Producto {pid}").strip(),
        price=price,
        currency=(pi.get("currentPrice") or {}).get("currencyUnit") or "MXN",
        was_price=was,
        savings=savings or None,
        discount_pct=discount,
        rollback=bool((pi.get("priceDisplayCodes") or {}).get("rollback")),
        available=status == "IN_STOCK",
        availability_status=status.lower() if isinstance(status, str) else None,
        brand=product.get("brand"),
        seller=product.get("sellerDisplayName") or product.get("sellerName"),
        rating=_num(product.get("averageRating")),
        reviews=int(product["numberOfReviews"]) if product.get("numberOfReviews") is not None else None,
        order_limit=product.get("orderLimit"),
        image_url=image,
        url=product_url(pid),
        description=product.get("shortDescription"),
        raw_price_info=pi,
    )


class WalmartClient:
    """Consulta productos de walmart.com.mx."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_product(self, product_id: str) -> ProductData:
        try:
            async with self._session.get(
                product_url(product_id),
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 404:
                    raise ProductNotFound(f"Producto {product_id} no existe")
                if resp.status in (403, 412, 429, 503):
                    raise WalmartBlocked(f"Walmart respondió {resp.status}")
                if resp.status != 200:
                    raise WalmartError(f"Walmart respondió {resp.status}")
                html = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WalmartError(f"Error de conexión: {err}") from err
        return parse_product_html(html, product_id)
