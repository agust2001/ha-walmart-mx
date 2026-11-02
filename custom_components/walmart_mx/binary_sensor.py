"""Sensores binarios: en stock, en oferta, en su precio mínimo histórico."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WalmartConfigEntry, WalmartProductCoordinator
from .entity import WalmartEntity


@dataclass(frozen=True, kw_only=True)
class WalmartBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[WalmartProductCoordinator], bool | None]


def _at_lowest(c: WalmartProductCoordinator) -> bool | None:
    if c.data.price is None or c.history.lowest is None:
        return None
    # "en mínimo" solo tiene sentido si el precio alguna vez fue distinto
    return len(c.history.changes) > 1 and c.data.price <= c.history.lowest.price + 0.005


BINARY_SENSORS: tuple[WalmartBinaryDescription, ...] = (
    WalmartBinaryDescription(key="in_stock", is_on_fn=lambda c: c.data.available),
    WalmartBinaryDescription(key="on_sale", is_on_fn=lambda c: bool(c.data.savings) or c.data.rollback),
    WalmartBinaryDescription(key="at_lowest_price", is_on_fn=_at_lowest),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(WalmartBinarySensor(coordinator, d) for d in BINARY_SENSORS)


class WalmartBinarySensor(WalmartEntity, BinarySensorEntity):
    entity_description: WalmartBinaryDescription

    def __init__(self, coordinator: WalmartProductCoordinator, description: WalmartBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator)
