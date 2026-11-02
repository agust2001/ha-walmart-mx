"""Botón para consultar el precio en el momento."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WalmartConfigEntry
from .entity import WalmartEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WalmartRefreshButton(entry.runtime_data, "refresh")])


class WalmartRefreshButton(WalmartEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
