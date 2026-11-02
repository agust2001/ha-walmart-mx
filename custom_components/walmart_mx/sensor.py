"""Sensores: precio, precio anterior, ahorro, descuento, mínimo/máximo histórico, cambios, etc."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WalmartConfigEntry, WalmartProductCoordinator
from .entity import WalmartEntity

CURRENCY = "MXN"


@dataclass(frozen=True, kw_only=True)
class WalmartSensorDescription(SensorEntityDescription):
    value_fn: Callable[[WalmartProductCoordinator], Any]
    attrs_fn: Callable[[WalmartProductCoordinator], dict[str, Any]] | None = None


def _diff(c: WalmartProductCoordinator) -> float | None:
    h = c.history
    if h.last is None or h.previous is None:
        return None
    return round(h.last.price - h.previous.price, 2)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


SENSORS: tuple[WalmartSensorDescription, ...] = (
    WalmartSensorDescription(
        key="price",
        native_unit_of_measurement=CURRENCY,
        state_class=SensorStateClass.MEASUREMENT,  # habilita estadísticas (min/max/media) en el historial
        suggested_display_precision=2,
        value_fn=lambda c: c.data.price,
        attrs_fn=lambda c: {
            "product_id": c.product_id,
            "url": c.data.url,
            "brand": c.data.brand,
        },
    ),
    WalmartSensorDescription(
        key="was_price",
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda c: c.data.was_price,
    ),
    WalmartSensorDescription(
        key="savings",
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda c: c.data.savings or 0,
    ),
    WalmartSensorDescription(
        key="discount",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda c: c.data.discount_pct or 0,
    ),
    WalmartSensorDescription(
        key="lowest_price",
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda c: c.history.lowest.price if c.history.lowest else None,
        attrs_fn=lambda c: {"date": _iso(c.history.lowest.date) if c.history.lowest else None},
    ),
    WalmartSensorDescription(
        key="highest_price",
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda c: c.history.highest.price if c.history.highest else None,
        attrs_fn=lambda c: {"date": _iso(c.history.highest.date) if c.history.highest else None},
    ),
    WalmartSensorDescription(
        key="price_vs_lowest",
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda c: (
            round(c.data.price - c.history.lowest.price, 2)
            if c.data.price is not None and c.history.lowest
            else None
        ),
    ),
    WalmartSensorDescription(
        key="last_price_change",
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=_diff,
        attrs_fn=lambda c: {
            "previous_price": c.history.previous.price if c.history.previous else None,
            "current_price": c.history.last.price if c.history.last else None,
            "percent": (
                round(100 * _diff(c) / c.history.previous.price, 1)
                if c.history.previous and c.history.previous.price and _diff(c) is not None
                else None
            ),
        },
    ),
    WalmartSensorDescription(
        key="last_price_change_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.history.last.date if c.history.previous and c.history.last else None,
    ),
    WalmartSensorDescription(
        key="price_history",
        value_fn=lambda c: len(c.history.changes),
        attrs_fn=lambda c: {
            "first_seen": _iso(c.history.first_seen),
            "history": [{"date": p.date.isoformat(), "price": p.price} for p in c.history.changes],
        },
    ),
    WalmartSensorDescription(
        key="rating",
        suggested_display_precision=1,
        value_fn=lambda c: c.data.rating,
        attrs_fn=lambda c: {"reviews": c.data.reviews},
    ),
    WalmartSensorDescription(
        key="reviews",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.reviews,
    ),
    WalmartSensorDescription(
        key="order_limit",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.order_limit,
    ),
    WalmartSensorDescription(
        key="link",
        # URL corta (/ip/producto/<id>): el estado de un sensor admite máximo 255 caracteres
        value_fn=lambda c: c.data.url,
    ),
    WalmartSensorDescription(
        key="seller",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.seller,
    ),
    WalmartSensorDescription(
        key="last_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.last_check,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(WalmartSensor(coordinator, d) for d in SENSORS)


class WalmartSensor(WalmartEntity, SensorEntity):
    entity_description: WalmartSensorDescription
    # el historial completo puede ser largo: no se guarda en la base de datos en cada cambio
    _unrecorded_attributes = frozenset({"history"})

    def __init__(self, coordinator: WalmartProductCoordinator, description: WalmartSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator) if fn else None
