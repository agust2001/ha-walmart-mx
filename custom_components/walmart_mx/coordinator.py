"""Coordinador: consulta un producto cada cierto tiempo y lleva su historial de precios."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    ProductData,
    ProductNotFound,
    WalmartBlocked,
    WalmartClient,
    WalmartError,
    WalmartThrottle,
    product_url,
)
from .const import (
    CONF_PRODUCT_ID,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    EVENT_PRICE_CHANGED,
    MAX_HISTORY,
    STORAGE_VERSION,
    scan_interval,
)

_LOGGER = logging.getLogger(__name__)

WalmartConfigEntry = ConfigEntry["WalmartProductCoordinator"]


def async_get_throttle(hass: HomeAssistant) -> WalmartThrottle:
    """El límite de consultas es uno solo para todos los productos."""
    return hass.data.setdefault(DOMAIN, WalmartThrottle())


@dataclass
class PricePoint:
    price: float
    date: datetime

    def as_dict(self) -> dict[str, Any]:
        return {"price": self.price, "date": self.date.isoformat()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PricePoint:
        return cls(float(d["price"]), dt_util.parse_datetime(d["date"]) or dt_util.utcnow())


@dataclass
class PriceHistory:
    """Historial persistente de un producto (sobrevive reinicios de HA)."""

    first_seen: datetime | None = None
    last_seen: datetime | None = None  # última vez que se pudo leer el precio
    lowest: PricePoint | None = None
    highest: PricePoint | None = None
    changes: list[PricePoint] = field(default_factory=list)  # un punto por cada precio distinto

    @property
    def last(self) -> PricePoint | None:
        return self.changes[-1] if self.changes else None

    @property
    def previous(self) -> PricePoint | None:
        return self.changes[-2] if len(self.changes) > 1 else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "lowest": self.lowest.as_dict() if self.lowest else None,
            "highest": self.highest.as_dict() if self.highest else None,
            "changes": [p.as_dict() for p in self.changes],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> PriceHistory:
        if not d:
            return cls()
        return cls(
            first_seen=dt_util.parse_datetime(d["first_seen"]) if d.get("first_seen") else None,
            last_seen=dt_util.parse_datetime(d["last_seen"]) if d.get("last_seen") else None,
            lowest=PricePoint.from_dict(d["lowest"]) if d.get("lowest") else None,
            highest=PricePoint.from_dict(d["highest"]) if d.get("highest") else None,
            changes=[PricePoint.from_dict(p) for p in d.get("changes") or []],
        )

    def register(self, price: float, now: datetime) -> PricePoint | None:
        """Agrega un precio. Devuelve el punto anterior si el precio cambió."""
        if self.first_seen is None:
            self.first_seen = now
        self.last_seen = now
        if self.lowest is None or price < self.lowest.price:
            self.lowest = PricePoint(price, now)
        if self.highest is None or price > self.highest.price:
            self.highest = PricePoint(price, now)
        last = self.last
        if last is not None and abs(last.price - price) < 0.005:
            return None
        self.changes.append(PricePoint(price, now))
        del self.changes[:-MAX_HISTORY]
        return last


class WalmartProductCoordinator(DataUpdateCoordinator[ProductData]):
    """Mantiene actualizado un producto de Walmart."""

    config_entry: WalmartConfigEntry

    def __init__(self, hass: HomeAssistant, entry: WalmartConfigEntry) -> None:
        self.product_id: str = entry.data[CONF_PRODUCT_ID]
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.product_id}",
            update_interval=scan_interval(entry.options.get(CONF_SCAN_INTERVAL)),
        )
        self.throttle = async_get_throttle(hass)
        self.client = WalmartClient(async_get_clientsession(hass), self.throttle)
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{self.product_id}")
        self.history = PriceHistory()
        self.last_check: datetime | None = None

    async def async_load_stored(self) -> None:
        """Carga lo guardado para arrancar sin depender de que Walmart responda."""
        stored = await self._store.async_load() or {}
        self.history = PriceHistory.from_dict(stored)
        product = stored.get("product")
        if product:
            known = {f.name for f in fields(ProductData)}
            self.data = ProductData(**{k: v for k, v in product.items() if k in known})
        else:
            # guardado por una versión anterior: solo se conoce el nombre y el precio
            self.data = ProductData(
                product_id=self.product_id,
                name=self.config_entry.title,
                price=self.history.last.price if self.history.last else None,
                url=product_url(self.product_id),
            )

    @property
    def is_stale(self) -> bool:
        """Si ya pasó el intervalo desde la última lectura del precio."""
        seen = self.history.last_seen
        return seen is None or dt_util.utcnow() - seen >= self.update_interval

    def _stored_data(self) -> dict[str, Any]:
        product = asdict(self.data)
        del product["raw_price_info"]
        return {**self.history.as_dict(), "product": product}

    async def _async_update_data(self) -> ProductData:
        try:
            data = await self.client.async_get_product(self.product_id)
        except ProductNotFound as err:
            raise UpdateFailed(f"Producto {self.product_id} no encontrado en Walmart") from err
        except WalmartBlocked as err:
            _LOGGER.debug("%s: se mantiene el último dato: %s", self.product_id, err)
            return self.data
        except WalmartError as err:
            raise UpdateFailed(str(err)) from err

        now = dt_util.utcnow()
        self.last_check = now
        if data.price is not None:
            anterior = self.history.register(data.price, now)
            if anterior is not None:
                diff = round(data.price - anterior.price, 2)
                _LOGGER.info("%s: precio %.2f -> %.2f", data.name, anterior.price, data.price)
                self.hass.bus.async_fire(
                    EVENT_PRICE_CHANGED,
                    {
                        "product_id": data.product_id,
                        "name": data.name,
                        "old_price": anterior.price,
                        "new_price": data.price,
                        "difference": diff,
                        "percent": round(100 * diff / anterior.price, 1) if anterior.price else None,
                        "url": data.url,
                        "lowest_price": self.history.lowest.price if self.history.lowest else None,
                    },
                )
        self._store.async_delay_save(self._stored_data, 10)
        return data
